# Monitoramento e logs

[Voltar ao índice da documentação](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README.md)

---

## Sistema de logging

O bot possui logging com:

- **Cores no Console** — Diferentes cores para cada nivel de log
- **Traceback** — Stack traces formatados
- **Sanitizacao Automatica** — Tokens e senhas sao mascarados
- **Rotacao de Arquivos** — Logs rotacionam automaticamente (5MB, 3 backups)
- **Niveis Configuraveis** — DEBUG, INFO, WARNING, ERROR, CRITICAL

### Exemplo de logs

```
2026-02-13 10:30:45 - [INFO] Bot conectado como: Mafty#1234 (ID: 123456789)
2026-02-13 10:30:46 - [INFO] Servidores conectados: 3
2026-02-13 10:30:47 - [INFO] Agendador de tarefas iniciado (12h).
2026-02-13 10:31:15 - [INFO] Iniciando varredura de inteligencia... (trigger=loop)
2026-02-13 10:31:20 - [WARNING] URL bloqueada por seguranca: http://localhost/test
2026-02-13 10:31:25 - [INFO] Varredura concluida. (enviadas=5, cache_hits=12/15)
```

### Ver logs

```bash
# Docker
docker-compose logs -f

# Local
tail -f logs/bot.log

grep ERROR logs/bot.log
grep WARNING logs/bot.log
```

---

**Documentação técnica:** [LOGGING_AND_EXCEPTIONS.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/LOGGING_AND_EXCEPTIONS.md) · [Melhorias de logging](https://github.com/carmipa/gundam-news-discord/blob/main/analysis/LOGGING_IMPROVEMENTS.md)
