import asyncio
import json
import sys
from pathlib import Path

import aiohttp
import feedparser

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.scanner import sanitize_link, parse_entry_dt, get_news_metadata
from core.filters import match_intel

SOURCES_FILE = PROJECT_ROOT / "sources.json"


async def simulate_scan():
    print("Iniciando simulacao do scanner...")
    try:
        with SOURCES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            sources = data.get("youtube_feeds", []) + data.get("rss_feeds", [])
    except Exception as e:
        print(f"Erro lendo sources.json: {e}")
        return

    dummy_config = {"1": {"filters": ["todos"], "language": "pt_BR"}}

    async with aiohttp.ClientSession() as session:
        for url in sources:
            print(f"Fetching {url}")
            try:
                async with session.get(url, timeout=10) as resp:
                    text = await resp.text(errors="ignore")
                    feed = feedparser.parse(text)
                    entries = getattr(feed, "entries", [])
                    print(f"  Encontrados {len(entries)} itens")

                    matched_count = 0
                    for entry in entries[:10]:
                        link = entry.get("link", "")
                        if not link:
                            continue
                        link = sanitize_link(link)

                        _ = parse_entry_dt(entry)
                        title = entry.get("title", "")
                        summary = entry.get("summary", "") or entry.get("description", "")

                        matched = match_intel("1", title, summary, dummy_config, source_url=url)
                        if matched:
                            matched_count += 1
                            get_news_metadata(title, link)

                            if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                                _ = entry.media_thumbnail[0].get("url", "")

                            assert isinstance(title, str)

                    print(f"  {matched_count}/{len(entries[:10])} passaram pelo filtro.")
            except Exception as e:
                print(f"  Falha: {e}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(simulate_scan())
