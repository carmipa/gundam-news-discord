"""
HTML Monitor - Detects changes in static websites (Official Gundam Sites).
"""
import ssl
import logging
import hashlib
import asyncio
import aiohttp
import certifi
from typing import List, Dict, Tuple
from bs4 import BeautifulSoup

from utils.storage import p, load_json_safe, save_json_safe

log = logging.getLogger("MaftyIntel")

# Tags to ignore during hash calculation (noise reduction)
IGNORE_TAGS = ['script', 'style', 'meta', 'noscript', 'iframe', 'svg']
# Classes/IDs often used for ads or dynamic widgets
IGNORE_SELECTORS = ['.ad', '.advertisement', '.widget', '#clock', '.timestamp', '.cookie-consent']

async def fetch_page_hash(session: aiohttp.ClientSession, url: str) -> Tuple[str, str, str]:
    """
    Fetches a page, cleans it, and returns (url, title, hash).
    Returns (url, "", "") on failure.
    """
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                log.debug(f"HTML Monitor: {url} returned {resp.status}")
                return url, "", ""
            
            content = await resp.text(errors="ignore")
            
            # Parse and Clean
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove noise tags
            for tag in soup(IGNORE_TAGS):
                tag.decompose()
            
            # Remove noise classes (Safe attempt)
            for selector in IGNORE_SELECTORS:
                for match in soup.select(selector):
                    match.decompose()
            
            # Get text content only (ignoring HTML structure changes)
            text_content = soup.get_text(separator=' ', strip=True)
            
            # Hash calculation
            page_hash = hashlib.sha256(text_content.encode('utf-8')).hexdigest()
            title = soup.title.string.strip() if soup.title else "No Title"
            
            return url, title, page_hash

    except Exception as e:
        log.warning(f"HTML Monitor: Failed to fetch {url}: {e}")
        return url, "", ""

async def check_official_sites(current_state: Dict[str, str]) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    """
    Checks official sites for changes.
    Args:
        current_state: Dict {url: last_hash}
    Returns:
        (updates_list, new_state)
    """
    sources = load_json_safe(p("sources.json"), {})
    urls = sources.get("official_sites_reference_(not_rss)", [])
    
    if not urls:
        return [], current_state

    # SSL & Headers (Same as scanner.py)
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    
    updates = []
    new_state = current_state.copy()
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        tasks = [fetch_page_hash(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        for url, title, page_hash in results:
            if not page_hash:
                continue
                
            last_hash = current_state.get(url)
            
            # If no last hash (first run), just save it
            if not last_hash:
                new_state[url] = page_hash
                log.info(f"HTML Monitor: Initialized hash for {url}")
                continue
            
            # If hash changed, it's an update!
            if page_hash != last_hash:
                log.info(f"HTML Monitor: CHANGE DETECTED in {url}")
                updates.append({
                    "title": f"🔄 Update: {title}",
                    "link": url,
                    "summary": "Official site content has changed. Please check for new announcements."
                })
                new_state[url] = page_hash
    
    return updates, new_state
