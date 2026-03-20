# 🧱 Arquitetura — Gundam News Bot

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](../readme.md)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?logo=discord&logoColor=white)](../readme.md)
[![Arquitetura](https://img.shields.io/badge/Arquitetura-Modular-green)](../readme.md)

Visão geral da arquitetura do **Mafty Intelligence System**: fluxo de dados, componentes e segurança. Diagramas Mermaid compatíveis com o renderizador do GitHub (sem aspas simples em rótulos que quebrem o parser).

---

## 📋 Índice

- [Visão macro](#-visão-macro---fluxo-completo-de-dados)
- [Arquivos de estado](#-arquivos-de-estado)
- [Componentes principais](#-componentes-principais)
- [Fluxo de segurança](#-fluxo-de-segurança)
- [Ciclo de vida do bot](#-ciclo-de-vida-do-bot)
- [Deploy e execução](#-deploy-e-execução)

---

## 📐 Visão macro — Fluxo completo de dados

```mermaid
flowchart TB
    subgraph Entrada["📥 Entrada"]
        A["sources.json<br/>Feeds RSS/Atom/YouTube"]
        A2["sources.json<br/>Sites Oficiais HTML"]
    end

    subgraph Processamento["🔍 Processamento"]
        B["Scanner<br/>core/scanner.py"]
        J["HTML Monitor<br/>core/html_monitor.py"]
        C["Normalização<br/>URL + entries"]
        D["Filtros Mafty<br/>core/filters.py"]
        E["Tradutor<br/>utils/translator.py"]
        S["Validação Segurança<br/>utils/security.py"]
    end

    subgraph Armazenamento["💾 Armazenamento"]
        H["config.json<br/>canal + filtros + idioma"]
        I["history.json<br/>links enviados"]
        K["state.json<br/>dedup + cache + hashes"]
    end

    subgraph Saida["📤 Saída"]
        F["Postagem Discord<br/>Canal por guild"]
        W["Web Dashboard<br/>:8080"]
    end

    A -->|"🔒 Validação"| S
    S -->|"✅ Aprovado"| B
    A2 --> J
    B --> C
    J -->|"Mudança detectada"| D
    C --> D
    D -->|"Aprovado"| E
    D -->|"Reprovado"| G["❌ Ignorado"]
    E --> F

    H --> D
    H --> E
    I --> D
    F --> I
    F --> K
    J --> K

    W -.->|"Monitora"| H
    W -.->|"Monitora"| K
```

| Símbolo | Significado |
|--------|-------------|
| 📥 | Entrada (feeds e sites) |
| 🔍 | Processamento (scanner, filtros, tradutor) |
| 💾 | Armazenamento (JSON em disco) |
| 📤 | Saída (Discord + Web) |
| 🔒 | Validação de segurança (anti-SSRF) |

---

## 📁 Arquivos de estado

| Arquivo | Função |
|---------|--------|
| `config.json` | Canal por guild, filtros (Gunpla, Filmes, etc.) e idioma. |
| `sources.json` | Lista de feeds (RSS/Atom/YouTube) e sites oficiais para o HTML Watcher. |
| `state.json` | Dedup por feed, cache HTTP (ETags), hashes HTML, metadados de limpeza. |
| `history.json` | Lista global de links já enviados (fallback de deduplicação). |
| `backups/` | Backups de `state.json` gerados pelo `/clean_state`. |
| `logs/bot.log` | Log rotativo da aplicação. |

```mermaid
flowchart LR
    subgraph disco["Disco"]
        C["config.json"]
        S["state.json"]
        H["history.json"]
        B["backups"]
        L["logs"]
    end

    C -->|leitura escrita| Bot["Bot"]
    S --> Bot
    H --> Bot
    Bot -->|backup clean_state| B
    Bot -->|gravacao| L
```

---

## 🧩 Componentes principais

| Componente | Caminho | Responsabilidade |
|------------|---------|------------------|
| **Main** | `main.py` | Inicialização do bot, eventos, sync de comandos, carregamento de cogs. |
| **Scanner** | `core/scanner.py` | Loop de varredura de feeds, dedup, cache HTTP, postagem no Discord. |
| **HTML Monitor** | `core/html_monitor.py` | Monitoramento de sites oficiais (hash de conteúdo). |
| **Filtros** | `core/filters.py` | Regras de filtragem (GUNDAM_CORE, blacklist, categorias). |
| **Admin Cog** | `bot/cogs/admin.py` | Comandos `/forcecheck` e `/clean_state`. |
| **Dashboard Cog** | `bot/cogs/dashboard.py` | Comandos `/dashboard` e `/set_canal`. |
| **Info Cog** | `bot/cogs/info.py` | Comandos `/help`, `/about`, `/ping`, `/feeds`, `/setlang`. |
| **Status Cog** | `bot/cogs/status.py` | Comandos `/status` e `/now`. |
| **Storage** | `utils/storage.py` | Leitura/gravação JSON, backup, `clean_state` em memória. |
| **Security** | `utils/security.py` | Validação de URLs (anti-SSRF), sanitização de logs. |
| **Web** | `web/server.py` | Dashboard web (aiohttp), autenticação e rate limiting. |

---

## 🔒 Fluxo de segurança

```mermaid
flowchart LR
    subgraph HTTP["HTTP"]
        A["URL de feed"] --> B["utils/security.py"]
        B -->|valida| C["Request HTTP"]
        B -->|bloqueia| D["Log seguranca"]
    end

    subgraph Web["Servidor web"]
        E["Request"] --> F["Rate limiting"]
        F --> G["Token opcional"]
        G --> H["Dashboard"]
    end

    subgraph Logs["Logs"]
        I["Evento"] --> J["Sanitizacao"]
        J --> K["Arquivo e console"]
    end
```

- **URLs:** validadas antes de qualquer requisição (anti-SSRF).
- **Web:** rate limiting por IP e token opcional.
- **Logs:** sanitização de dados sensíveis antes de gravar/exibir.

---

## 🔄 Ciclo de vida do bot

```mermaid
stateDiagram-v2
    [*] --> Conectando
    Conectando --> Online: Token OK
    Online --> SyncGuild: on_ready
    SyncGuild --> ViewsPersistentes: add_view por guild
    ViewsPersistentes --> ScannerAtivo: inicia loop
    ScannerAtivo --> ScannerAtivo: varredura
    ScannerAtivo --> Online: erro tratado
```

1. **Conectando** — Validação do token.
2. **Online** — Conectado ao Discord.
3. **SyncGuild** — Sincronização dos comandos slash.
4. **ViewsPersistentes** — Restauração dos botões do dashboard.
5. **ScannerAtivo** — Loop de varredura em execução.

---

## 🐳 Deploy e execução

```mermaid
flowchart TB
    subgraph Opcoes["Execucao"]
        L["python main.py"]
        D["docker-compose up"]
        S["systemd service"]
    end

    subgraph Ambiente["Ambiente"]
        L --> Env[".env DISCORD_TOKEN e demais"]
        D --> Env
        S --> Env
    end

    Env --> Bot["Bot scanner e web"]
```

- **Local:** `python main.py` (desenvolvimento).
- **Produção:** Docker (recomendado) ou systemd; variáveis em `.env`.

Para detalhes de instalação e configuração, veja o [readme principal](../readme.md).
