# 📊 Monitoramento e logs

← [Voltar ao índice da documentação](README.md)

---

## Sistema de logging

O bot possui um sistema de logging profissional com:

- 🎨 **Cores no Console** — Diferentes cores para cada nível de log
- 📝 **Traceback Colorido** — Stack traces formatados com cores
- 🔒 **Sanitização Automática** — Tokens e senhas são mascarados
- 📁 **Rotação de Arquivos** — Logs rotacionam automaticamente (5MB, 3 backups)
- 📊 **Níveis Configuráveis** — DEBUG, INFO, WARNING, ERROR, CRITICAL

### Exemplo de logs

```
2026-02-13 10:30:45 - [INFO] ℹ️ Bot conectado como: Mafty#1234 (ID: 123456789)
2026-02-13 10:30:46 - [INFO] ℹ️ 📊 Servidores conectados: 3
2026-02-13 10:30:47 - [INFO] ℹ️ 🔄 Agendador de tarefas iniciado (12h).
2026-02-13 10:31:15 - [INFO] ℹ️ 🔎 Iniciando varredura de inteligência... (trigger=loop)
2026-02-13 10:31:20 - [WARNING] ⚠️ 🔒 URL bloqueada por segurança: http://localhost/test - IP privado/local não permitido
2026-02-13 10:31:25 - [INFO] ℹ️ ✅ Varredura concluída. (enviadas=5, cache_hits=12/15, trigger=loop)
```

### Ver logs

```bash
# Docker
docker-compose logs -f

# Local
tail -f logs/bot.log

# Filtrar por nível
grep ERROR logs/bot.log
grep WARNING logs/bot.log
```

---

**Documentação técnica:** [LOGGING_AND_EXCEPTIONS.md](LOGGING_AND_EXCEPTIONS.md) · [Melhorias de logging](../analysis/LOGGING_IMPROVEMENTS.md)
