"""
Canal de notícias configurado por guild: registro no arranque e desvinculação
quando o canal é apagado no Discord.
"""
import logging

from bot.views.filter_dashboard import FilterDashboard
from utils.storage import load_config_cached, save_config_safe

log = logging.getLogger("MaftyIntel")


def _preparar_views_e_canais(bot) -> dict:
    """
    Registra as views persistentes e avisa sobre canais que não estão visíveis.

    PROPÓSITO DE NEGÓCIO:
        Faz o painel de filtros voltar a responder depois de um restart e deixa
        no log quais guilds estão com o canal configurado inacessível.

    INVARIANTES DO DOMÍNIO:
        - É ACESSÓRIO: nada aqui pode impedir o scheduler de arrancar. Quem chama
          é responsável por não deixar a exceção subir ao handler de evento.
        - Uma guild com id inválido não interrompe o registro das outras.
        - NÃO apaga `channel_id`. `get_channel() is None` no arranque também
          acontece com guild momentaneamente indisponível (queda parcial do
          Discord); apagar ali fazia a guild perder a configuração para sempre, em
          silêncio. Canal apagado de fato é tratado pelo evento
          `on_guild_channel_delete`, que é o sinal definitivo.

    COMPORTAMENTO EM CASO DE FALHA:
        Falhas por guild são registadas e o laço continua; nada é gravado.

    Returns:
        O config carregado — o anúncio de versão precisa dele para saber a que
        canais escrever. Devolve {} se o ficheiro não for um dict.
    """
    cfg = load_config_cached({})
    if isinstance(cfg, dict):
        for gid in cfg.keys():
            try:
                bot.add_view(FilterDashboard(int(gid)))
                log.info(f"View persistente registrada para guild {gid}")
            except ValueError as e:
                log.error(f"Erro ao converter guild_id '{gid}' para inteiro: {e}")
            except Exception as e:
                log.error(f"Erro ao registrar view persistente para guild {gid}: {type(e).__name__}: {e}", exc_info=True)

        for gid, gdata in list(cfg.items()):
            if not isinstance(gdata, dict): continue
            channel_id = gdata.get("channel_id")
            if not channel_id: continue
            try:
                if bot.get_channel(int(channel_id)) is None:
                    log.warning(
                        f"⚠️ Canal configurado não visível ao iniciar: channel_id {channel_id}, Guild {gid}. "
                        "Configuração MANTIDA (pode ser indisponibilidade temporária); "
                        "a varredura pula este canal enquanto ele não aparecer."
                    )
            except (ValueError, TypeError):
                log.error(f"channel_id inválido no config: {channel_id!r} (Guild {gid})")

    return cfg if isinstance(cfg, dict) else {}


def desvincular_canal_apagado(guild_id: int, channel_id: int) -> bool:
    """
    Remove do config o canal de notícias que foi APAGADO no Discord.

    PROPÓSITO DE NEGÓCIO:
        Canal apagado não volta; deixar o id no config faz a guild parecer
        configurada quando não recebe nada. O admin precisa rodar /set_canal.

    INVARIANTES DO DOMÍNIO:
        - Só age sobre o canal configurado daquela guild; apagar outro canal da
          guild não mexe em nada.
        - Mantém filtros e idioma: só `channel_id` vira None.

    COMPORTAMENTO EM CASO DE FALHA:
        Devolve False quando não havia nada a fazer; exceções de disco ficam
        registradas por `save_config_safe` (que não levanta).
    """
    cfg = load_config_cached({})
    if not isinstance(cfg, dict):
        return False
    gdata = cfg.get(str(guild_id))
    if not isinstance(gdata, dict) or str(gdata.get("channel_id")) != str(channel_id):
        return False
    gdata["channel_id"] = None
    save_config_safe(cfg)
    log.warning(
        f"🗑️ Canal de notícias {channel_id} da guild {guild_id} foi apagado no Discord; "
        "desvinculado do config. Um administrador precisa rodar /set_canal."
    )
    return True
