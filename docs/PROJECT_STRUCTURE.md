# 🗂️ Estrutura do projeto

← [Voltar ao índice da documentação](README.md)

---

```
gundam-news-discord/
├── 📄 main.py              # Bot principal
├── 📄 settings.py          # Carrega configurações do .env
├── 📄 sources.json         # RSS, YouTube e sites oficiais (HTML)
├── 📄 requirements.txt     # Dependências Python
├── 📄 Dockerfile           # Imagem Docker do bot
├── 📄 docker-compose.yml   # Orquestração (volumes: config, history, state)
├── 📄 .env.example         # Exemplo de configuração
├── 📄 .gitignore           # Arquivos ignorados pelo Git
├── 🖼️ icon.png            # Ícone do bot
├── 📁 .github/             # Workflows do GitHub Actions
├── 📁 bot/                 # Lógica do bot (Cogs, Views)
│   ├── cogs/               # Comandos (admin, dashboard, status, info)
│   └── views/              # Views persistentes (FilterDashboard)
├── 📁 core/                # Core do sistema
│   ├── scanner.py          # Scanner de feeds
│   ├── filters.py          # Sistema de filtros
│   ├── html_monitor.py     # Monitor HTML
│   └── stats.py            # Estatísticas
├── 📁 docs/                # Documentação (comandos, tutorial, arquitetura)
├── 📁 tests/               # Testes automatizados
├── 📁 translations/        # Internacionalização (i18n)
├── 📁 utils/               # Utilitários
│   ├── logger.py           # Logging (console UTF-8 no Windows, arquivo rotativo)
│   ├── security.py         # Validação e segurança
│   ├── storage.py          # Armazenamento JSON
│   ├── translator.py       # Tradução
│   └── cache.py            # Cache HTTP
├── 📁 web/                 # Web Dashboard
│   ├── server.py           # Servidor aiohttp
│   └── templates/          # Templates HTML
└── 📄 README.md            # Visão geral do repositório
```

> **Nota:** Os arquivos `config.json`, `history.json` e `state.json` são gerados automaticamente em runtime e estão no `.gitignore`.

---

**Relacionado:** [Arquitetura](ARCHITECTURE.md)
