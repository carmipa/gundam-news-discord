# 🛰️ Gundam News Bot — Mafty Intelligence System

<p align="center">
  <img alt="Games Bot" src="./icon.png" width="300">
</p>

<p align="center">
  <a href="https://github.com/carmipa/gundam-news-discord/actions/workflows/python-app.yml">
    <img src="https://github.com/carmipa/gundam-news-discord/actions/workflows/python-app.yml/badge.svg" alt="CI Status" />
  </a>
  <img src="https://img.shields.io/badge/Discord-Bot-5865F2?logo=discord&logoColor=white" alt="Discord Bot" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/discord.py-2.x-00B0F4?logo=python&logoColor=white" alt="discord.py 2.x" />
  <img src="https://img.shields.io/badge/Status-Produção-success" alt="Status" />
  <img src="https://img.shields.io/badge/Security-Hardened-brightgreen" alt="Security" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License MIT" />
</p>

<p align="center">
  <b>Monitoramento inteligente de feeds RSS/Atom/YouTube sobre o universo Gundam</b><br>
  Filtragem cirúrgica • Dashboard interativo • Postagem automática no Discord<br>
  <i>🔒 Segurança aprimorada • 📊 Logs detalhados • 🛡️ Proteção anti-SSRF</i>
</p>

---

## 📋 Índice

