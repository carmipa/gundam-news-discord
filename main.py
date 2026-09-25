# =========================================================
# Mafty Sovereign - Gundam News Bot v3.0
# main.py (Modularized)
# =========================================================
"""
Ponto de entrada do bot Discord.
- Carrega config, inicia web server, registra views e cogs.
- Sobe o agendador de varreduras e, ao detectar novo commit, envia anúncio de atualização.
- Exceções de libs (discord, aiohttp) não são convertidas; erros do domínio podem usar utils.exceptions.
"""
import logging
import asyncio
from datetime import datetime
import discord
from discord.ext import commands

from settings import TOKEN, COMMAND_PREFIX, LOG_LEVEL, SCAN_VERBOSE
from utils.storage import p, load_json_safe, load_config_cached, save_config_safe, save_json_safe
from bot.views.filter_dashboard import FilterDashboard
from core.scanner import start_scheduler, solicitar_varredura_manual
from web.server import start_web_server  # Novo web server
from utils.git_info import get_git_changes, get_current_hash, get_commits_since

# Configuração de Logs
from utils.logger import setup_logger, wire_child_loggers_to_main

# Configura o logger global do bot
_level = logging.DEBUG if LOG_LEVEL == "DEBUG" else logging.INFO
log = setup_logger(name="MaftySovereign", log_file="logs/bot.log", level=_level)

# Mesmos handlers do MaftySovereign nos ramos MaftyIntel / MaftyWeb / CyberIntel
# (senão INFO/DEBUG ficam só no root WARNING e somem do `docker compose logs`)
wire_child_loggers_to_main(
    "MaftySovereign",
    "MaftyIntel",
    "MaftyWeb",
    "CyberIntel",
)

if SCAN_VERBOSE and LOG_LEVEL != "DEBUG":
    log.info(
        "📡 SCAN_VERBOSE=1 — logs detalhados da varredura (Raio-X) em INFO "
        "(sem subir LOG_LEVEL=DEBUG)."
    )

# Silencia o barulho de bibliotecas externas
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("discord.http").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.INFO)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# =========================================================
# SETUP DO BOT
# =========================================================

