"""
Logs detalhados da varredura (modo servidor / Raio-X) sem ativar DEBUG global.

Ative com SCAN_VERBOSE=1 no .env para ver SEMAFORO, JITTER, PROXY, CACHE, etc. em INFO.
"""
import logging
from typing import Any, Dict

from settings import SCAN_VERBOSE


def scan_verbose(logger: logging.Logger, msg: str) -> None:
    """INFO se SCAN_VERBOSE; caso contrário DEBUG (requer LOG_LEVEL=DEBUG para aparecer)."""
    if SCAN_VERBOSE:
        logger.info(msg)
    else:
        logger.debug(msg)


def scan_verbose_cache(logger: logging.Logger, url: str, cache_headers: Dict[str, Any]) -> None:
    """Evita INFO gigante com dict completo de headers."""
    if SCAN_VERBOSE:
        logger.info(f"📦 [CACHE] {url} (revalidação condicional / If-Modified)")
    else:
        logger.debug(f"📦 [CACHE] Usando headers de cache para {url}: {cache_headers}")
