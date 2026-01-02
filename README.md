# 🛰️ Gundam Boot News — Mafty Intelligence System

<p align="center">
  <img alt="Gundam Boot News Banner" src="https://img.shields.io/badge/Mafty%20Intelligence-System-111827?style=for-the-badge&logo=target&logoColor=white">
</p>

<p align="center">
  <a href="https://discord.com/developers/applications">
    <img alt="Discord Bot" src="https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white">
  </a>
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

Bot de automação para **Discord**, focado no universo **Gundam** e **Gunpla**.  
Ele monitora feeds de **notícias**, **hobby/model kits**, **lançamentos**, **patch notes**, e **vídeos oficiais**, centralizando tudo direto no seu servidor.

> **Tema:** *Mafty Intelligence* — soberania informacional em tempo real.

---

## ✨ Funcionalidades

- ✅ **Setup via UI (Dropdown):** `!setup` abre um menu para escolher o canal sem precisar lidar com IDs.
- 🔄 **Monitoramento automatizado:** varredura contínua de RSS/Atom + YouTube.
- 💾 **Persistência de configuração:** salva o canal ativo em `config.json` para sobreviver a reinícios.
- 🧠 **Filtro de Inteligência:** posta apenas conteúdos relevantes (ex.: “Gundam”, “Gunpla”, “Bandai”, etc.).
- 🧩 **Embeds bonitos:** cards com título, descrição e link (pronto pra clicar).

---

## 🧭 Fontes Monitoradas (exemplo)

> Você pode manter as fontes em `sources.json` (recomendado) para editar sem mexer no código.

### RSS / Atom
- Anime News Network — News RSS
- Gundam News — Feed
- Gunpla101 — Feed
- GUNJAP — RSS2
- USA Gundam Store — Atom (blog)
- Bandai (EUA) — RSS
- Gundam Kits Collection — RSS (Blogger)

### Oficiais (sites)
- Gundam Official (JP) + Gundam Official (EN)
- Bandai Hobby (Global/JP)
- The Gundam Base (News / Staff Blog)
- Battle Operation 2 (Info / patches)

---

## 🧰 Requisitos

- **Python 3.10+**
- Dependências:
  - `discord.py`
  - `feedparser`
  - `python-dotenv`

---

## ⚙️ Instalação

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
pip install -U discord.py feedparser python-dotenv
```

---

## 🔐 Configuração (.env)

Crie um arquivo `.env` na raiz do projeto:

```env
DISCORD_TOKEN=SEU_TOKEN_AQUI
```

> **Nunca** comite seu `.env`. (Use `.gitignore`.)

---

## 📡 Como Usar

### 1) Inicie o bot
```bash
python main.py
```

### 2) Configure o canal alvo
No Discord:
1. Digite: `!setup`
2. Selecione o canal no **Dropdown**
3. Confirme: aparecerá uma mensagem de “Soberania Estabelecida”.

---

## 🧪 Troubleshooting

### ❌ Erro 403 / 50013 — Missing Permissions
Se o log mostrar `50013`, o bot não tem permissão no canal escolhido.

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
├─ main.py              # lógica principal do bot + comandos + UI
├─ settings.py          # leitura do .env e configs
├─ sources.json         # fontes RSS/Atom/YouTube (editável sem mexer no código)
├─ config.json          # gerado automaticamente (persistência do canal alvo)
├─ .env                 # token (NÃO versionar)
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
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCejtUitnpnf8Be-v5NuDSLw"
  ],
  "official_sites": [
    "https://gundam-official.com/",
    "https://en.gundam-official.com/news",
    "https://global.bandai-hobby.net/en-us/news/",
    "https://bandai-hobby.net/news/",
    "https://www.gundam-base.net/news",
    "https://www.gundam-base.net/staffblog/",
    "https://bo2.ggame.jp/en/info/"
  ]
}
```

---

## 🚀 Subindo para o GitHub

```bash
git add .
git commit -m "Add README + setup UI + sources list"
git push origin main
```

---

## ☄️ Créditos / Nota

Desenvolvido para entusiastas de **Gundam** e **Gunpla**.  
Que a soberania de **Mafty** guie suas notícias. 🟨🟦