def _preparar_views_e_canais(bot) -> dict:
    """
    Registra as views persistentes e limpa canais que deixaram de existir.

    PROPÓSITO DE NEGÓCIO:
        Faz o painel de filtros voltar a responder depois de um restart e evita
        que o bot tente publicar num canal apagado a cada varredura.

    INVARIANTES DO DOMÍNIO:
        - É ACESSÓRIO: nada aqui pode impedir o scheduler de arrancar. Quem chama
          é responsável por não deixar a exceção subir ao handler de evento.
        - Uma guild com id inválido não interrompe o registro das outras.
        - O config só é gravado quando algo mudou de facto.

    COMPORTAMENTO EM CASO DE FALHA:
        Falhas por guild são registadas e o laço continua. Falha na gravação do
        config propaga para o chamador, que a converte em log e segue.

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

        # Valida canais configurados: avisa se algum canal não existe (ex.: foi deletado)
        cfg_changed = False
        for gid, gdata in list(cfg.items()):
            if not isinstance(gdata, dict): continue
            channel_id = gdata.get("channel_id")
            if not channel_id: continue
            try:
                ch = bot.get_channel(int(channel_id))
                if ch is None:
                    guild_name = ""
                    try:
                        g = bot.get_guild(int(gid))
                        if g:
                            guild_name = f" (servidor: {g.name})"
                    except (ValueError, TypeError):
                        pass
                    log.warning(
                        f"⚠️ Canal configurado não encontrado ao iniciar: channel_id {channel_id}, Guild {gid}{guild_name}. "
                        "Removendo do config para evitar falhas."
                    )
                    gdata["channel_id"] = None
                    cfg_changed = True
            except (ValueError, TypeError):
                pass
                
        if cfg_changed:
            save_config_safe(cfg)

    return cfg if isinstance(cfg, dict) else {}


async def main():
    # Intents
    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = True

    # Bot Instance
    bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

    # =========================================================
    # EVENTOS
    # =========================================================

    @bot.event
    async def on_interaction(interaction: discord.Interaction):
        """Registra no log todo uso de comando (slash) para acompanhamento."""
        if interaction.type != discord.InteractionType.application_command:
            return
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        command_name = interaction.command.name if interaction.command else "?"
        guild_id = interaction.guild.id if interaction.guild else "DM"
        user = interaction.user
        options = interaction.data.get("options", []) if interaction.data else []
        parts = []
        for o in options:
            if isinstance(o, dict):
                name = o.get("name", "")
                val = o.get("value", "")
                parts.append(f"{name}={val}" if name else str(val))
        opts_str = " ".join(parts)
        log.info(
            f"📌 [{now_str}] Comando: /{command_name} | por {user} (ID: {user.id}) | Guild: {guild_id}"
            + (f" | {opts_str}" if opts_str.strip() else "")
        )

    @bot.command()
    @commands.is_owner()
    async def sync(ctx):
        """Comando manual para sincronizar comandos Slash."""
        try:
            # Sync global
            synced = await bot.tree.sync()
            await ctx.send(f"✅ Sincronizado {len(synced)} comandos globalmente.")
            
            # Sync na guild atual também (garantia)
            if ctx.guild:
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced_guild = await ctx.bot.tree.sync(guild=ctx.guild)
                await ctx.send(f"✅ Sincronizado {len(synced_guild)} comandos na guild: {ctx.guild.name}")
        except discord.HTTPException as e:
            log.error(f"Erro HTTP ao sincronizar comandos: {e.status} - {e.text}")
            await ctx.send(f"❌ Erro HTTP ao sincronizar: {e.status}")
        except Exception as e:
            log.exception(f"Erro ao sincronizar comandos: {type(e).__name__}: {e}")
            await ctx.send(f"❌ Erro ao sincronizar: {type(e).__name__}")

    @bot.event
    async def on_ready():
        # on_ready dispara também em reconexões. A inicialização (web server, views,
        # sync de comandos, scheduler, anúncio de versão) deve ocorrer UMA vez por
        # processo — senão o web server tenta reabrir a porta, os comandos são
        # re-sincronizados (rate limit) e o anúncio é reenviado a cada reconexão.
        if getattr(bot, "_startup_done", False):
            log.info("🔄 on_ready (reconexão) — inicialização já concluída, pulando.")
            return

        log.info(f"✅ Bot conectado como: {bot.user} (ID: {bot.user.id})")
        log.info(f"📊 Servidores conectados: {len(bot.guilds)}")

        # 0. Iniciar Web Server (Fase 10) — ACESSÓRIO, nunca pode derrubar o resto.
        #
        # Exceção levantada dentro de um handler de evento do discord.py é apenas
        # REGISTADA por ele: tudo o que viria depois neste on_ready deixa de correr.
        # Como o scheduler (passo 3) vem depois, uma falha aqui produz o pior modo
        # possível — bot online, respondendo a comandos, que NUNCA varre.
        #
        # E o cenário é alcançável: `_startup_done` só é marcado no fim deste
        # handler, portanto uma falha em qualquer passo intermédio faz a próxima
        # reconexão reexecutar o on_ready — e aí `site.start()` encontra a porta já
        # aberta pela tentativa anterior e levanta OSError(EADDRINUSE), tornando o
        # bot permanentemente mudo até alguém reiniciar o contêiner.
        #
        # O dashboard é conveniência; a varredura é a função do bot. Se um dos dois
        # tiver de cair, é o dashboard.
        try:
            # Host e porta vêm de variáveis de ambiente (padrão: 127.0.0.1:8080)
            await start_web_server()
        except OSError as e:
            log.error(
                f"❌ Web Dashboard não subiu ({type(e).__name__}: {e}). "
                "O bot CONTINUA: varredura e comandos não dependem dele."
            )
        except Exception as e:
            log.exception(
                f"❌ Web Dashboard falhou de forma inesperada ({type(e).__name__}: {e}). "
                "O bot CONTINUA: varredura e comandos não dependem dele."
            )

        # 1. Carregar Views Persistentes — ACESSÓRIO.
        # Envolvido porque `save_config_safe` (fim do bloco) escreve em disco e
        # pode levantar; sem esta rede, disco cheio aqui impede o scheduler do
        # passo 3 de arrancar e o bot fica online sem varrer.
        cfg = {}
        try:
            cfg = _preparar_views_e_canais(bot)
        except Exception as e:
            log.exception(
                f"❌ Falha ao preparar views/canais ({type(e).__name__}: {e}). "
                "O bot CONTINUA: a varredura não depende disto."
            )

        # 2. Sync Comandos (Slash)
        try:
            # Sincroniza global (pode demorar) ou por guild
            # Para dev, sync por guild é mais rápido e garante update imediato
            # IMPORTANTE: É necessário copiar os globais para a guild antes de syncar a guild
            for guild in bot.guilds:
                bot.tree.copy_global_to(guild=discord.Object(id=guild.id))
                await bot.tree.sync(guild=discord.Object(id=guild.id))
                log.info(f"Comandos sincronizados (copy_global) em: {guild.name}")
        except discord.HTTPException as e:
            log.error(f"Erro HTTP no sync de comandos: {e.status} - {e.text}")
        except Exception as e:
            log.exception(f"Falha no sync de comandos: {type(e).__name__}: {e}")

        # 3. Iniciar Loop de Scanner
        start_scheduler(bot)

        # 4. Anúncio de Versão (Git Check)
        try:
            current_hash = get_current_hash()
            state_file = p("state.json")
            state = load_json_safe(state_file, {})
            last_hash = state.get("last_announced_hash")

            if current_hash:
                # Texto do(s) último(s) commit(s) como "o que foi feito" nesta atualização
                # Como o usuário pediu para anunciar a cada reinício, mostramos sempre as últimas alterações.
                commits = get_commits_since(last_hash if current_hash != last_hash else None, max_commits=1)
                changes_block = "\n".join(f"• {c}" for c in commits)
                if len(changes_block) > 3800:
                    changes_block = changes_block[:3797] + "..."
                repo_url = "https://github.com/carmipa/gundam-news-discord"
                description = (
                    f"**Última atualização de inteligência aplicada:**\n{changes_block}\n\n"
                    f"**Repository:** [github.com/carmipa/gundam-news-discord]({repo_url})"
                )

                now = datetime.now()
                date_str = now.strftime("%Y.%m.%d")
                time_str = now.strftime("%H:%M")
                # Alerta: atualização do sistema (deploy) — 🔄 📦 teal RGB(26,188,156)
                UPDATE_COLOR = discord.Color.from_rgb(26, 188, 156)
                embed = discord.Embed(
                    title=f"🔄 📦 System update — {date_str}",
                    description=description,
                    color=UPDATE_COLOR
                )
                embed.set_author(
                    name="🔄 Stability update",
                    icon_url=bot.user.display_avatar.url if bot.user and bot.user.display_avatar else None
                )
                embed.set_footer(text=f"🔄 Update applied | Deploy: {time_str} BRT")

                # Envia para TODOS os canais configurados (cada servidor vê o anúncio)
                sent = 0
                if isinstance(cfg, dict):
                    for gid, gdata in cfg.items():
                        if not isinstance(gdata, dict):
                            continue
                        ch_id = gdata.get("channel_id")
                        if not ch_id:
                            continue
                        ch = bot.get_channel(int(ch_id))
                        if ch:
                            try:
                                await ch.send(embed=embed)
                                sent += 1
                                log.info(f"📢 Anúncio de atualização enviado ao canal {ch.name} (Guild {gid})")
                            except Exception as e:
                                log.warning(f"Falha ao enviar anúncio no canal {ch_id}: {e}")

                if sent > 0:
                    state["last_announced_hash"] = current_hash
                    save_json_safe(state_file, state)
                    log.info(f"📢 Atualização {current_hash} anunciada em {sent} canal(is).")
                else:
                    log.warning("⚠️ Erro ao encontrar canais para anunciar o reinício/atualização do bot.")
            else:
                log.info("ℹ️ Não foi possível obter o hash do Git para anúncio.")

        except Exception as e:
            log.exception(f"❌ Falha ao processar anúncio de versão: {type(e).__name__}: {e}")

        # Marca a inicialização como concluída (não repetir em reconexões).
        bot._startup_done = True

    # =========================================================
    # CARREGAR COGS
    # =========================================================
    
    # Porta única de varredura manual para os cogs: aplica o intervalo mínimo e a
    # não-sobreposição do engine e devolve (resultado, segundos) para a resposta.
    def pedir_varredura(trigger: str = "manual"):
        return solicitar_varredura_manual(bot, trigger)

    try:
        # Carrega extensões normais (que têm setup(bot))
        await bot.load_extension("bot.cogs.info")
        
        # Admin, Dashboard e Status precisam da função de scan injetada
        # Como load_extension não aceita args, importamos e setup manual 
        # ou usamos uma abordagem de injeção. 
        # Simplificação: Passamos via bot instance ou setup manual.
        
        # Abordagem Híbrida: Carregar Status normalmente, e Admin/Dashboard manualmente
        from bot.cogs.status import setup as setup_status
        from bot.cogs.admin import setup as setup_admin
        from bot.cogs.dashboard import setup as setup_dashboard
        
        await setup_status(bot, pedir_varredura)
        await setup_admin(bot, pedir_varredura)
        await setup_dashboard(bot, pedir_varredura)
        
        log.info("🧩 Cogs carregados com sucesso.")
    except Exception as e:
        log.exception(f"Falha ao carregar cogs: {e}")

    # =========================================================
    # START
    # =========================================================
    await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("🛑 Bot encerrado pelo usuário.")
    except Exception as e:
        log.exception(f"🔥 Erro fatal: {e}")
