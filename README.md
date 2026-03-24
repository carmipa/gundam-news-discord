# Gundam News Bot — Mafty Intelligence System

<p align="center">
  <img alt="Gundam News Bot" src="./icon.png" width="300">
</p>

<p align="center">
  <a href="https://github.com/carmipa/gundam-news-discord/actions/workflows/python-app.yml">
    <img src="https://github.com/carmipa/gundam-news-discord/actions/workflows/python-app.yml/badge.svg" alt="CI Status" />
  </a>
  <img src="https://img.shields.io/badge/Discord-Bot-5865F2?logo=discord&logoColor=white" alt="Discord Bot" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/discord.py-2.x-00B0F4?logo=python&logoColor=white" alt="discord.py 2.x" />
  <img src="https://img.shields.io/badge/Status-Produ%C3%A7%C3%A3o-success" alt="Status" />
  <img src="https://img.shields.io/badge/Security-Hardened-brightgreen" alt="Security" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License MIT" />
</p>

<p align="center">
  <b>Monitoramento inteligente de feeds RSS/Atom/YouTube sobre o universo Gundam</b><br>
  Filtragem cirúrgica • Dashboard interativo • Postagem automática no Discord<br>
  <i>Segurança aprimorada • Logs detalhados • Proteção anti-SSRF</i>
</p>

---

<p align="center">
  Link de download do bot: https://discord.com/discovery/applications/1456658169769234525
</p>

---

<p align="center">
  <a href="https://www.youtube.com/watch?v=rZGLuvKVZ9s">
    <img src="https://img.youtube.com/vi/rZGLuvKVZ9s/mqdefault.jpg" alt="Reproduzir Vídeo 1" width="400" />
    <br>
    <img src="https://img.shields.io/badge/▶_Reproduzir_Vídeo-Clique_para_Assistir-red?style=flat-square" alt="Play" />
  </a>
</p>

---

<p align="center">
  <a href="https://www.youtube.com/watch?v=FDLcXdPmolA">
    <img src="https://img.youtube.com/vi/FDLcXdPmolA/mqdefault.jpg" alt="Reproduzir Vídeo 2" width="400" />
    <br>
    <img src="https://img.shields.io/badge/▶_Reproduzir_Vídeo-Clique_para_Assistir-red?style=flat-square" alt="Play" />
  </a>
</p>

---

## Índice

Os links abaixo apontam para arquivos na branch **`main`** no GitHub (evita ambiguidade com caminhos relativos).

| Seção | Onde ler |
|-------|----------|
| **Documentação completa (índice com links)** | **[docs/README.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README.md)** |
| Funcionalidades | [abaixo](#funcionalidades) |
| Segurança e GRC | [abaixo](#segurança-e-grc) |
| Arquitetura (diagramas) | [docs/ARCHITECTURE.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/ARCHITECTURE.md) |
| Instalação | [docs/INSTALLATION.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/INSTALLATION.md) |
| Configuração | [docs/CONFIGURATION.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/CONFIGURATION.md) |
| Comandos | [COMMANDS_LIST](https://github.com/carmipa/gundam-news-discord/blob/main/docs/COMMANDS_LIST.md) · [COMMANDS_REFERENCE](https://github.com/carmipa/gundam-news-discord/blob/main/docs/COMMANDS_REFERENCE.md) |
| Dashboard e filtros | [docs/DASHBOARD_AND_FILTERS.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/DASHBOARD_AND_FILTERS.md) |
| Deploy | [docs/DEPLOY.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/DEPLOY.md) |
| Logs e monitoramento | [docs/MONITORING_AND_LOGS.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/MONITORING_AND_LOGS.md) |
| Estrutura de pastas | [docs/PROJECT_STRUCTURE.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/PROJECT_STRUCTURE.md) |
| Problemas comuns | [docs/TROUBLESHOOTING.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/TROUBLESHOOTING.md) |

---

## Funcionalidades

| Feature | Descrição |
|---------|-----------|
| **Scanner periódico** | Varredura de feeds RSS/Atom/YouTube (configurável via `LOOP_MINUTES`) |
| **HTML Watcher** | Sites oficiais sem RSS (ex.: Gundam Official) |
| **Dashboard persistente** | Painel com botões após restart |
| **Filtros por categoria** | Gunpla, Filmes, Games, Música, Fashion + TUDO |
| **Anti-spam / blacklist** | Bloqueia conteúdo não relacionado |
| **Deduplicação** | `history.json` |
| **Multi-guild** | Config por servidor |
| **Multi-idioma** | EN, PT, ES, IT, JA (`/setlang`) |
| **Web dashboard** | `http://host:8080` |
| **Segurança** | Anti-SSRF, rate limit, auth opcional no web |

---

## Segurança e GRC

Resumo: validação de URLs (anti-SSRF), rate limiting, sanitização de logs, headers HTTP seguros, SSL com certifi.

- **Visão GRC:** [docs/OVERVIEW.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/OVERVIEW.md)
- **Análise:** [analysis/SECURITY_GRC_ANALYSIS.md](https://github.com/carmipa/gundam-news-discord/blob/main/analysis/SECURITY_GRC_ANALYSIS.md)

---

## Arquitetura

Diagramas Mermaid (fluxo de dados, segurança, componentes): **[docs/ARCHITECTURE.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/ARCHITECTURE.md)**

---

## Instalação rápida

```bash
git clone https://github.com/carmipa/gundam-news-discord.git
cd gundam-news-discord
python -m venv .venv && .venv\Scripts\activate   # Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edite DISCORD_TOKEN
```

Ou com Docker: **[docs/INSTALLATION.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/INSTALLATION.md)** e **[docs/DEPLOY.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/DEPLOY.md)**.

---

## Documentação

**Índice principal (lista com links para cada arquivo):** **[docs/README.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README.md)**

---

## Contribuindo

1. Fork → branch `feature/...` → commit → Pull Request.

---

## Licença

**MIT** — veja [LICENSE](https://github.com/carmipa/gundam-news-discord/blob/main/LICENSE).

---

## Autor

**Paulo André Carminati** — [![GitHub](https://img.shields.io/badge/GitHub-carmipa-181717?logo=github)](https://github.com/carmipa)

---

<p align="center">
  <i>Mafty Intelligence System</i><br>
  <b>Versão 2.1</b>
</p>
