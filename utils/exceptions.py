"""
Exceções personalizadas do Gundam News Discord Bot.

Todas herdam de GundamIntelError para permitir "except GundamIntelError"
e deixar erros de bibliotecas externas (discord, aiohttp) passarem.

Uso recomendado:
- Levante a exceção mais específica possível (ex: InvalidCleanTypeError).
- Em pontos de entrada (comandos, loop), capture GundamIntelError ou a específica,
  logue com log.exception() e responda ao usuário de forma clara.

Níveis de log sugeridos:
- DEBUG: fluxo interno, cache hit, filtro bloqueou item.
- INFO:  varredura iniciada/concluída, backup criado, canal configurado.
- WARNING: recuperável (arquivo não existe usando padrão, timeout em um feed, interação expirada).
- ERROR: falha que merece atenção (JSON corrompido, permissão negada, falha ao enviar mensagem).
- CRITICAL/exception: falha que pode derrubar o fluxo (erro não tratado no loop); use log.exception().

Documentação completa: docs/LOGGING_AND_EXCEPTIONS.md
"""


class GundamIntelError(Exception):
    """Base para todas as exceções do bot. Capture esta para tratar qualquer erro do domínio."""

    def __init__(self, message: str, *args, **kwargs):
        self.message = message
        super().__init__(message, *args, **kwargs)


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------


class ConfigError(GundamIntelError):
    """Configuração inválida ou ausente (ex: guild sem channel_id, filtros vazios)."""
    pass


# ---------------------------------------------------------------------------
# Storage / Persistência
# ---------------------------------------------------------------------------


class StorageError(GundamIntelError):
    """Erro ao ler ou escrever arquivo de persistência (config, state, history)."""
    pass


class InvalidCleanTypeError(ValueError, GundamIntelError):
    """
    Tipo de limpeza do state.json inválido.
    Herda de ValueError para compatibilidade com código que já captura ValueError.
    """
    pass


# ---------------------------------------------------------------------------
# Validação (URL, IDs, entrada do usuário)
# ---------------------------------------------------------------------------


class ValidationError(GundamIntelError):
    """Dado de entrada inválido (URL bloqueada, ID malformado, filtro inválido)."""
    pass


# ---------------------------------------------------------------------------
# Feeds / Rede
# ---------------------------------------------------------------------------


class FeedError(GundamIntelError):
    """Erro ao buscar ou processar um feed (timeout, status 4xx/5xx, XML inválido)."""
    pass
