import asyncio
import aiohttp
import feedparser
import logging
import ssl
import certifi
import sys
import os

# Force UTF-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.append(os.getcwd())

from core.scanner import load_sources, load_history
from core.filters import match_intel, _contains_any, GUNDAM_CORE, BLACKLIST
from utils.storage import load_json_safe, p

# Setup basic logging
logging.basicConfig(level=logging.INFO)

from utils.cache import load_http_state, get_cache_headers

async def debug_scan():
    print("=== DEBUG SCAN START ===")
    urls = load_sources()
    print(f"Loaded {len(urls)} sources.")
    
    history_list, history_set = load_history()
    print(f"Loaded history with {len(history_set)} items.")
    
    config = load_json_safe(p("config.json"), {})
    
    http_state = load_http_state()
    print(f"Loaded http_state with {len(http_state)} entries.")

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    base_headers = {"User-Agent": "Mozilla/5.0 MaftyIntel/2.1 Debug"}
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx), headers=base_headers) as session:
        for url in urls:
            print(f"\n--- Checking {url} ---")
            
            # Check if we have cache headers
            req_headers = get_cache_headers(url, http_state)
            if req_headers:
                print(f"    Using Cache Headers: {req_headers}")
            else:
                print(f"    No Cache Headers found.")

            try:
                # FIRST REQUEST: With Cache Headers (Simulate Bot)
                async with session.get(url, headers={**base_headers, **req_headers}) as resp:
                    print(f"    [Active Cache] Status: {resp.status}")
                    if resp.status == 304:
                        print("    -> 304 Not Modified. Bot skips this.")
                    
                    # If 304, we MUST fetch again without headers to see what we are missing
                    if resp.status == 304:
                        print("    -> Force fetching without cache headers to compare...")
                        async with session.get(url, headers=base_headers) as resp2:
                             print(f"    [Force Fetch] Status: {resp2.status}")
                             text = await resp2.text()
                    else:
                        text = await resp.text()

                if 'text' not in locals(): # Should handle non-200/non-304
                     continue

                feed = feedparser.parse(text)
                entries = getattr(feed, "entries", [])
                print(f"    Entries found: {len(entries)}")
                
                if not entries:
                    print(f"    WARN: No entries found for {url}")
                    continue

                for i, entry in enumerate(entries[:3]): # Check first 3 only
                    title = entry.get("title", "No Title")
                    link = entry.get("link", "No Link")
                    summary = entry.get("summary", "") or entry.get("description", "")
                    
                    print(f"    [{i}] Title: {title}")
                    print(f"        Link: '{link}'")
                    
                    if link in history_set:
                        print("        -> SKIPPED (In History - EXACT MATCH)")
                        continue
                    
                    # Check for partial match (URL params issue)
                    # Simple heuristic: check if base url matches any in history
                    # This is just for debug info
                    
                    print(f"        -> Testing Filters...")
                    content = f"{title} {summary}".lower()
                    
                    # Pre-check global blockers
                    from core.filters import _contains_any, GUNDAM_CORE, BLACKLIST
                    if _contains_any(content, BLACKLIST):
                         print(f"           [FAIL] BLACKLIST")
                         continue

                    if not _contains_any(content, GUNDAM_CORE):
                         print(f"           [FAIL] Missing GUNDAM_CORE")
                         continue
                         
                    passed_any = False
                    for gid, gdata in config.items():
                        if match_intel(str(gid), title, summary, config):
                            print(f"           [PASS] Matches guild {gid}")
                            passed_any = True
                                
                    if not passed_any:
                        print("        -> RESULT: SKIPPED (Filtered)")
                    else:
                        print("        -> RESULT: WOULD SEND (Missing in History)")

            except Exception as e:
                print(f"ERROR processing {url}: {e}")

if __name__ == "__main__":
    asyncio.run(debug_scan())