- [✨ Funcionalidades](#-funcionalidades)
- [🔒 Segurança e GRC](#-segurança-e-grc)
- [🧱 Arquitetura](#-arquitetura)
- [🚀 Instalação](#-instalação)
- [⚙️ Configuração](#️-configuração)
- [🧰 Comandos](#-comandos)
- [📚 Documentação](#-documentação)
- [🎛️ Dashboard](#️-dashboard)
- [🧠 Sistema de Filtros](#-sistema-de-filtros)
- [🖥️ Deploy](#️-deploy)
- [📊 Monitoramento e Logs](#-monitoramento-e-logs)
- [🧩 Troubleshooting](#-troubleshooting)
- [📜 Licença](#-licença)

---

## ✨ Funcionalidades

| Feature | Descrição |
|---------|-----------|
| 📡 **Scanner Periódico** | Varredura de feeds RSS/Atom/YouTube a cada 12h (configurável via LOOP_MINUTES) |
| 🕵️ **HTML Watcher** | Monitora sites oficiais sem RSS (ex: Gundam Official) detectando mudanças visuais |
| 🎛️ **Dashboard Persistente** | Painel interativo com botões que funciona mesmo após restart |
| 🎯 **Filtros por Categoria** | Gunpla, Filmes, Games, Música, Fashion + opção "TUDO" |
| 🛡️ **Anti-Spam** | Blacklist para bloquear animes/jogos não relacionados a Gundam |
| 🔄 **Deduplicação** | Nunca repete notícias (histórico em `history.json`) |
| 🌐 **Multi-Guild** | Configuração independente por servidor Discord |
| 📝 **Logs Coloridos** | Sistema de logging avançado com cores e traceback detalhado |
| 🎨 **Embeds Ricos** | Notícias com visual premium (cor Gundam, thumbnails, timestamps) |
| 🎞️ **Player Nativo** | Vídeos do YouTube/Twitch tocam direto no chat (sem abrir navegador) |
| 🌍 **Multi-Idioma** | Suporte a EN, PT, ES, IT, JA (detecção automática + `/setlang`) |
| 🖥️ **Web Dashboard** | Painel visual em <http://host:8080> com status em tempo real |
| 🧹 **Auto-Cleanup** | Limpeza automática de cache a cada 7 dias para performance (Zero manutenção) |
| ❄️ **Cold Start** | Posta imediatamente as 3 notícias mais recentes de novas fontes (ignora travas) |
| 🔐 **SSL Seguro** | Conexões verificadas com certifi (proteção contra MITM) |
| 🔒 **Validação de URLs** | Proteção anti-SSRF (Server-Side Request Forgery) |
| 🛡️ **Rate Limiting** | Proteção contra abuso de comandos e servidor web |
| 🔐 **Autenticação Web** | Servidor web protegido com token (opcional) |

---

## 🔒 Segurança e GRC

### Melhorias de Segurança Implementadas

| Recurso | Status | Descrição |
|---------|--------|-----------|
| 🔒 **Validação de URLs** | ✅ | Bloqueia IPs privados e domínios locais (anti-SSRF) |
| 🛡️ **Rate Limiting** | ✅ | Limite de requisições por IP no servidor web |
| 🔐 **Autenticação Web** | ✅ | Token opcional para acesso ao dashboard web |
| 📝 **Sanitização de Logs** | ✅ | Informações sensíveis são mascaradas automaticamente |
| 🔒 **Headers de Segurança** | ✅ | CSP, X-Frame-Options, X-Content-Type-Options |
| ✅ **Validação SSL** | ✅ | Certificados verificados com certifi |
| 🚫 **Tratamento de Erros** | ✅ | Exceções específicas com contexto detalhado |

### Análise de Segurança

📄 **Visão GRC (governança, riscos, controle):** [docs/OVERVIEW.md](docs/OVERVIEW.md) · **Análise de segurança:** [analysis/SECURITY_GRC_ANALYSIS.md](analysis/SECURITY_GRC_ANALYSIS.md)

**Principais melhorias:**
- ✅ Validação de URLs antes de fazer requisições HTTP
- ✅ Rate limiting em comandos críticos e servidor web
- ✅ Sanitização automática de logs (tokens, senhas)
- ✅ Tratamento específico de exceções com contexto
- ✅ Headers de segurança HTTP configurados

---

## 🧱 Arquitetura

> **Renderização no GitHub:** os diagramas usam [Mermaid](https://github.blog/2022-02-14-include-diagrams-markdown-files-github/) (GFM). Evitamos aspas simples dentro de rótulos e caracteres que quebram o parser.

### 1) Visão Macro — Fluxo Completo de Dados

```mermaid
flowchart TB
    subgraph ent["Entrada"]
        A["sources.json - RSS Atom YouTube"]
        A2["sources.json - sites HTML sem RSS"]
    end

    subgraph proc["Processamento"]
        B["Scanner core/scanner.py"]
        J["HTML Monitor core/html_monitor.py"]
        C["Normalizacao URL e entries"]
        D["Filtros Mafty core/filters.py"]
        E["Tradutor utils/translator.py"]
        S["Validacao utils/security.py"]
    end

    subgraph stor["Armazenamento"]
        H["config.json canal filtros idioma"]
        I["history.json dedup"]
        K["state.json cache e hashes HTML"]
    end

    subgraph out["Saida"]
        F["Postagem Discord por guild"]
        W["Web Dashboard aiohttp"]
    end

    A -->|validacao anti-SSRF| S
    S -->|aprovado| B
    A2 --> J
    B --> C
    J -->|mudanca| D
    C --> D
    D -->|aprovado| E
    D -->|reprovado| G["Ignorado"]
    E --> F

    H --> D
    H --> E
    I --> D
    F --> I
    F --> K
    J --> K

    W -.->|monitora| H
    W -.->|monitora| I
```

> **Legenda:**
>
> - `sources.json` — Lista de feeds monitorados
> - `config.json` — Configuração de canal e filtros por servidor
> - `history.json` — Links já enviados (deduplicação)
> - `state.json` — Estado de cache HTTP e hashes HTML
> - 🔒 **Validação de Segurança** — Anti-SSRF e validação de URLs

---

### 2) Fluxo do Comando `/set_canal` e `/dashboard`

```mermaid
sequenceDiagram
    participant Admin
    participant Bot
    participant Disk as config.json
    participant Security as utils/security

    Note over Admin,Security: Configuracao de canal
    Admin->>Bot: /set_canal canal
    Bot->>Security: valida permissoes do bot
    Security-->>Bot: permissoes OK
    Bot->>Disk: salva channel_id da guild
    Bot-->>Admin: canal configurado

    Note over Admin,Security: Filtros via dashboard
    Admin->>Bot: /dashboard
    Bot->>Disk: salva channel_id canal atual
    Bot-->>Admin: painel com botoes
    Admin->>Bot: clica filtros categoria
    Bot->>Disk: atualiza filtros da guild
    Bot-->>Admin: botoes atualizados

    Note over Bot: Apos restart
    Bot->>Disk: le config.json
    Bot-->>Admin: views persistentes registradas
    Admin->>Bot: botoes antigos
    Bot-->>Admin: interacao valida
```

> **Destaques:**
>
> - `/set_canal` — Comando dedicado para configurar canal rapidamente
> - `/dashboard` — Painel completo com filtros e configurações
> - Botões funcionam **mesmo após restart** do bot
> - Configuração é **salva em disco** automaticamente

---

### 3) Estados Principais do Bot

```mermaid
stateDiagram-v2
    [*] --> Conectando
    Conectando --> Online: Token OK
    Online --> SyncGuild: on_ready
    SyncGuild --> ViewsPersistentes: add_view por guild
    ViewsPersistentes --> ScannerAtivo: inicia loop
    ScannerAtivo --> ScannerAtivo: varredura feeds
    ScannerAtivo --> Online: erro tratado no feed
    note right of ScannerAtivo
        Validacao URL anti-SSRF
        Logs e rate limit web
    end note
```

> **Ciclo de vida:**
>
> 1. **Conectando** — Validando token
> 2. **Online** — Conectado ao Discord
> 3. **SyncGuild** — Sincronizando comandos slash
> 4. **ViewsPersistentes** — Restaurando botões do dashboard
> 5. **ScannerAtivo** — Loop de varredura rodando com segurança

---

### 4) Arquitetura de Segurança

```mermaid
flowchart LR
    subgraph http["Requisicoes HTTP"]
        A["URL de feed"] --> B["utils/security.py"]
        B -->|valida| C["Request HTTP"]
        B -->|bloqueia| D["Log seguranca"]
    end

    subgraph web["Servidor web"]
        E["Request"] --> F["Rate limiting"]
        F --> G["Auth token opcional"]
        G --> H["Dashboard"]
    end

    subgraph logsys["Logs"]
        I["Evento"] --> J["Sanitizacao"]
        J --> K["Formatacao e traceback"]
        K --> L["Arquivo e console"]
    end
```

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.10 ou superior
- Token de bot do Discord ([Portal de Desenvolvedores](https://discord.com/developers/applications))
- Git (para clonar o repositório)

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/carmipa/gundam-news-discord.git
cd gundam-news-discord

# 2. Crie ambiente virtual
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 3. Instale dependências
pip install -r requirements.txt

# 4. Configure o ambiente
cp .env.example .env
# Edite o .env com seu token
```

### 🐳 Instalação com Docker (Recomendado)

```bash
# Clone o repositório
git clone https://github.com/carmipa/gundam-news-discord.git
cd gundam-news-discord

# Configure .env
cp .env.example .env
nano .env  # Adicione seu DISCORD_TOKEN

# Inicie com Docker Compose
docker-compose up -d

# Ver logs
docker-compose logs -f
```

📖 **Guia completo de deploy:** Veja [DEPLOY.md](DEPLOY.md) para instruções detalhadas.

---

## ⚙️ Configuração

### Variáveis de Ambiente (`.env`)

```env
# ⚠️ OBRIGATÓRIO
DISCORD_TOKEN=seu_token_aqui

# ⚙️ OPCIONAL
COMMAND_PREFIX=!
LOOP_MINUTES=720
LOG_LEVEL=INFO  # Use DEBUG para logs detalhados
HTTP_TIMEOUT=10  # Timeout HTTP em segundos (feeds e sites oficiais)

# 🔒 Segurança do Servidor Web (Opcional)
WEB_AUTH_TOKEN=seu_token_secreto_aqui  # Recomendado para produção
WEB_HOST=127.0.0.1  # 127.0.0.1 = apenas localhost, 0.0.0.0 = todos os IPs
WEB_PORT=8080
```

> **🔒 Segurança:** Configure `WEB_AUTH_TOKEN` em produção para proteger o dashboard web!

### Fontes de Feeds (`sources.json`)

O bot aceita múltiplos formatos:

<details>
<summary><b>📁 Formato com categorias (recomendado)</b></summary>

```json
{
  "rss_feeds": [
    "https://www.animenewsnetwork.com/news/rss.xml",
    "https://gundamnews.org/feed"
  ],
  "youtube_feeds": [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCejtUitnpnf8Be-v5NuDSLw"
  ],
  "official_sites_reference_(not_rss)": [
    "https://gundam-official.com/",
    "https://en.gundam-official.com/news"
  ]
}
```

</details>

<details>
<summary><b>📁 Formato lista simples</b></summary>

```json
[
  "https://www.animenewsnetwork.com/news/rss.xml",
  "https://gundamnews.org/feed"
]
```

</details>

---

## 🧰 Comandos

### 🔧 Comandos Administrativos

| Comando | Descrição | Uso |
|---------|-----------|-----|
| `/set_canal` | Define o canal onde o bot enviará notícias | `/set_canal [canal:#noticias]` |
| `/dashboard` | Abre painel visual para configurar filtros | `/dashboard` |
| `/setlang` | Define o idioma do bot para o servidor | `/setlang idioma:pt_BR` |
| `/forcecheck` | Força uma varredura imediata de feeds | `/forcecheck` |
| `/clean_state` | Limpa partes do state.json (com backup automático) | `/clean_state tipo:dedup confirmar:sim` |
| `/server_log` | Exibe últimas linhas do log do servidor (botão Atualizar) | `/server_log [linhas:50]` |

### 📊 Comandos Informativos

| Comando | Descrição | Uso |
|---------|-----------|-----|
| `/status` | Mostra estatísticas do bot (Uptime, Scans, etc) | `/status` |
| `/feeds` | Lista todas as fontes monitoradas | `/feeds` |
| `/help` | Mostra manual de ajuda completo | `/help` |
| `/ping` | Verifica latência do bot | `/ping` |
| `/about` | Informações sobre o bot | `/about` |

> **🔒 Permissão:** Apenas administradores podem usar comandos administrativos.

| 📋 [**Lista de comandos**](docs/COMMANDS_LIST.md) | 📖 [**Referência completa**](docs/COMMANDS_REFERENCE.md) | 🧹 [**Tutorial /clean_state**](docs/TUTORIAL_CLEAN_STATE.md) |
|--------------------------------------------------|--------------------------------------------------------|-------------------------------------------------------------|

### 📖 Exemplos de Uso

#### Configuração

```bash
# Configurar canal rapidamente
/set_canal                    # Usa o canal atual
/set_canal canal:#noticias    # Define canal específico

# Abrir dashboard completo
/dashboard                    # Abre painel com filtros

# Definir idioma
/setlang idioma:pt_BR         # Português
/setlang idioma:en_US         # Inglês
```

#### Manutenção

```bash
# Limpar state.json (requer confirmação)
/clean_state tipo:dedup confirmar:não    # Ver estatísticas primeiro
/clean_state tipo:dedup confirmar:sim   # Executar limpeza

# Tipos disponíveis:
# - dedup: Histórico de links enviados
# - http_cache: Cache HTTP (ETags)
# - html_hashes: Hashes de monitoramento HTML
# - tudo: Limpa tudo (use com cuidado!)

# Ver log do servidor (últimas linhas)
/server_log                   # Últimas 50 linhas (padrão)
/server_log linhas:20         # Últimas 20 linhas (10–100)

# Forçar varredura manual
/forcecheck                   # Executa scan imediato
```

#### Informações

```bash
# Verificar status
/status                       # Estatísticas do bot

# Listar feeds
/feeds                        # Todas as fontes monitoradas

# Ajuda
/help                         # Manual completo
```

### ⚠️ Comando `/clean_state` - Detalhes

O comando `/clean_state` permite limpar partes específicas do `state.json`:

**Opções de Limpeza:**

| Tipo | O que Limpa | Impacto |
|------|-------------|---------|
| 🧹 **dedup** | Histórico de links enviados | ⚠️ Bot repostará notícias recentes |
| 🌐 **http_cache** | Cache HTTP (ETags, Last-Modified) | ℹ️ Mais requisições HTTP, sem repostagem |
| 🔍 **html_hashes** | Hashes de monitoramento HTML | ⚠️ Sites serão detectados como "mudados" |
| ⚠️ **tudo** | Limpa tudo (exceto metadados) | 🚨 Todos os efeitos acima combinados |

**Proteções:**
- ✅ Backup automático antes de limpar
- ✅ Confirmação dupla obrigatória
- ✅ Estatísticas antes/depois
- ✅ Logging de auditoria completo

**Exemplo Completo:**
```
1. /clean_state tipo:dedup confirmar:não
   → Mostra estatísticas e pede confirmação

2. /clean_state tipo:dedup confirmar:sim
   → Cria backup → Limpa → Mostra resultado
```

📘 **Tutorial passo a passo com diagramas:** [docs/TUTORIAL_CLEAN_STATE.md](docs/TUTORIAL_CLEAN_STATE.md)

---

## 📚 Documentação

| Documento | Conteúdo |
|-----------|----------|
| [docs/COMMANDS_LIST.md](docs/COMMANDS_LIST.md) | Lista rápida: o que cada comando faz |
| [docs/COMMANDS_REFERENCE.md](docs/COMMANDS_REFERENCE.md) | Referência completa: sintaxe, parâmetros, exemplos |
| [docs/TUTORIAL_CLEAN_STATE.md](docs/TUTORIAL_CLEAN_STATE.md) | Tutorial do comando de limpeza (diagramas e passo a passo) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitetura: fluxo de dados, componentes, segurança |
| [docs/TUTORIAL.md](docs/TUTORIAL.md) | Tutorial geral de todos os comandos |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Deploy com Docker e systemd |
| [analysis/SECURITY_GRC_ANALYSIS.md](analysis/SECURITY_GRC_ANALYSIS.md) | Análise de segurança e GRC |

---

## 🎛️ Dashboard

O painel interativo permite configurar quais categorias monitorar:

| Botão | Função |
|-------|--------|
| 🌟 **TUDO** | Liga/desliga todas as categorias |
| 🤖 **Gunpla** | Kits, P-Bandai, Ver.Ka, HG/MG/RG/PG |
| 🎬 **Filmes** | Anime, trailers, séries, Hathaway, SEED |
| 🎮 **Games** | Jogos Gundam (GBO2, Breaker, etc.) |
| 🎵 **Música** | OST, álbuns, openings/endings |
| 👕 **Fashion** | Roupas e merchandise |
| 🌐 **Idioma** | Seleciona idioma (🇺🇸 🇧🇷 🇪🇸 🇮🇹 🇯🇵) |
| 📌 **Ver filtros** | Mostra filtros ativos |
| 🔄 **Reset** | Limpa todos os filtros |

### Indicadores visuais

- 🟢 **Verde** = Filtro ativo
- ⚪ **Cinza** = Filtro inativo
- 🔵 **Azul** = Idioma selecionado

---

## 🧠 Sistema de Filtros

A filtragem **não é simples** — o bot usa um sistema em **camadas** para garantir precisão cirúrgica:

### Fluxo de Decisão

```mermaid
flowchart TD
    A["Noticia recebida"] --> B{"URL valida anti-SSRF?"}
    B -->|nao| C["Bloqueada log seguranca"]
    B -->|sim| D{"Blacklist?"}
    D -->|sim| C
    D -->|nao| E{"Termos GUNDAM_CORE?"}
    E -->|nao| C
    E -->|sim| F{"Filtro todos ativo?"}
    F -->|sim| G["Aprovada"]
    F -->|nao| H{"Categoria selecionada OK?"}
    H -->|sim| G
    H -->|nao| C
    G --> I{"Link ja em history.json?"}
    I -->|sim| C
    I -->|nao| J["Envia ao Discord"]
```

### ✅ Regras de Filtragem (ordem real)

| Etapa | Verificação | Ação |
|-------|-------------|------|
| 0️⃣ | **Validação de Segurança** | Verifica URL (anti-SSRF) |
| 1️⃣ | Junta `title + summary` | Concatena texto |
| 2️⃣ | Limpa HTML e normaliza | Remove tags, espaços extras |
| 3️⃣ | **BLACKLIST** | Se aparecer (ex: *One Piece*), bloqueia |
| 4️⃣ | **GUNDAM_CORE** | Se não houver termos Gundam, bloqueia |
| 5️⃣ | Filtro `todos` ativo? | Libera tudo se sim |
| 6️⃣ | Categoria selecionada | Precisa bater com palavras-chave |
| 7️⃣ | **Deduplicação** | Se link já está em `history.json`, ignora |

### 🎯 Termos do GUNDAM_CORE

```
gundam, gunpla, mobile suit, universal century, rx-78, zaku, zeon, 
char, amuro, hathaway, mafty, seed, seed freedom, witch from mercury, 
g-witch, p-bandai, premium bandai, ver.ka, hg, mg, rg, pg, sd, fm, re/100
```

### 🚫 BLACKLIST (bloqueados)

```
one piece, dragon ball, naruto, bleach, pokemon, digimon, 
attack on titan, jujutsu, demon slayer
```

---

## 🖥️ Deploy

### Local (desenvolvimento)

```bash
python main.py
```

### 🐳 Docker (Recomendado para Produção)

```bash
# Inicie com Docker Compose
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar
docker-compose down
```

**Vantagens do Docker:**
- ✅ Reinício automático se crashar
- ✅ Isolamento completo do sistema
- ✅ Fácil atualização (`git pull && docker-compose restart`)
- ✅ Logs com rotação automática
- ✅ Portável entre servidores

### VPS com systemd (produção)

Crie o arquivo `/etc/systemd/system/gundam-bot.service`:

```ini
[Unit]
Description=Gundam News Bot - Mafty Intel
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/gundam-bot
ExecStart=/opt/gundam-bot/.venv/bin/python main.py
Restart=always
RestartSec=5
User=gundam

[Install]
WantedBy=multi-user.target
```

Comandos úteis:

```bash
# Ativar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable gundam-bot
sudo systemctl start gundam-bot

# Verificar status
sudo systemctl status gundam-bot

# Ver logs em tempo real
journalctl -u gundam-bot -f
```

📖 **Guia completo:** Veja [docs/DEPLOY.md](docs/DEPLOY.md) para instruções detalhadas.

---

## 📊 Monitoramento e Logs

### Sistema de Logging Avançado

O bot possui um sistema de logging profissional com:

- 🎨 **Cores no Console** — Diferentes cores para cada nível de log
- 📝 **Traceback Colorido** — Stack traces formatados com cores
- 🔒 **Sanitização Automática** — Tokens e senhas são mascarados
- 📁 **Rotação de Arquivos** — Logs rotacionam automaticamente (5MB, 3 backups)
- 📊 **Níveis Configuráveis** — DEBUG, INFO, WARNING, ERROR, CRITICAL

### Exemplo de Logs

```
2026-02-13 10:30:45 - [INFO] ℹ️ Bot conectado como: Mafty#1234 (ID: 123456789)
2026-02-13 10:30:46 - [INFO] ℹ️ 📊 Servidores conectados: 3
2026-02-13 10:30:47 - [INFO] ℹ️ 🔄 Agendador de tarefas iniciado (12h).
2026-02-13 10:31:15 - [INFO] ℹ️ 🔎 Iniciando varredura de inteligência... (trigger=loop)
2026-02-13 10:31:20 - [WARNING] ⚠️ 🔒 URL bloqueada por segurança: http://localhost/test - IP privado/local não permitido
2026-02-13 10:31:25 - [INFO] ℹ️ ✅ Varredura concluída. (enviadas=5, cache_hits=12/15, trigger=loop)
```

### Ver Logs

```bash
# Docker
docker-compose logs -f

# Local
tail -f logs/bot.log

# Filtrar por nível
grep ERROR logs/bot.log
grep WARNING logs/bot.log
```

📄 **Documentação de melhorias:** Veja [analysis/LOGGING_IMPROVEMENTS.md](analysis/LOGGING_IMPROVEMENTS.md) para detalhes.

---

## 🗂️ Estrutura do Projeto

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
└── 📄 README.md            # Esta documentação
```

> **Nota:** Os arquivos `config.json`, `history.json` e `state.json` são gerados automaticamente em runtime e estão no `.gitignore`.

---

## 🧩 Troubleshooting

<details>
<summary><b>❌ CommandNotFound: Application command 'set_canal' not found</b></summary>

**Causa:** Sincronização global lenta do Discord.

**Solução:** O bot já faz sync por guild no `on_ready()`. Aguarde alguns segundos após o bot conectar.

</details>

<details>
<summary><b>❌ Bot não tem permissão para enviar mensagens</b></summary>

**Causa:** Bot não tem permissões no canal configurado.

**Solução:** 
1. Verifique as permissões do bot no servidor
2. Use `/set_canal` novamente - o bot verifica permissões automaticamente
3. Conceda as permissões: **Enviar Mensagens** e **Incorporar Links**

</details>

<details>
<summary><b>⚠️ "PyNaCl is not installed… voice will NOT be supported"</b></summary>

**Isso não é erro!** É apenas um aviso. O bot não usa recursos de voz, pode ignorar com segurança.

</details>

<details>
<summary><b>🔒 URL bloqueada por segurança</b></summary>

**Causa:** URL contém IP privado ou domínio local (proteção anti-SSRF).

**Solução:** Verifique se a URL em `sources.json` está correta e é pública.

</details>

<details>
<summary><b>⚠️ UnicodeEncodeError / emojis no console (Windows)</b></summary>

**Causa:** Terminal em encoding regional (ex.: cp1252) ao imprimir emojis nos logs.

**Solução:** O `utils/logger.py` usa stream UTF-8 no Windows quando possível. Se ainda falhar, defina antes de rodar: `set PYTHONIOENCODING=utf-8` (CMD) ou `$env:PYTHONIOENCODING="utf-8"` (PowerShell). Os logs em `logs/bot.log` permanecem em UTF-8.

</details>

---

## 🤝 Contribuindo

1. Faça um Fork do projeto
2. Crie sua feature branch (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

---

## 📜 Licença

Este projeto está licenciado sob a **MIT License** - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## 👨‍💻 Autor

**Paulo André Carminati**  
[![GitHub](https://img.shields.io/badge/GitHub-carmipa-181717?logo=github)](https://github.com/carmipa)

---

## 📚 Documentação Adicional

- 🛡️ [docs/OVERVIEW.md](docs/OVERVIEW.md) — Visão GRC: governança, riscos, controle e rastreabilidade
- 📋 [docs/COMMANDS_LIST.md](docs/COMMANDS_LIST.md) — Lista de comandos (o que cada um faz)
- 🧹 [docs/TUTORIAL_CLEAN_STATE.md](docs/TUTORIAL_CLEAN_STATE.md) — Tutorial do comando de limpeza
- 🧱 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Diagramas de arquitetura
- 🔒 [analysis/SECURITY_GRC_ANALYSIS.md](analysis/SECURITY_GRC_ANALYSIS.md) — Análise de segurança e GRC
- 📝 [analysis/LOGGING_IMPROVEMENTS.md](analysis/LOGGING_IMPROVEMENTS.md) — Melhorias de logging
- 🐳 [docs/DEPLOY.md](docs/DEPLOY.md) — Guia de deploy com Docker

---

<p align="center">
  🛰️ <i>Mafty Intelligence System — Vigilância contínua do Universal Century</i><br>
  <b>Versão 2.1</b> • <i>Segurança Aprimorada • Logs Profissionais • Multi-Idioma</i>
</p>
