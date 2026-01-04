"""
Cache utilities - HTTP caching with ETag and Last-Modified support.
"""
from typing import Dict, Any
from .storage import load_json_safe, save_json_safe, p


def load_http_state() -> Dict[str, Dict[str, str]]:
    """
    Carrega state.json com ETags e Last-Modified por URL.
    
    Returns:
        Dict com formato: {"https://feed.com": {"etag": "abc123", "last_modified": "..."}}
    """
    return load_json_safe(p("state.json"), {})


def save_http_state(state: Dict[str, Dict[str, str]]) -> None:
    """
    Salva cache de ETags e Last-Modified.
    
    Args:
        state: Dicionário de estados HTTP por URL
    """
    save_json_safe(p("state.json"), state)


def get_cache_headers(url: str, state: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """
    Retorna headers de cache para uma URL se disponíveis.
    
    Args:
        url: URL do feed
        state: Estado HTTP carregado
    
    Returns:
        Headers If-None-Match e/ou If-Modified-Since se disponíveis
    """
    headers = {}
    url_state = state.get(url, {})
    
    if "etag" in url_state and url_state["etag"]:
        headers["If-None-Match"] = url_state["etag"]
    
    if "last_modified" in url_state and url_state["last_modified"]:
        headers["If-Modified-Since"] = url_state["last_modified"]
    
    return headers


def update_cache_state(url: str, response_headers: Any, state: Dict[str, Dict[str, str]]) -> None:
    """
    Atualiza state com ETags e Last-Modified da resposta HTTP.
    
    Args:
        url: URL do feed
        response_headers: Headers da resposta HTTP
        state: Estado HTTP a atualizar (modificado in-place)
    """
    if url not in state:
        state[url] = {}
    
    # Salva ETag se presente (case-insensitive)
    if "ETag" in response_headers:
        state[url]["etag"] = response_headers["ETag"]
    elif "etag" in response_headers:
        state[url]["etag"] = response_headers["etag"]
    
    # Salva Last-Modified se presente (case-insensitive)
    if "Last-Modified" in response_headers:
        state[url]["last_modified"] = response_headers["Last-Modified"]
    elif "last-modified" in response_headers:
        state[url]["last_modified"] = response_headers["last-modified"]
