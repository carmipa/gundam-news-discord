# 🛰️ Gundam News Bot — Mafty Intelligence System

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
  <img src="https://img.shields.io/badge/Status-Production-success" alt="Status" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License MIT" />
</p>

<p align="center">
  <b>Intelligent monitoring of RSS/Atom/YouTube feeds about the Gundam universe</b><br>
  Surgical filtering • Interactive Dashboard • Auto-posting to Discord
</p>

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [🧱 Architecture](#-architecture)
- [🚀 Installation](#-installation)
- [⚙️ Configuration](#️-configuration)
- [🧰 Commands](#-commands)
- [🎛️ Dashboard](#️-dashboard)
- [🧠 Filter System](#-filter-system)
- [🖥️ Deploy](#️-deploy)
- [🧩 Troubleshooting](#-troubleshooting)
- [📜 License](#-license)

---

## ✨ Features

| Feature | Description |
|---------|-----------|
| 📡 **Periodic Scanner** | Scans RSS/Atom/YouTube feeds every 12h (configurable via LOOP_MINUTES) |
| 🕵️ **HTML Watcher** | Monitors official non-RSS sites (e.g., Gundam Official) for visual changes |
| 🎛️ **Persistent Dashboard** | Interactive panel with buttons that work even after restart |
| 🎯 **Category Filters** | Gunpla, Movies, Games, Music, Fashion + "ALL" option |
| 🛡️ **Anti-Spam** | Blacklist to block non-Gundam related anime/games |
| 🔄 **Deduplication** | Never repeats news (history in `history.json`) |
| 🌐 **Multi-Guild** | Independent configuration per Discord server |
| 📝 **Logs in PT-BR** | Clear messages for debugging and monitoring |
| 🎨 **Rich Embeds** | Premium looking news (Gundam color, thumbnails, timestamps) |
| 🎞️ **Native Player** | YouTube/Twitch videos play directly in chat (no browser needed) |
| 🌍 **Multi-Language** | Support for EN, PT, ES, IT, JA (auto-detect + `/setlang`) |
| 🖥️ **Web Dashboard** | Visual panel at <http://host:8080> with real-time status |
| 🧹 **Auto-Cleanup** | Automatic cache cleaning every 7 days for performance (Zero maintenance) |
| ❄️ **Cold Start** | Immediately posts top 3 recent news from new sources (bypassing time locks) |
| 🔐 **Secure SSL** | Verified connections with certifi (MITM protection) |

---

## 🧱 Architecture

### 1) Macro View — Full Data Flow

```mermaid
flowchart LR
  A["sources.json<br>Feeds RSS/Atom/YouTube"] --> B["Scanner<br>core/scanner.py"]
  B --> C["Normalization<br>URL + entries"]
  C --> D["Mafty Filters<br>core/filters.py"]
  D -->|Approved| E["Translator (Auto)<br>utils/translator.py"]
  E --> F["Discord Post<br>Channel per guild"]
  D -->|Rejected| G["Ignore / Discard"]

  H["config.json<br>channel + filters + lang"] --> D
  H --> E
  I["history.json<br>sent links"] --> D
  F --> I

  W["Web Dashboard<br>aiohttp (Port 8080)"] .-> H
  W .-> I
  A["sources.json<br>Feeds RSS + HTML"] --> B["Scanner<br>core/scanner.py"]
  B --> C["Normalization<br>URL + entries"]
  B --> J["HTML Monitor<br>core/html_monitor.py"]
  C --> D["Mafty Filters<br>core/filters.py"]
  D -->|Approved| E["Translator (Auto)<br>utils/translator.py"]
  E --> F["Discord Post<br>Channel per guild"]
  J -->|Change Detected| F
  D -->|Rejected| G["Ignore / Discard"]

  H["config.json<br>channel + filters + lang"] --> D
  H --> E
  I["history.json<br>sent links"] --> D
  F --> I
  F --> K["state.json<br>Hashes HTML"]

  W["Web Dashboard<br>aiohttp (Port 8080)"] .-> H
  W .-> I
```

> **Legend:**
>
> - `sources.json` — List of monitored feeds
> - `config.json` — Channel and filter configuration per server
> - `history.json` — Sent links (deduplication)

---

### 2) `/dashboard` Command Flow and UI Persistence

```mermaid
sequenceDiagram
  participant Admin as Discord Admin
  participant Bot as Gundam News Bot
  participant Disk as config.json / history.json

  Admin->>Bot: /dashboard (in desired channel)
  Bot->>Disk: saves guild channel_id (current channel)
  Bot-->>Admin: sends panel (ephemeral) with buttons
  Admin->>Bot: clicks filters (Gunpla/Movies/Games...)
  Bot->>Disk: updates guild filters
  Bot-->>Admin: updates button colors (active/inactive)

  Note over Bot: Bot Restart (VPS/PC)
  Bot->>Disk: reads config.json
  Bot-->>Admin: re-registers Persistent Views (bot.add_view)
  Admin->>Bot: clicks old buttons
  Bot-->>Admin: works (doesn't break after restart)
```

> **Highlights:**
>
> - The panel is **ephemeral** (only you see it)
> - Buttons work **even after bot restart**
> - Configuration is **saved to disk** automatically

---

### 3) Main Bot States

```mermaid
stateDiagram-v2
  [*] --> Connecting
  Connecting --> Online: Token OK
  Online --> SyncGuild: on_ready()
  SyncGuild --> PersistentViews: add_view per guild from config
  PersistentViews --> ScannerActive: starts loop
  ScannerActive --> ScannerActive: scans feeds / posts / saves history
  ScannerActive --> Online: feed error (handled / PT logs)
```

> **Lifecycle:**
>
> 1. **Connecting** — Validating token
> 2. **Online** — Connected to Discord
> 3. **SyncGuild** — Syncing slash commands
> 4. **PersistentViews** — Restoring dashboard buttons
> 5. **ScannerActive** — Scan loop running

---

### 4) State Maintenance (Auto-Cleanup)

The bot features an autonomous maintenance system to prevent infinite cache growth:

- **7-Day Cycle**: Every week, the deduplication key (`dedup`) is automatically cleared.
- **Smart Cold Start**: Upon detecting a new source or recent cleanup, the bot enters "Cold Start" mode, allowing the **top 3 post recent news** to be posted immediately, bypassing restrictive time filters (while keeping content filters active).
- **Benefit**: Ensures the bot can run on resource-constrained environments without manual intervention.

---

## 🚀 Installation

### Prerequisites

- Python 3.10 or higher
- Discord Bot Token ([Developer Portal](https://discord.com/developers/applications))

### Step by Step

```bash
# 1. Clone the repository
git clone https://github.com/carmipa/gundam-news-discord.git
cd gundam-news-discord

# 2. Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your token
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```env
# Required
DISCORD_TOKEN=your_token_here

# Optional
COMMAND_PREFIX=!
LOOP_MINUTES=720
LOG_LEVEL=INFO  # Use DEBUG for detailed GRC logs
```

### Feed Sources (`sources.json`)

The bot accepts two formats:

<details>
<summary><b>📁 Category Format (Recommended)</b></summary>

```json
{
  "rss_feeds": [
    "https://www.animenewsnetwork.com/news/rss.xml",
    "https://gundamnews.org/feed"
  ],
  "youtube_feeds": [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCejtUitnpnf8Be-v5NuDSLw"
  ]
}
```

</details>

<details>
<summary><b>📁 Official Sites (HTML Monitoring)</b></summary>
Sites without RSS are placed in a separate array. The bot checks for hash changes.

```json
{
  "official_sites_reference_(not_rss)": [
    "https://gundam-official.com/",
    "https://en.gundam-official.com/news"
  ]
}
```

</details>

<details>
<summary><b>📁 Simple List Format</b></summary>

```json
[
  "https://www.animenewsnetwork.com/news/rss.xml",
  "https://gundamnews.org/feed"
]
```

</details>

---

## 🧰 Commands

### 🔧 Administrative Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `/set_canal` | Sets the channel where the bot will send news | `/set_canal [channel:#news]` |
| `/dashboard` | Opens visual panel to configure filters | `/dashboard` |
| `/setlang` | Sets bot language for the server | `/setlang language:en_US` |
| `/forcecheck` | Forces immediate feed scan | `/forcecheck` |
| `/clean_state` | Cleans parts of state.json (with automatic backup) | `/clean_state type:dedup confirm:yes` |

### 📊 Informational Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `/status` | Shows bot statistics (Uptime, Scans, etc) | `/status` |
| `/feeds` | Lists all monitored sources | `/feeds` |
| `/help` | Shows help manual | `/help` |
| `/ping` | Checks bot latency | `/ping` |
| `/about` | Bot information | `/about` |

> **🔒 Permission:** Only administrators can use administrative commands.

### 📖 Usage Examples

#### Configuration
```bash
# Set channel quickly
/set_canal                    # Uses current channel
/set_canal channel:#news      # Sets specific channel

# Open dashboard
/dashboard                    # Opens filter panel

# Set language
/setlang language:en_US       # English
/setlang language:pt_BR       # Portuguese
```

#### Maintenance
```bash
# Clean state.json (requires confirmation)
/clean_state type:dedup confirm:no     # View statistics first
/clean_state type:dedup confirm:yes    # Execute cleanup

# Available types:
# - dedup: Sent links history
# - http_cache: HTTP cache (ETags)
# - html_hashes: HTML monitoring hashes
# - everything: Cleans everything (use with caution!)

# Force manual scan
/forcecheck                   # Executes immediate scan
```

#### Information
```bash
# Check status
/status                       # Bot statistics

# List feeds
/feeds                        # All monitored sources

# Help
/help                         # Complete manual
```

### ⚠️ `/clean_state` Command - Details

The `/clean_state` command allows cleaning specific parts of `state.json`:

**Cleaning Options:**

| Type | What it Cleans | Impact |
|------|----------------|--------|
| 🧹 **dedup** | Sent links history | ⚠️ Bot will repost recent news |
| 🌐 **http_cache** | HTTP cache (ETags, Last-Modified) | ℹ️ More HTTP requests, no reposting |
| 🔍 **html_hashes** | HTML monitoring hashes | ⚠️ Sites will be detected as "changed" |
| ⚠️ **everything** | Cleans everything (except metadata) | 🚨 All effects above combined |

**Protections:**
- ✅ Automatic backup before cleaning
- ✅ Double confirmation required
- ✅ Statistics before/after
- ✅ Complete audit logging

---

## 🎛️ Dashboard

The interactive panel allows configuring which categories to monitor:

| Button | Function |
|-------|--------|
| 🌟 **ALL** | Toggle all categories |
| 🤖 **Gunpla** | Kits, P-Bandai, Ver.Ka, HG/MG/RG/PG |
| 🎬 **Movies** | Anime, trailers, series, Hathaway, SEED |
| 🎮 **Games** | Gundam Games (GBO2, Breaker, etc.) |
| 🎵 **Music** | OST, albums, openings/endings |
| 👕 **Fashion** | Apparel and merchandise |
| 📌 **View Filters** | Shows active filters |
| 🔄 **Reset** | Clears all filters |

### Visual Indicators

- 🟢 **Green** = Filter active
- ⚪ **Gray** = Filter inactive

---

## 🧠 Filter System

The filtering is **not simple** — the bot uses a **layered** system to ensure surgical precision:

### Decision Flow

```mermaid
flowchart TD
    A["📰 News Received"] --> B{"🚫 Is in BLACKLIST?"}
    B -->|Yes| C["❌ Discarded"]
    B -->|No| D{"🎯 Contains GUNDAM_CORE?"}
    D -->|No| C
    D -->|Yes| E{"🌟 'All' Filter Active?"}
    E -->|Yes| F["✅ Approved for Posting"]
    E -->|No| G{"📂 Matches Selected Category?"}
    G -->|Yes| F
    G -->|No| C
    F --> H{"🔄 Link in History?"}
    H -->|Yes| C
    H -->|No| I["📤 Send to Discord"]
```

### ✅ Filtering Rules (real order)

| Step | Check | Action |
|-------|-------------|------|
| 1️⃣ | Join `title + summary` | Concatenate text |
| 2️⃣ | Clean HTML and normalize | Remove tags, extra spaces |
| 3️⃣ | **BLACKLIST** | If present (e.g., *One Piece*), block |
| 4️⃣ | **GUNDAM_CORE** | If no Gundam terms, block |
| 5️⃣ | 'All' filter active? | Allow everything if yes |
| 6️⃣ | Selected Category | Must match keywords |
| 7️⃣ | **Deduplication** | If link is already in `history.json`, ignore |

### 🎯 GUNDAM_CORE Terms

```
gundam, gunpla, mobile suit, universal century, rx-78, zaku, zeon, 
char, amuro, hathaway, mafty, seed, seed freedom, witch from mercury, 
g-witch, p-bandai, premium bandai, ver.ka, hg, mg, rg, pg, sd, fm, re/100
```

### 🚫 BLACKLIST (blocked)

```
one piece, dragon ball, naruto, bleach, pokemon, digimon, 
attack on titan, jujutsu, demon slayer
```

### 🔧 Where to adjust precision?

| Constant | Purpose |
|-----------|-----------|
| `GUNDAM_CORE` | Enforces "is Gundam" — add terms here |
| `BLACKLIST` | Cuts noise from generalist feeds |
| `CAT_MAP` | Adjusts triggers per category |

---

## 🖥️ Deploy

### Local (Development)

```bash
python main.py
```

### VPS with systemd (Production)

Create file `/etc/systemd/system/gundam-bot.service`:

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

Useful commands:

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable gundam-bot
sudo systemctl start gundam-bot

# Check status
sudo systemctl status gundam-bot

# View real-time logs
journalctl -u gundam-bot -f
```

### 🐳 VPS with Docker (Recommended for Production)

**Quick Install:**

```bash
# Clone the repository
git clone https://github.com/carmipa/gundam-news-discord.git
cd gundam-news-discord

# Configure .env with your token
cp .env.example .env
nano .env

# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f
```

**Docker Benefits:**

- ✅ Auto-restart if crashes
- ✅ Complete system isolation
- ✅ Easy update (`git pull && docker-compose restart`)
- ✅ Log rotation
- ✅ Portable between servers

📖 **Complete Guide:** See [DEPLOY.md](DEPLOY.md) for detailed instructions.

---

## 🗂️ Project Structure

```
gundam-news-discord/
├── 📄 main.py              # Main Bot
├── 📄 settings.py          # Loads configuration from .env
├── 📄 sources.json         # List of monitored feeds
├── 📄 requirements.txt     # Python dependencies
├── 📄 .env.example         # Configuration example
├── 📄 .gitignore           # Git ignored files
├── 🖼️ icon.png             # Bot icon
├── 📁 .github/             # GitHub Actions Workflows
├── 📁 bot/                 # Bot logic (Cogs, Views)
├── 📁 core/                # System Core (Scanner, Filters, HTML Monitor)
├── 📁 tests/               # Automated tests
├── 📁 translations/        # Internationalization (i18n)
├── 📁 utils/               # Utilities (Logger, Helpers)
├── 📁 web/                 # Web Dashboard
└── 📄 README.md            # This documentation
```

> **Note:** Files `config.json` and `history.json` are generated automatically at runtime and are in `.gitignore`.

---

## 🧩 Troubleshooting

<details>
<summary><b>❌ CommandNotFound: Application command 'dashboard' not found</b></summary>

**Cause:** Discord global sync lag.

**Solution:** The bot already syncs per guild in `on_ready()`. Wait a few seconds after the bot connects.

</details>

<details>
<summary><b>❌ AttributeError: 'str' object has no attribute 'get'</b></summary>

**Cause:** Incorrect format of `sources.json`.

**Solution:** Check if the file is in one of the accepted formats (list or dictionary with categories).

</details>

<details>
<summary><b>⚠️ "PyNaCl is not installed… voice will NOT be supported"</b></summary>

**Not an error!** Just a warning. The bot does not use voice features, safely ignore.

</details>

---

## 🤝 Contributing

1. Fork the project
2. Create your feature branch (`git checkout -b feature/MyFeature`)
3. Commit your changes (`git commit -m 'Add MyFeature'`)
4. Push to the branch (`git push origin feature/MyFeature`)
5. Open a Pull Request

---

## 📜 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Paulo André Carminati**  
[![GitHub](https://img.shields.io/badge/GitHub-carmipa-181717?logo=github)](https://github.com/carmipa)

---

<p align="center">
  🛰️ <i>Mafty Intelligence System — Vigilance for the Universal Century</i>
</p>
