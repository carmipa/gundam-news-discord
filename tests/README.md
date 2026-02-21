# Testes — Gundam News Discord (Python)

**Atenção:** Os casos de teste (idempotência, persistência, concorrência, autorização, timeout, contexto mockado) foram inspirados em checklists pensados para **Java 25** (Spring, JDA, etc.). Aqui estão implementados em **Python** para este projeto:

- **Stack:** Python 3, discord.py, aiohttp, JSON (arquivos), pytest + pytest-asyncio.
- **Não há:** Spring Boot, JDA, RestTemplate, Jackson, parallelStream — tudo adaptado para Python/discord.py.

Rodar todos os testes:

```bash
pytest tests/ -v
```
