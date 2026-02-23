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
  <img src="https://img.shields.io/badge/Status-Produzione-success" alt="Status" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License MIT" />
</p>

<p align="center">
  <b>Monitoraggio intelligente di feed RSS/Atom/YouTube sull'universo Gundam</b><br>
  Filtraggio chirurgico • Dashboard interattiva • Pubblicazione automatica su Discord
</p>

---

## 📋 Indice

- [✨ Funzionalità](#-funzionalità)
- [🧱 Architettura](#-architettura)
- [🚀 Installazione](#-installazione)
- [⚙️ Configurazione](#️-configurazione)
- [🧰 Comandi](#-comandi)
- [🎛️ Dashboard](#️-dashboard)
- [🧠 Sistema di Filtri](#-sistema-di-filtri)
- [🖥️ Deploy](#️-deploy)
- [🧩 Risoluzione Problemi](#-risoluzione-problemi)
- [📜 Licenza](#-licenza)

---

## ✨ Funzionalità

| Funzionalità | Descrizione |
|---------|-----------|
| 📡 **Scanner Periodico** | Scansione di feed RSS/Atom/YouTube ogni 12h (configurabile) |
| 🕵️ **HTML Watcher** | Monitora siti ufficiali senza RSS (es: Gundam Official) rilevando cambiamenti visivi |
| 🎛️ **Dashboard Persistente** | Pannello interattivo con pulsanti che funzionano anche dopo il riavvio |
| 🎯 **Filtri per Categoria** | Gunpla, Film, Giochi, Musica, Moda + opzione "TUTTO" |
| 🛡️ **Anti-Spam** | Blacklist per bloccare anime/giochi non correlati a Gundam |
| 🔄 **Deduplicazione** | Non ripete mai le notizie (cronologia in `history.json`) |
| 🌐 **Multi-Guild** | Configurazione indipendente per server Discord |
| 📝 **Log Chiari** | Messaggi di debug e monitoraggio dettagliati |
| 🎨 **Embed Ricchi** | Notizie con visual premium (colore Gundam, miniature, timestamp) |
| 🎞️ **Player Nativo** | Video YouTube/Twitch riprodotti direttamente nella chat (senza aprire browser) |
| 🌍 **Multi-Lingua** | Supporto per EN, PT, ES, IT, JA (rilevamento automatico + `/setlang`) |
| 🖥️ **Web Dashboard** | Pannello visivo su <http://host:8080> con stato in tempo reale |
| 🧹 **Auto-Pulizia** | Pulizia automatica della cache ogni 7 giorni per prestazioni (Manutenzione Zero) |
| ❄️ **Cold Start** | Pubblica immediatamente le 3 notizie più recenti da nuove fonti (ignora blocchi temporali) |
| 🔐 **SSL Sicuro** | Connessioni verificate con certifi (protezione contro MITM) |

---

## 🧱 Architettura

### 1) Visione Macro — Flusso Completo dei Dati

```mermaid
flowchart LR
  A["sources.json<br>Feed RSS/Atom/YouTube"] --> B["Scanner<br>core/scanner.py"]
  B --> C["Normalizzazione<br>URL + entries"]
  B --> J["HTML Monitor<br>core/html_monitor.py"]
  C --> D["Filtri Mafty<br>core/filters.py"]
  D -->|Approvato| E["Traduttore (Auto)<br>utils/translator.py"]
  E --> F["Post Discord<br>Canale per guild"]
  J -->|Cambiamento Rilevato| F
  D -->|Rifiutato| G["Ignora / Scarta"]

  H["config.json<br>canale + filtri + lingua"] --> D
  H --> E
  I["history.json<br>link inviati"] --> D
  F --> I
  F --> K["state.json<br>Hash HTML"]

  W["Web Dashboard<br>aiohttp (Port 8080)"] .-> H
  W .-> I
```

---

## 🚀 Installazione

### Prerequisiti

- Python 3.10 o superiore
- Token bot Discord ([Portale Sviluppatori](https://discord.com/developers/applications))

### Passo dopo passo

```bash
# 1. Clona il repository
git clone https://github.com/carmipa/gundam-news-discord.git
cd gundam-news-discord

# 2. Crea ambiente virtuale
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 3. Installa dipendenze
pip install -r requirements.txt

# 4. Configura l'ambiente
cp .env.example .env
# Modifica .env con il tuo token
```

---

## ⚙️ Configurazione

### Variabili d'Ambiente (`.env`)

```env
# Obbligatorio
DISCORD_TOKEN=il_tuo_token_qui

# Opzionale
COMMAND_PREFIX=!
LOOP_MINUTES=720
LOG_LEVEL=INFO  # Usa DEBUG per log GRC dettagliati
```

### Fonti Feed (`sources.json`)

Il bot accetta due formati:

<details>
<summary><b>📁 Formato con categorie (consigliato)</b></summary>

```json
{
  "rss_feeds": [
    "https://www.animenewsnetwork.com/news/rss.xml",
  ],
  "youtube_feeds": [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCejtUitnpnf8Be-v5NuDSLw"
  ]
}
```

</details>

<details>
<summary><b>📁 Sito Ufficiali (Monitoraggio HTML)</b></summary>
I siti senza RSS sono inseriti in un array separato. Il bot controlla i cambiamenti di hash.

```json
{
  "official_sites_reference_(not_rss)": [
    "https://gundam-official.com/"
  ]
}
```

</details>

---

## 🧰 Comandi

### 🔧 Comandi Amministrativi

| Comando | Descrizione | Uso |
|---------|-------------|-----|
| `/set_canal` | Imposta il canale dove il bot invierà notizie | `/set_canal [canale:#notizie]` |
| `/dashboard` | Apre pannello visuale per configurare filtri | `/dashboard` |
| `/setlang` | Imposta la lingua del bot per il server | `/setlang lingua:it_IT` |
| `/forcecheck` | Forza una scansione immediata | `/forcecheck` |
| `/clean_state` | Pulisce parti del state.json (con backup automatico) | `/clean_state tipo:dedup confermare:si` |

### 📊 Comandi Informativi

| Comando | Descrizione | Uso |
|---------|-------------|-----|
| `/status` | Mostra statistiche del bot | `/status` |
| `/feeds` | Elenca tutte le fonti monitorate | `/feeds` |
| `/help` | Mostra manuale di aiuto | `/help` |
| `/ping` | Verifica latenza del bot | `/ping` |
| `/about` | Informazioni sul bot | `/about` |

> **🔒 Permessi:** Solo gli amministratori possono usare comandi amministrativi.

---

## 🎛️ Dashboard

Il pannello interattivo permette di configurare quali categorie monitorare:

| Pulsante | Funzione |
|-------|--------|
| 🌟 **TUTTO** | Attiva/disattiva tutte le categorie |
| 🤖 **Gunpla** | Kit, P-Bandai, Ver.Ka, HG/MG/RG/PG |
| 🎬 **Film** | Anime, trailer, serie, Hathaway, SEED |
| 🎮 **Giochi** | Giochi Gundam (GBO2, Breaker, ecc.) |
| 🎵 **Musica** | OST, album, sigle |
| 👕 **Moda** | Abbigliamento e merchandise |
| 📌 **Vedi filtri** | Mostra filtri attivi |
| 🔄 **Reset** | Azzera tutti i filtri |

---

## 🧠 Sistema di Filtri

Il filtraggio **non è semplice** — il bot usa un sistema a **strati** per garantire precisione chirurgica:

### Flusso Decisionale

```mermaid
flowchart TD
    A["📰 Notizia Ricevuta"] --> B{"🚫 È nella BLACKLIST?"}
    B -->|Sì| C["❌ Scartata"]
    B -->|No| D{"🎯 Contiene GUNDAM_CORE?"}
    D -->|No| C
    D -->|Sì| E{"🌟 Filtro 'tutto' attivo?"}
    E -->|Sì| F["✅ Approvata per Pubblicazione"]
    E -->|No| G{"📂 Corrisponde a categoria selezionata?"}
    G -->|Sì| F
    G -->|No| C
    F --> H{"🔄 Link già in cronologia?"}
    H -->|Sì| C
    H -->|No| I["📤 Invia a Discord"]
```

---

## 🖥️ Deploy

### Docker (Consigliato)

```bash
docker-compose up -d
```

Vedi [DEPLOY.md](DEPLOY.md) per maggiori dettagli.

---

## 📜 Licenza

Questo progetto è sotto licenza **MIT License** - vedi il file [LICENSE](LICENSE) per dettagli.

---

<p align="center">
  🛰️ <i>Mafty Intelligence System — Vigilanza continua dell'Universal Century</i>
</p>
