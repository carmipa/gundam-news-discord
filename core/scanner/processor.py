"""
Processor module - Handles link sanitization, date parsing, and deduplication.
"""
import logging
import time
from datetime import datetime, timezone
from dateutil import parser as dtparser
from typing import List, Set, Tuple, Dict, Any, Optional
from urllib.parse import urlparse, urlunparse

from utils.storage import p, load_json_safe, save_json_safe

log = logging.getLogger("CyberIntel")

def load_history() -> Tuple[List[str], Set[str]]:
    h = load_json_safe(p("history.json"), [])
    if not isinstance(h, list): h = []
    h = [x for x in h if isinstance(x, str)]
    return h, set(h)

def save_history(history_list: List[str], limit: int = 2000) -> None:
    save_json_safe(p("history.json"), history_list[-limit:])

def sanitize_link(link: str) -> str:
    """Removes tracking params while keeping essential ones."""
    try:
        parsed = urlparse(link)
        if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
            return link
            
        q_pairs = parsed.query.split('&')
        cleaned_pairs = [
            pair for pair in q_pairs 
            if not pair.startswith(('utm_', 'ref', 'source', 'fbclid', 'timestamp'))
            and pair 
        ]
        new_query = '&'.join(cleaned_pairs)
        
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    except Exception:
        return link

def parse_entry_dt(entry: Any) -> Optional[datetime]:
    """Robust date parsing from feed entries."""
    try:
        s = getattr(entry, "published", None) or getattr(entry, "updated", None)
        if s: return dtparser.isoparse(s)
        
        st = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if st: return datetime(*st[:6], tzinfo=timezone.utc)
    except Exception:
        pass
    return None

def is_recent(entry_dt: Optional[datetime], days_limit: int = 7) -> bool:
    if not entry_dt: return True
    now = datetime.now(entry_dt.tzinfo) if entry_dt.tzinfo else datetime.now()
    return (now - entry_dt).days <= days_limit
