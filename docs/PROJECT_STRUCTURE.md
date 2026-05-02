# Estrutura do projeto

[Voltar ao índice da documentação](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README.md)

---

```
gundam-news-discord/
├── main.py              # Bot principal
├── settings.py          # Carrega configuracoes do .env
├── sources.json         # RSS, YouTube e sites oficiais (HTML)
├── requirements.txt     # Dependencias Python
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── icon.png
├── .github/             # Workflows GitHub Actions
├── bot/                 # Cogs, Views
│   ├── cogs/
│   └── views/
├── core/
│   ├── scanner/           # Pacote do scanner (substitui o monolito scanner.py)
│   │   ├── __init__.py
│   │   ├── engine.py      # Orquestração do ciclo de varredura
│   │   ├── fetcher.py     # HTTP + feedparser (RSS/Atom/YouTube)
│   │   ├── processor.py   # Dedup, datas, sanitização de links
│   │   └── notifier.py    # Embeds Discord + OG opcional
│   ├── filters.py
│   ├── html_monitor.py
│   └── stats.py
├── docs/
├── tests/
├── translations/
├── utils/
│   ├── logger.py
│   ├── security.py
│   ├── storage.py
│   ├── translator.py
│   └── cache.py
└── web/
    ├── server.py
    └── templates/
```

> **Nota:** `config.json`, `history.json` e `state.json` sao gerados em runtime e estao no `.gitignore`.

---

**Relacionado:** [Arquitetura](https://github.com/carmipa/gundam-news-discord/blob/main/docs/ARCHITECTURE.md)
