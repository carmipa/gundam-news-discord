"""
HTML Monitor - Detects changes in static websites (Official Gundam Sites).
"""
import ssl
import logging
import hashlib
import asyncio
import httpx

# ... (imports unchanged)

# ... (constants unchanged)

async def fetch_page_hash(client: httpx.AsyncClient, url: str) -> Tuple[str, str, str]:
    """
    Fetches a page, cleans it, and returns (url, title, hash).
    Returns (url, "", "") on failure.
    """
    try:
        # Validação de segurança: anti-SSRF
        is_valid, error_msg = validate_url(url)
        if not is_valid:
            log.warning(f"🔒 URL bloqueada por segurança no HTML Monitor: {url} - {error_msg}")
            return url, "", ""
        
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            log.debug(f"HTML Monitor: {url} returned {resp.status_code}")
            return url, "", ""
        
        content = resp.text
        
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

    except httpx.RequestError as e:
        log.warning(f"🌐 Erro de conexão no HTML Monitor para '{url}': {e}")
        return url, "", ""
    except Exception as e:
        log.warning(f"⚠️ Erro inesperado no HTML Monitor para '{url}': {type(e).__name__}: {e}", exc_info=True)
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

    # Headers (Same as scanner.py)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    updates = []
    new_state = current_state.copy()
    
    # HTTPX Client with http2 support and large limits explicitly handled by default config usually
    # but we can verify later if needed. HTTPX handles large headers much better than aiohttp default.
    async with httpx.AsyncClient(headers=headers, timeout=30.0, verify=certifi.where()) as client:
        tasks = [fetch_page_hash(client, url) for url in urls]
        # Asyncio gather works same way
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
