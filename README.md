# 🛰️ Gundam Boot News — Mafty Intelligence System (v2.0)

<p align="center">
  <img alt="Gundam Boot News Banner" src="https://img.shields.io/badge/Mafty%20Intelligence-System-111827?style=for-the-badge&logo=target&logoColor=white">
</p>

<p align="center">
  <a href="https://discord.com/developers/applications">
    <img alt="Discord Bot" src="https://img.shields.io/badge/Status-Operacional-gold?style=for-the-badge&logo=discord&logoColor=white">
  </a>
  <img alt="Architecture" src="https://img.shields.io/badge/Architecture-SaaS%20Multi--Server-blueviolet?style=for-the-badge&logo=cloud&logoColor=white">
  <img alt="Auto Translation" src="https://img.shields.io/badge/Feature-Auto--Translation-green?style=for-the-badge&logo=googletranslate&logoColor=white">
  <a href="https://www.python.org/">
    <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white">
  </a>
  <a href="https://github.com/Rapptz/discord.py">
    <img alt="discord.py" src="https://img.shields.io/badge/discord.py-2.x-2B2D31?style=for-the-badge&logo=python&logoColor=white">
  </a>
  <a href="https://pypi.org/project/feedparser/">
    <img alt="feedparser" src="https://img.shields.io/badge/feedparser-RSS%2FAtom-0A0A0A?style=for-the-badge&logo=rss&logoColor=white">
  </a>
</p>

O **Mafty Intelligence System** é um bot de automação avançada para **Discord**, focado no ecossistema **Gundam** e **Gunpla**.  
Ele monitora feeds globais (**RSS/Atom** e **YouTube**) e entrega **inteligência traduzida e categorizada** diretamente no seu servidor.

> **Tema:** *Mafty Intelligence* — soberania informacional em tempo real.

---

## 🚀 Funcionalidades de Elite (Core Features)

- **Soberania SaaS (Multi-Servidor):** o bot gerencia configurações independentes por servidor (guild), salvando preferências de canais e filtros de forma isolada.
- **Dashboard de Filtros (UI/UX):** configure sem comandos complexos. Use `!dashboard` para abrir um painel interativo e selecionar categorias.
- **Categorização Inteligente:** filtra e classifica automaticamente os alertas em:
  - 📦 **Gunpla**: Model Kits (HG, MG, RG, P-Bandai).
  - 🎬 **Filmes/Anime**: lançamentos, trailers e vazamentos (Hathaway, SEED Freedom, etc.).
  - 🎮 **Games**: notícias de jogos (console/PC/mobile).
  - 🎵 **Músicas**: trilhas sonoras, aberturas e encerramentos.
  - 👕 **Fashion**: colaborações de roupas e lifestyle.
- **Tradução em Tempo Real:** converte automaticamente títulos em **EN/JP → PT-BR**.
- **Combo Visual “Rich Preview”:** envia um Card (Embed) + link direto para forçar preview rico no Discord.

---

## 🧭 Fontes Monitoradas (exemplo)

> Mantenha as fontes em `sources.json` para editar sem mexer no código.

### RSS / Atom
- Anime News Network — News RSS
- Gundam News — Feed
- Gunpla101 — Feed
- GUNJAP — RSS2
- USA Gundam Store — Atom (blog)
- Bandai (EUA) — RSS
- Gundam Kits Collection — RSS (Blogger)

### YouTube (Atom)
- GUNDAM CHANNEL (GundamInfo)
- SawanoHiroyuki[nZk] (músicas / OST)

### Oficiais (sites)
- Gundam Official (JP/EN)
- Bandai Hobby (Global/JP)
- The Gundam Base (News / Staff Blog)
- Battle Operation 2 (Info / patches)

---

## 🧰 Requisitos

- **Python 3.10+**
- Dependências (via `requirements.txt`):
  - `discord.py`
  - `feedparser`
  - `python-dotenv`

---

## 🛠️ Instalação

### 1) Clonar o repositório
```bash
git clone https://github.com/SEU_USUARIO/SEU_REPO.git
cd SEU_REPO
```

### 2) Criar e ativar ambiente virtual (opcional, recomendado)

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

## 🔐 Configuração (.env)

Crie um arquivo `.env` na raiz do projeto:

```env
TOKEN=SEU_DISCORD_TOKEN
ID_CANAL=ID_PADRAO
COMMAND_PREFIX=!
LOOP_MINUTES=30
```

> **Nunca** comite seu `.env`. Use `.env.example` como modelo.

---

## 📡 Operação do Sistema

### 1) Inicie o bot
```bash
python main.py
```

### 2) Configure filtros e canal alvo
No Discord:

1. Digite: `!dashboard`
2. O bot define o canal atual como alvo
3. Use o painel para ativar/desativar categorias (🌟 **Tudo / All-In** para cobertura total)

---

## 🧪 Troubleshooting

### ❌ Erro 403 / 50013 — Missing Permissions
Se o log mostrar `50013`, o bot não tem permissão para postar no canal escolhido.

**Como resolver**
1. Abra **Permissões do Canal**
2. Adicione o bot (ex.: `Gundam_boot_news`)
3. Garanta:
   - ✅ Ver Canal  
   - ✅ Enviar Mensagens  
   - ✅ Inserir Links  
   - ✅ Incorporar Links (Embeds)

---

## 🗂️ Estrutura de Arquivos (sugestão)

```txt
.
├─ main.py              # núcleo + comandos + UI (dashboard)
├─ settings.py          # leitura do .env e configs
├─ sources.json         # fontes RSS/Atom/YouTube
├─ config.json          # persistência por servidor (não versionar)
├─ .env                 # token (NÃO versionar)
├─ .env.example         # modelo sem segredos
└─ README.md
```

---

## 🧩 Exemplo de `sources.json`

```json
{
  "rss_feeds": [
    "https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us",
    "https://gundamnews.org/feed",
    "https://gunpla101.com/feed",
    "https://www.gunjap.net/site/?feed=rss2",
    "https://www.usagundamstore.com/blogs/usa-gundam-blog.atom",
    "https://www.bandai.com/blog/rss/feed",
    "https://www.gundamkitscollection.com/feeds/posts/default?alt=rss"
  ],
  "youtube_feeds": [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCejtUitnpnf8Be-v5NuDSLw",
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCbJM_Y06iuUOl3hVPqYcvng"
  ],
  "official_sites": [
    "https://gundam-official.com/",
    "https://en.gundam-official.com/news",
    "https://www.gundam-seed.net/news/",
    "https://bo2.ggame.jp/en/info/",
    "https://global.bandai-hobby.net/en-us/news/",
    "https://bandai-hobby.net/news/",
    "https://www.gundam-base.net/news",
    "https://www.gundam-base.net/staffblog/",
    "https://www.bandai.com/News",
    "https://en.gundam-official.com/video-music",
    "https://www.sunrise-music.co.jp/"
  ]
}
```

---

## 🚀 Subindo para o GitHub

```bash
git add .
git commit -m "Update README (v2.0) + dashboard + multi-server notes"
git push origin main
```

---

## ☄️ Créditos / Nota

Desenvolvido para entusiastas de **Gundam** e **Gunpla**.  
Que a soberania de **Mafty** guie seus alertas!
