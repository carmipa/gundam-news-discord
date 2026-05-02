"""
Fetcher module - Handles HTTP requests and RSS feed parsing with stealth techniques.
"""
import ssl
import asyncio
import logging
import random
import aiohttp
import certifi
import feedparser
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urlparse

from settings import (
    HTTP_TIMEOUT,
    FEED_FETCH_MAX_ATTEMPTS,
    FEED_HTTP_TIMEOUT_MAX_SEC,
    FEED_FIRST_DELAY_MAX_SEC,
    FEED_FETCH_INTER_RETRY_DELAYS,
    FEED_FETCH_RETRY_BACKOFF_SEC
)
from utils.storage import p, load_json_safe
from utils.security import validate_url
from utils.cache import get_cache_headers, update_cache_state

log = logging.getLogger("CyberIntel")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

def load_sources() -> List[str]:
    sources_raw = load_json_safe(p("sources.json"), {})
    urls: List[str] = []
    
    if isinstance(sources_raw, dict):
        for key in ("rss_feeds", "youtube_feeds", "feeds", "sources"):
            val = sources_raw.get(key, [])
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.startswith("http"):
                        urls.append(item.strip())
    
    # Unique preserving order
    return list(dict.fromkeys(urls))

def load_feed_fetch_overrides() -> Dict[str, Dict[str, Any]]:
    sources_raw = load_json_safe(p("sources.json"), {})
    if not isinstance(sources_raw, dict): return {}
    return sources_raw.get("feed_fetch_overrides", {})

async def fetch_feed(session: aiohttp.ClientSession, canonical_url: str, http_cache: dict) -> Optional[Tuple[str, List[Any]]]:
    """
    Fetches and parses a single feed with retries and stealth.
    """
    overrides = load_feed_fetch_overrides().get(canonical_url, {})
    timeout_sec = min(float(overrides.get("http_timeout_sec", HTTP_TIMEOUT)), float(FEED_HTTP_TIMEOUT_MAX_SEC))
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    
    for attempt in range(FEED_FETCH_MAX_ATTEMPTS):
        try:
            # Security check
            is_valid, _ = validate_url(canonical_url)
            if not is_valid: return None

            # Stealth Headers
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
                "Referer": f"{urlparse(canonical_url).scheme}://{urlparse(canonical_url).netloc}/"
            }
            
            # Merge cache headers
            headers.update(get_cache_headers(canonical_url, http_cache))
            
            async with session.get(canonical_url, headers=headers, timeout=timeout) as resp:
                if resp.status == 304:
                    return None # No changes
                
                if resp.status >= 400:
                    log.warning(f"HTTP {resp.status} for {canonical_url}")
                    if resp.status in (403, 429) and attempt < FEED_FETCH_MAX_ATTEMPTS - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return None

                update_cache_state(canonical_url, resp.headers, http_cache)
                text = await resp.text(errors="ignore")
                
                loop = asyncio.get_running_loop()
                feed = await loop.run_in_executor(None, lambda: feedparser.parse(text))
                return canonical_url, getattr(feed, "entries", [])

        except Exception as e:
            log.debug(f"Error fetching {canonical_url}: {e}")
            if attempt < FEED_FETCH_MAX_ATTEMPTS - 1:
                await asyncio.sleep(1)
            else:
                log.error(f"Failed to fetch {canonical_url} after {FEED_FETCH_MAX_ATTEMPTS} attempts.")
    
    return None
