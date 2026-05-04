"""
HTML Monitor - Detects changes in static websites (Official Gundam Sites).
"""
import ssl
import logging
import hashlib
import asyncio
import httpx

import certifi
from typing import List, Dict, Tuple, Any
from bs4 import BeautifulSoup

from settings import CLOUDFLARE_PROXY_URL, MAX_CONCURRENT_FEEDS
from utils.storage import p, load_json_safe, save_json_safe
from utils.security import validate_url

log = logging.getLogger("MaftyIntel")

# Tags to ignore during hash calculation (noise reduction)
IGNORE_TAGS = ['script', 'style', 'meta', 'noscript', 'iframe', 'svg']
# Classes/IDs often used for ads or dynamic widgets
IGNORE_SELECTORS = ['.ad', '.advertisement', '.widget', '#clock', '.timestamp', '.cookie-consent']

async def fetch_page_hash(client: httpx.AsyncClient, url: str) -> tuple[str, str, str]:
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
        
        # URL final para a requisição (pode ser via proxy)
        request_url = url
        if CLOUDFLARE_PROXY_URL:
            request_url = f"{CLOUDFLARE_PROXY_URL}{url}"
            log.debug(f"🛡️ [PROXY HTML] Usando worker para contornar firewall em: {url}")
        else:
            log.debug(f"🌐 [HTML DIRETO] Baixando página: {url}")

        log.debug(f"🚀 [HTTP GET] Requisitando {request_url}")
        resp = await client.get(request_url, follow_redirects=True)
        log.debug(f"📥 [HTTP RESP] Status {resp.status_code} recebido de {url}")
        if resp.status_code != 200:
            if resp.status_code == 403:
                log.warning(f"🚫 Acesso Negado HTML Monitor (403): O site '{url}' bloqueou o bot.")
            elif resp.status_code == 404:
                log.warning(f"👻 Não Encontrado HTML Monitor (404): O site '{url}' parece não existir mais.")
            elif resp.status_code == 429:
                log.warning(f"⏳ Rate Limit HTML Monitor (429): Servidor do site '{url}' pediu para aguardar.")
            elif resp.status_code >= 500:
                log.warning(f"🔥 Erro de Servidor HTML Monitor ({resp.status_code}): O site '{url}' está instável/caiu.")
            else:
                log.warning(f"⚠️ Erro HTTP HTML Monitor ({resp.status_code}): Falha ao acessar '{url}'.")
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
        log.debug(f"🧹 [PARSE HTML] HTML limpo para {url}. Tamanho do texto resultante: {len(text_content)} bytes")
        
        # Hash calculation
        page_hash = hashlib.sha256(text_content.encode('utf-8')).hexdigest()
        title = soup.title.string.strip() if soup.title else "No Title"
        log.debug(f"🔐 [HASH] Hash gerado para {url}: {page_hash[:8]}...")
        
        return url, title, page_hash

    except httpx.RequestError as e:
        log.warning(f"🌐 Erro de conexão no HTML Monitor para '{url}': {e}")
        return url, "", ""
    except Exception as e:
        log.warning(f"⚠️ Erro inesperado no HTML Monitor para '{url}': {type(e).__name__}: {e}", exc_info=True)
        return url, "", ""


def _html_monitor_urls_from_sources(sources: Dict[str, Any]) -> List[str]:
    """Legacy official_sites_reference_(not_rss) + official_sites (lista de dicts ou strings)."""
    out: List[str] = []
    for block in (
        sources.get("official_sites_reference_(not_rss)", []),
        sources.get("official_sites", []),
    ):
        if not isinstance(block, list):
            continue
        for item in block:
            if isinstance(item, str) and item.startswith("http"):
                out.append(item.strip())
            elif isinstance(item, dict) and item.get("url"):
                u = item["url"]
                if isinstance(u, str) and u.startswith("http"):
                    out.append(u.strip())
    return list(dict.fromkeys(out))


async def check_official_sites(current_state: Dict[str, str]) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    """
    Checks official sites for changes with concurrency limiting.
    Args:
        current_state: Dict {url: last_hash}
    Returns:
        (updates_list, new_state)
    """
    sources = load_json_safe(p("sources.json"), {})
    urls = _html_monitor_urls_from_sources(sources if isinstance(sources, dict) else {})

    if not urls:
        return [], current_state

    # Headers: imitando navegador moderno
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1"
    }
    
    updates = []
    new_state = current_state.copy()
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)

    async with httpx.AsyncClient(headers=headers, timeout=30.0, verify=certifi.where()) as client:
        async def throttled_fetch(url):
            async with semaphore:
                # O monitor de HTML já é lento por natureza, o semáforo aqui é crucial
                return await fetch_page_hash(client, url)

        tasks = [throttled_fetch(url) for url in urls]
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
