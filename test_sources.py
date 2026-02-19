
import json
import asyncio
import httpx
import feedparser
import time
from bs4 import BeautifulSoup
import sys

# Windows console encoding fix
sys.stdout.reconfigure(encoding='utf-8')

SOURCES_FILE = "sources.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

async def check_rss(client, url):
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        
        feed = feedparser.parse(resp.content)
        if feed.bozo:
             # Some valid feeds trigger bozo, check entries
             if not feed.entries:
                 return False, f"Bozo Error: {feed.bozo_exception}"
        
        if not feed.entries:
            return False, "0 Entradas (Feed Vazio)"
            
        last_date = "N/A"
        if 'published' in feed.entries[0]:
            last_date = feed.entries[0].published
        elif 'updated' in feed.entries[0]:
            last_date = feed.entries[0].updated
            
        return True, f"✅ OK ({len(feed.entries)} posts, Último: {last_date})"
    except Exception as e:
        return False, f"Erro: {str(e)}"

async def check_html(client, url):
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        
        if len(resp.text) < 500:
            return False, f"Conteúdo muito curto ({len(resp.text)} bytes)"
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else "Sem Título"
        
        return True, f"✅ OK (Título: {title})"
    except Exception as e:
        return False, f"Erro: {str(e)}"

async def main():
    print("📂 Carregando sources.json...")
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ sources.json não encontrado!")
        return

    async with httpx.AsyncClient(headers=HEADERS, timeout=20.0, verify=False) as client:
        
        print("\n🔎 --- TESTANDO FEEDS RSS ---")
        rss_feeds = data.get("rss_feeds", [])
        for url in rss_feeds:
            status, msg = await check_rss(client, url)
            icon = "✅" if status else "❌"
            print(f"{icon} {url}\n   └── {msg}")

        print("\n🔎 --- TESTANDO CANAIS YOUTUBE (RSS) ---")
        yt_feeds = data.get("youtube_feeds", [])
        for url in yt_feeds:
            status, msg = await check_rss(client, url)
            icon = "✅" if status else "❌"
            print(f"{icon} {url}\n   └── {msg}")

        print("\n🔎 --- TESTANDO HTML MONITOR (SITES OFICIAIS) ---")
        html_sites = data.get("official_sites_reference_(not_rss)", [])
        for url in html_sites:
            status, msg = await check_html(client, url)
            icon = "✅" if status else "❌"
            print(f"{icon} {url}\n   └── {msg}")

if __name__ == "__main__":
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    pass 
    # Suppress httpx logs
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Teste interrompido pelo usuário.")
