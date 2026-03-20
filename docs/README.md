# Documentação — Gundam News Bot

Índice central: cada tópico em **arquivo próprio**. Links absolutos (`blob/main`) para o GitHub abrirem sempre o ficheiro certo.

**Raiz do projeto:** [README.md na raiz](https://github.com/carmipa/gundam-news-discord/blob/main/README.md)

---

## Início rápido

| Documento | Descrição |
|-----------|-----------|
| [INSTALLATION.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/INSTALLATION.md) | Pré-requisitos, venv, pip, Docker |
| [CONFIGURATION.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/CONFIGURATION.md) | `.env`, `sources.json` |
| [DEPLOY.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/DEPLOY.md) | Docker, systemd, produção |

---

## Arquitetura e operação

| Documento | Descrição |
|-----------|-----------|
| [ARCHITECTURE.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/ARCHITECTURE.md) | Fluxo de dados, componentes, diagramas Mermaid |
| [DASHBOARD_AND_FILTERS.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/DASHBOARD_AND_FILTERS.md) | Painel de filtros e pipeline de filtragem |
| [PROJECT_STRUCTURE.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/PROJECT_STRUCTURE.md) | Árvore de pastas do repositório |
| [MONITORING_AND_LOGS.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/MONITORING_AND_LOGS.md) | Logs, `tail`, Docker |
| [LOGGING_AND_EXCEPTIONS.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/LOGGING_AND_EXCEPTIONS.md) | Exceções do domínio e níveis de log |

---

## Comandos e tutoriais

| Documento | Descrição |
|-----------|-----------|
| [COMMANDS_LIST.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/COMMANDS_LIST.md) | Tabela: o que cada comando faz |
| [COMMANDS_REFERENCE.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/COMMANDS_REFERENCE.md) | Sintaxe, parâmetros, exemplos |
| [TUTORIAL.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/TUTORIAL.md) | Tutorial geral dos comandos |
| [TUTORIAL_CLEAN_STATE.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/TUTORIAL_CLEAN_STATE.md) | `/clean_state` passo a passo |

---

## Segurança e governança

| Documento | Descrição |
|-----------|-----------|
| [OVERVIEW.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/OVERVIEW.md) | Visão GRC (governança, riscos, controle) |
| [SOURCES_VERIFICATION.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/SOURCES_VERIFICATION.md) | Testar e revisar fontes RSS/HTML |

---

## Manutenção e problemas

| Documento | Descrição |
|-----------|-----------|
| [TROUBLESHOOTING.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/TROUBLESHOOTING.md) | Erros comuns e soluções |
| [CHANGELOG.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/CHANGELOG.md) | Histórico de versões |

---

## Outros idiomas (README)

| Idioma | Arquivo |
|--------|---------|
| English | [README_EN.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README_EN.md) |
| Español | [README_ES.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README_ES.md) |
| Italiano | [README_IT.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README_IT.md) |
| 日本語 | [README_JP.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README_JP.md) |

---

## Análises (`analysis/`)

| Documento | Descrição |
|-----------|-----------|
| [SECURITY_GRC_ANALYSIS.md](https://github.com/carmipa/gundam-news-discord/blob/main/analysis/SECURITY_GRC_ANALYSIS.md) | Análise de segurança e GRC |
| [LOGGING_IMPROVEMENTS.md](https://github.com/carmipa/gundam-news-discord/blob/main/analysis/LOGGING_IMPROVEMENTS.md) | Melhorias de logging |

---

*Diagramas Mermaid: evitar rótulos com aspas simples que quebrem o parser do GitHub.*
