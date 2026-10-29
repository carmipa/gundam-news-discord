"""
Stats module - contadores da varredura e veredito de saúde por ciclo.

Um painel que só mede SUCESSO é indistinguível de um painel que não mede nada:
`feeds_falhos=0` tanto significa "nenhuma fonte falhou" quanto "o contador nunca
foi alimentado". Este módulo mede também a AUSÊNCIA — fontes que pararam de
entregar, ciclos sem notícia, traduções rejeitadas — e fecha cada varredura com
um veredito explícito e o motivo dele.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Vereditos possíveis de uma varredura. Três estados, nunca dois: "não verificou"
# não é aprovação (mesma disciplina das guardas executáveis).
VEREDITO_OK = "OK"
VEREDITO_ATENCAO = "ATENCAO"
VEREDITO_ANOMALIA = "ANOMALIA"


class BotStats:
    """Estatísticas do bot em memória."""

    def __init__(self):
        """Inicializa contadores de estatísticas."""
        self.start_time = datetime.now()
        self.scans_completed = 0
        self.news_posted = 0
        self.feeds_failed = 0
        self.last_scan_time = None
        self.cache_hits_total = 0
        # Ausência: contadores que só existem para revelar o que NÃO aconteceu.
        self.traducoes_rejeitadas = 0
        # Separados de `traducoes_rejeitadas` para a causa não se perder: página de
        # erro, recusa do serviço e pausa do disjuntor pedem ações diferentes.
        self.traducoes_falhas_servico = 0
        self.traducoes_suspensas = 0
        self.feeds_vazios = 0
        self.ciclos_sem_envio = 0
        self.ultimo_veredito: Optional[Dict[str, Any]] = None

    @property
    def uptime(self) -> timedelta:
        """
        Retorna tempo de atividade do bot.

        Returns:
            timedelta desde o início
        """
        return datetime.now() - self.start_time

    def format_uptime(self) -> str:
        """
        Formata uptime de forma legível.

        Returns:
            String formatada (ex: "2d 4h 30m")
        """
        total_seconds = int(self.uptime.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


def avaliar_varredura(
    fontes_totais: int,
    feeds_falhos: int,
    feeds_vazios: int,
    enviadas: int,
    cache_hits: int,
    traducoes_rejeitadas: int,
    ciclos_sem_envio: int,
    traducoes_falhas_servico: int = 0,
    traducoes_suspensas: int = 0,
) -> Dict[str, Any]:
    """
    Fecha uma varredura com veredito e MOTIVO, medindo ausência e não só sucesso.

    PROPÓSITO DE NEGÓCIO:
        É o painel de saúde do bot. Sem ele, uma varredura que não entregou nada
        porque metade das fontes morreu tem exatamente a mesma aparência de uma
        varredura tranquila num dia sem notícia — e a diferença entre as duas é o
        bot estar funcionando ou não.

    INVARIANTES DO DOMÍNIO:
        - Todo veredito vem acompanhado de pelo menos um MOTIVO textual quando não
          é OK. Veredito sem motivo é rótulo, não diagnóstico.
        - O zero legítimo é dito com todas as letras: "0 enviadas, e nenhuma fonte
          falhou" é um motivo registado, não silêncio.
        - Nenhum contador vira veredito sozinho: a proporção é que decide. Uma
          fonte falha em 60 é ruído; 30 em 60 é anomalia.
        - `fontes_totais == 0` é ANOMALIA, nunca OK — catálogo vazio é a falha que
          este instrumento existe para apanhar, e um detector que reporta catálogo
          vazio como saudável tem um buraco exatamente onde devia enxergar.
        - Cada causa de tradução degradada tem motivo próprio (página de erro,
          recusa do serviço, disjuntor aberto). Juntar as três num texto só já fez o
          painel dizer "página de erro" durante nove dias de HTTP 429.

    COMPORTAMENTO EM CASO DE FALHA:
        Não levanta. Entradas negativas ou de tipo inesperado são normalizadas
        para 0; o pior caso devolve ANOMALIA com o motivo "contadores inválidos",
        que é visível — nunca um OK por omissão.
    """
    def _n(v: Any) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return -1
        return v if v >= 0 else -1

    valores = {
        "fontes_totais": _n(fontes_totais),
        "feeds_falhos": _n(feeds_falhos),
        "feeds_vazios": _n(feeds_vazios),
        "enviadas": _n(enviadas),
        "cache_hits": _n(cache_hits),
        "traducoes_rejeitadas": _n(traducoes_rejeitadas),
        "ciclos_sem_envio": _n(ciclos_sem_envio),
        "traducoes_falhas_servico": _n(traducoes_falhas_servico),
        "traducoes_suspensas": _n(traducoes_suspensas),
    }
    if any(v < 0 for v in valores.values()):
        return {
            "veredito": VEREDITO_ANOMALIA,
            "motivos": ["contadores inválidos — a medição não é confiável"],
            "metricas": valores,
            "quando": datetime.now().isoformat(timespec="seconds"),
        }

    motivos: List[str] = []
    veredito = VEREDITO_OK

    def _sobe(novo: str) -> None:
        nonlocal veredito
        ordem = {VEREDITO_OK: 0, VEREDITO_ATENCAO: 1, VEREDITO_ANOMALIA: 2}
        if ordem[novo] > ordem[veredito]:
            veredito = novo

    total = valores["fontes_totais"]
    falhos = valores["feeds_falhos"]
    vazios = valores["feeds_vazios"]

    if total == 0:
        motivos.append("catálogo vazio: nenhuma fonte foi carregada")
        _sobe(VEREDITO_ANOMALIA)
    else:
        # Fontes que não entregaram, por qualquer motivo (falha ou 200 sem itens).
        mudas = falhos + vazios
        proporcao = mudas / total
        if proporcao >= 0.5:
            motivos.append(
                f"{mudas} de {total} fontes não entregaram nada "
                f"({falhos} falharam, {vazios} responderam vazias)"
            )
            _sobe(VEREDITO_ANOMALIA)
        elif proporcao >= 0.25:
            motivos.append(
                f"{mudas} de {total} fontes não entregaram nada "
                f"({falhos} falharam, {vazios} responderam vazias)"
            )
            _sobe(VEREDITO_ATENCAO)

    if valores["traducoes_rejeitadas"] > 0:
        motivos.append(
            f"{valores['traducoes_rejeitadas']} tradução(ões) rejeitadas — "
            "o serviço devolveu página de erro; foi publicado o original"
        )
        _sobe(VEREDITO_ATENCAO)

    if valores["traducoes_falhas_servico"] > 0:
        motivos.append(
            f"{valores['traducoes_falhas_servico']} tradução(ões) recusadas pelo serviço "
            "(erro ou HTTP 429); foi publicado o original"
        )
        _sobe(VEREDITO_ATENCAO)

    if valores["traducoes_suspensas"] > 0:
        motivos.append(
            f"{valores['traducoes_suspensas']} tradução(ões) não tentadas — tradução "
            "pausada depois de recusa do serviço; foi publicado o original"
        )
        _sobe(VEREDITO_ATENCAO)

    # Ausência de entrega: um ciclo sem envio é normal; vários seguidos, não.
    if valores["enviadas"] == 0:
        if valores["ciclos_sem_envio"] >= 24:
            motivos.append(
                f"{valores['ciclos_sem_envio']} ciclos seguidos sem publicar nada"
            )
            _sobe(VEREDITO_ANOMALIA)
        elif valores["ciclos_sem_envio"] >= 6:
            motivos.append(
                f"{valores['ciclos_sem_envio']} ciclos seguidos sem publicar nada"
            )
            _sobe(VEREDITO_ATENCAO)
        else:
            # O zero legítimo, dito com todas as letras.
            motivos.append(
                "0 publicadas neste ciclo — sem novidade nas fontes que responderam"
            )

    if veredito == VEREDITO_OK and not motivos:
        motivos.append(
            f"{valores['enviadas']} publicadas, {total - falhos - vazios} "
            f"de {total} fontes entregaram"
        )

    return {
        "veredito": veredito,
        "motivos": motivos,
        "metricas": valores,
        "quando": datetime.now().isoformat(timespec="seconds"),
    }


# Instância global de estatísticas
stats = BotStats()
