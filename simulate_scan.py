import sys
import asyncio
import feedparser
import aiohttp
from core.scanner import sanitize_link, parse_entry_dt, get_news_metadata
from core.filters import match_intel
import json

async def simulate_scan():
    print("🚀 Iniciando Simulação do Scanner...")
    try:
        with open('sources.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            sources = data.get('youtube_feeds', []) + data.get('rss_feeds', [])
    except Exception as e:
        print(f"Erro lendo sources.json: {e}")
        return

    # Use a dummy config allowing all
    dummy_config = {"1": {"filters": ["todos"], "language": "pt"}}
    
    async with aiohttp.ClientSession() as session:
        for url in sources:
            print(f"📡 Fetching {url}")
            try:
                async with session.get(url, timeout=10) as resp:
                    text = await resp.text(errors="ignore")
                    feed = feedparser.parse(text)
                    entries = getattr(feed, "entries", [])
                    print(f"  ✅ Encontrados {len(entries)} vídeos")
                    
                    matched_count = 0
                    for entry in entries:
                        link = entry.get("link", "")
                        if not link: continue
                        link = sanitize_link(link)
                        
                        dt = parse_entry_dt(entry)
                        # We won't strictly drop by age, just simulate
                        title = entry.get("title", "")
                        summary = entry.get("summary", "") or entry.get("description", "")
                        
                        # Match testing
                        matched = match_intel("1", title, summary, dummy_config, source_url=url)
                        if matched:
                            matched_count += 1
                            prefix, color = get_news_metadata(title, link)
                            
                            # Embed simulation
                            thumb = ""
                            if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                                thumb = entry.media_thumbnail[0].get("url", "")
                            
                            # Simple validation that properties exist
                            assert isinstance(title, str)
                            
                    print(f"  👉 {matched_count}/{len(entries)} passaram pelo filtro.")
            except Exception as e:
                print(f"  ❌ Falha: {e}")

if __name__ == '__main__':
    # Set Windows event loop policy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(simulate_scan())
