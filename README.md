# 🛰️ Gundam Boot News — Mafty Intelligence System (v2.0)

<p align="center">
  <img src="icon.png" alt="Gundam Boot News Icon" width="140" />
</p>

<p align="center">
  <img alt="Mafty Intelligence System" src="https://img.shields.io/badge/Mafty%20Intelligence-System-111827?style=for-the-badge&logo=target&logoColor=white">
</p>

<p align="center">
  <img alt="Status" src="https://img.shields.io/badge/Status-Operacional-gold?style=for-the-badge&logo=discord&logoColor=white">
  <img alt="Architecture" src="https://img.shields.io/badge/Architecture-SaaS%20Multi--Server-blueviolet?style=for-the-badge&logo=cloud&logoColor=white">
  <img alt="Auto Translation" src="https://img.shields.io/badge/Feature-Auto--Translation-green?style=for-the-badge&logo=googletranslate&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="discord.py" src="https://img.shields.io/badge/discord.py-2.x-2B2D31?style=for-the-badge&logo=python&logoColor=white">
  <img alt="feedparser" src="https://img.shields.io/badge/feedparser-RSS%2FAtom-0A0A0A?style=for-the-badge&logo=rss&logoColor=white">
</p>

O **Mafty Intelligence System** é um bot de automação avançada para **Discord**, focado no ecossistema **Gundam** e **Gunpla**.  
Ele monitora feeds globais (**RSS/Atom** e **YouTube**) e entrega **inteligência traduzida e categorizada** diretamente no seu servidor.

> **Tema:** *Mafty Intelligence* — soberania informacional em tempo real.

---

## 🚀 Funcionalidades de Elite (Core Features)

- **Soberania SaaS (Multi-Servidor):** configurações independentes por servidor (guild), salvando preferências de canal e filtros por servidor.
- **Dashboard de Filtros (UI/UX):** use `!dashboard` para abrir um painel interativo com botões e escolher categorias.
- **Categorização Inteligente:**
  - 📦 **Gunpla** — HG / MG / RG / P-Bandai / Model Kits
  - 🎬 **Filmes/Anime** — releases, trailers, episódios, etc.
  - 🎮 **Games** — console/PC/mobile, updates e patches
  - 🎵 **Músicas** — OST, OP/ED, releases
  - 👕 **Fashion** — collabs e apparel
- **Tradução em Tempo Real:** EN/JP → PT-BR (título do alerta).
- **Combo Visual “Rich Preview”:** envia **Embed + link puro** para forçar preview grande no Discord.

---

## 🧱 Arquitetura (Diagrama)

> GitHub renderiza Mermaid nativamente. Se você estiver visualizando fora do GitHub, pode aparecer como código.

```mermaid
flowchart TB
  subgraph Discord["Discord"]
    U["Usuários/Admin"] -->|!dashboard| B["Bot (discord.py)"]
    B -->|Embeds + Link| C["Canal configurado"]
  end

  subgraph App["Aplicação (Python)"]
    B --> D["FilterDashboard (UI Buttons)"]
    D -->|Load/Save| CFG["config.json (por servidor/guild)"]

    B --> L["Task Loop: intelligence_gathering()"]
    L -->|Read| SRC["sources.json"]
    L --> FP["feedparser.parse()"]
    FP --> R["Feeds RSS/Atom"]
    FP --> Y["Feeds YouTube (Atom)"]

    L --> TR["deep_translator (GoogleTranslator)"]
    TR --> API["Serviço de Tradução"]
  end

  subgraph Env["Config / Ambiente"]
    ENV[".env (DISCORD_TOKEN / DISCORD_CHANNEL_ID)"] --> SET["settings.py"]
    SET --> B
  end
```

---

## 🧭 Fontes Monitoradas

> As fontes ficam em `sources.json`, assim você edita sem mexer no código.

- **rss_feeds**: RSS/Atom de sites (notícias, gunpla, lojas, etc.)
- **youtube_feeds**: Atom feed de canais do YouTube
- **official_sites**: lista de referência (links oficiais)

---

## 🧰 Requisitos

- **Python 3.10+**
- Dependências (via `requirements.txt`):
  - `discord.py`
  - `feedparser`
  - `python-dotenv`
  - `deep-translator`

---

## 🛠️ Instalação

### 1) Clonar o repositório
```bash
git clone https://github.com/carmipa/gundam-news-discord.git
cd gundam-news-discord
```

### 2) Criar e ativar ambiente virtual (recomendado)

**Windows (PowerShell)**
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux/macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Instalar dependências
```bash
pip install -r requirements.txt
```

---

## 🔐 Configuração do `.env`

Crie um arquivo `.env` na raiz (você pode copiar de `.env.example`):

```env
DISCORD_TOKEN=seu_token_aqui
DISCORD_CHANNEL_ID=seu_id_do_canal_aqui
```

> **Segurança:** nunca faça commit do `.env`. Mantenha no `.gitignore`.

---

## 📡 Como Usar

### 1) Inicie o bot
```bash
python main.py
```

### 2) Configure filtros/canal
No Discord (com permissões de admin):
1. Vá no canal que você quer receber os alertas
2. Digite: `!dashboard`
3. Clique nos botões para ativar/desativar categorias (🌟 **Tudo / All-In** para cobertura total)

---

## 🗂️ Estrutura do Projeto

```txt
.
├─ main.py              # núcleo + comandos + UI (dashboard) + loop de monitoramento
├─ settings.py          # lê DISCORD_TOKEN / DISCORD_CHANNEL_ID do .env
├─ sources.json         # feeds RSS/Atom + YouTube Atom + sites oficiais
├─ config.json          # persistência por servidor (NÃO versionar em produção)
├─ icon.png             # ícone do projeto (usado neste README)
├─ .env.example         # modelo de .env (sem segredos)
├─ .gitignore
└─ README.md
```

---

## 🧪 Troubleshooting

### ❌ Erro 403 / 50013 — Missing Permissions
Se o log mostrar `50013`, o bot não tem permissão para postar no canal.

**Como resolver**
- Permissões do canal:
  - ✅ Ver Canal
  - ✅ Enviar Mensagens
  - ✅ Inserir Links
  - ✅ Incorporar Links (Embeds)

---

## 🛡️ Roadmap Anti-Flood (próximos upgrades)

- **Dedup global** por `guid → link → hash(title+source)`  
- **Cache por janela** (ex.: últimos 2000 hashes por 7–30 dias)
- **ETag/Last-Modified** para evitar reprocessar o feed inteiro
- **Rate-limit por fonte** (ex.: 3 posts/10 min por feed)
- **Modo Digest** (1 embed com 10 links por ciclo)

---

## ☄️ Nota

Desenvolvido para entusiastas de **Gundam** e **Gunpla**.  
**“Que a soberania de Mafty guie seus alertas!”**
