# Logs e exceções

## Exceções personalizadas

Todas as exceções do domínio do bot herdam de `GundamIntelError` (`utils/exceptions.py`).

| Exceção | Quando usar | Herda de |
|--------|-------------|----------|
| **GundamIntelError** | Base; capture para tratar qualquer erro do bot | Exception |
| **ConfigError** | Config inválida ou ausente (ex.: guild sem channel_id) | GundamIntelError |
| **StorageError** | Erro ao ler/escrever config, state, history | GundamIntelError |
| **InvalidCleanTypeError** | Tipo de limpeza do `/clean_state` inválido | ValueError, GundamIntelError |
| **ValidationError** | URL bloqueada, ID malformado, filtro inválido | GundamIntelError |
| **FeedError** | Timeout, status 4xx/5xx ou XML inválido ao buscar feed | GundamIntelError |

- **Por que personalizadas?** Mensagens claras para o usuário e para logs; possibilidade de `except GundamIntelError` sem capturar erros de libs (discord, aiohttp).
- **InvalidCleanTypeError** herda de `ValueError` para compatibilidade com código que já trata `ValueError`.

## Níveis de log

O logger usado é `MaftyIntel` (configurado em `utils/logger.py`).

| Nível | Uso |
|-------|-----|
| **DEBUG** | Fluxo interno (cache hit, item bloqueado por filtro, parse de data). |
| **INFO** | Varredura iniciada/concluída, backup criado, canal configurado, anúncio enviado. |
| **WARNING** | Situação recuperável: arquivo não existe (usando padrão), timeout em um feed, interação expirada, canal não encontrado. |
| **ERROR** | Falha que exige atenção: JSON corrompido, permissão negada, falha ao enviar mensagem, erro ao criar backup. |
| **exception()** | Erro inesperado com traceback completo (ex.: no loop de varredura, ao carregar cogs). |

- Logs são sanitizados por `SecurityFilter` (tokens/senhas mascarados).
- Arquivo: `logs/bot.log` (rotação 5 MB, 3 backups).
