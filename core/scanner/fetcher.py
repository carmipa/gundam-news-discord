"""
Fetcher module - Handles HTTP requests and RSS feed parsing with stealth techniques.
"""
import ssl
import asyncio
import logging
import aiohttp
import certifi
import feedparser
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urlparse

from settings import (
    HTTP_TIMEOUT,
    FEED_FETCH_MAX_ATTEMPTS,
    FEED_HTTP_TIMEOUT_MAX_SEC,
    FEED_FETCH_INTER_RETRY_DELAYS,
    FEED_FETCH_RETRY_BACKOFF_SEC,
    FEED_USER_AGENT,
)
from utils.storage import p, load_json_safe
from utils.security import validate_url
from utils.cache import get_cache_headers, update_cache_state

log = logging.getLogger("MaftyIntel.scanner")

# HTTP 4xx/5xx que costumam ser transitórios e merecem nova tentativa no mesmo URL
_FEED_RETRYABLE_STATUS = frozenset({403, 429, 502, 503, 504})


def _delay_before_feed_retry(attempt_index: int) -> float:
    """Pausa após falha na tentativa `attempt_index` (0 = após 1ª falha), alinhada a settings."""
    if attempt_index < len(FEED_FETCH_INTER_RETRY_DELAYS):
        return FEED_FETCH_INTER_RETRY_DELAYS[attempt_index]
    excess = attempt_index - len(FEED_FETCH_INTER_RETRY_DELAYS)
    return FEED_FETCH_RETRY_BACKOFF_SEC * (2 ** max(0, excess))


def load_sources() -> List[str]:
    sources_raw = load_json_safe(p("sources.json"), {})
    urls: List[str] = []
    
    if isinstance(sources_raw, dict):
        # We look into standard feed keys (v1 and v2 structures)
        keys_to_check = ["rss_feeds", "youtube_feeds", "reddit_feeds", "official_sites", "feeds", "sources"]
        for key in keys_to_check:
            val = sources_raw.get(key, [])
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.startswith("http"):
                        urls.append(item.strip())
                    elif isinstance(item, dict) and item.get("url"):
                        url = item["url"]
                        if isinstance(url, str) and url.startswith("http"):
                            urls.append(url.strip())
    
    # Unique preserving order
    return list(dict.fromkeys(urls))

def load_feed_fetch_overrides() -> Dict[str, Dict[str, Any]]:
    sources_raw = load_json_safe(p("sources.json"), {})
    if not isinstance(sources_raw, dict): return {}
    return sources_raw.get("feed_fetch_overrides", {})

async def fetch_feed(session: aiohttp.ClientSession, canonical_url: str, http_cache: dict) -> Optional[Tuple[str, List[Any]]]:
    """
    Fetches and parses a single feed with retries (delays e UA em settings).
    """
    overrides = load_feed_fetch_overrides().get(canonical_url, {})
    timeout_sec = min(float(overrides.get("http_timeout_sec", HTTP_TIMEOUT)), float(FEED_HTTP_TIMEOUT_MAX_SEC))
    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    
    for attempt in range(FEED_FETCH_MAX_ATTEMPTS):
        try:
            # Security check
            is_valid, _ = validate_url(canonical_url)
            if not is_valid: return None

            headers = {
                "User-Agent": FEED_USER_AGENT,
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
                    if resp.status in _FEED_RETRYABLE_STATUS and attempt < FEED_FETCH_MAX_ATTEMPTS - 1:
                        await asyncio.sleep(_delay_before_feed_retry(attempt))
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
                await asyncio.sleep(_delay_before_feed_retry(attempt))
            else:
                log.error(f"Failed to fetch {canonical_url} after {FEED_FETCH_MAX_ATTEMPTS} attempts.")
    
    return None
