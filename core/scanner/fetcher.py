"""
Fetcher module - Handles HTTP requests and RSS feed parsing with stealth techniques.
"""
import asyncio
import logging
import aiohttp
import feedparser
from typing import Any, List, Dict, Tuple, Optional
from urllib.parse import urlparse

from settings import (
    HTTP_TIMEOUT,
    FEED_FETCH_MAX_ATTEMPTS,
    FEED_HTTP_TIMEOUT_MAX_SEC,
    FEED_FIRST_DELAY_MAX_SEC,
    FEED_FETCH_INTER_RETRY_DELAYS,
    FEED_FETCH_RETRY_BACKOFF_SEC,
    CLOUDFLARE_PROXY_URL,
    CLOUDFLARE_PROXY_SECRET,
)
from utils.storage import p, load_json_safe
from utils.security import validate_url
from utils.cache import get_cache_headers, update_cache_state
from core.stats import stats

from .logutil import scan_verbose, scan_verbose_cache

log = logging.getLogger("MaftyIntel.scanner")

# HTTP 4xx/5xx que costumam ser transitórios e merecem nova tentativa no mesmo URL
_FEED_RETRYABLE_STATUS = frozenset({403, 429, 502, 503, 504})

# Domínios que costumam precisar de proxy/evasão agressiva
_PROXY_CANDIDATE_DOMAINS = ["youtube.com", "youtu.be", "nyaa.si", "tokyotosho.info", "reddit.com"]

# Resultado interno de _fetch_feed_url
_OK = "ok"
_NOT_MODIFIED = "not_modified"
_FAIL = "fail"


def _delay_before_feed_retry(attempt_index: int) -> float:
    """Pausa após falha na tentativa `attempt_index` (0 = após 1ª falha), alinhada a settings."""
    if attempt_index < len(FEED_FETCH_INTER_RETRY_DELAYS):
        return FEED_FETCH_INTER_RETRY_DELAYS[attempt_index]
    excess = attempt_index - len(FEED_FETCH_INTER_RETRY_DELAYS)
    return FEED_FETCH_RETRY_BACKOFF_SEC * (2 ** max(0, excess))


def _sources_from_list(val: Any) -> List[Dict[str, Any]]:
    """Extrai objetos de fonte de listas com strings ou dicts. Preserva metadados."""
    out: List[Dict[str, Any]] = []
    if not isinstance(val, list):
        return out
    for item in val:
        if isinstance(item, str) and item.startswith("http"):
            out.append({"url": item.strip(), "metadata": {}})
            continue
        if isinstance(item, dict):
            if item.get("enabled") is False:
                continue
            u = item.get("url")
            if isinstance(u, str) and u.startswith("http"):
                # Preserva o item inteiro como metadados (exceto a URL que já extraímos)
                meta = item.copy()
                out.append({"url": u.strip(), "metadata": meta})
    return out


def load_sources() -> List[Dict[str, Any]]:
    """Carrega fontes de sources.json preservando metadados de configuração."""
    sources_raw = load_json_safe(p("sources.json"), {})
    all_sources: List[Dict[str, Any]] = []

    if isinstance(sources_raw, dict):
        keys_to_check = [
            "rss_feeds",
            "youtube_feeds",
            "reddit_feeds",
            "tracker_feeds",
            "feeds",
            "sources",
        ]
        for key in keys_to_check:
            all_sources.extend(_sources_from_list(sources_raw.get(key, [])))

    # Deduplicação baseada na URL
    seen_urls = set()
    unique_sources = []
    for src in all_sources:
        if src["url"] not in seen_urls:
            seen_urls.add(src["url"])
            unique_sources.append(src)

    return unique_sources


def _first_delay_seconds(metadata: Dict[str, Any]) -> float:
    """first_request_delay_sec da fonte (Nyaa/YouTube podem precisar), com teto de settings."""
    raw = metadata.get("first_request_delay_sec")
    if raw is None:
        return 0.0
    try:
        return max(0.0, min(float(raw), FEED_FIRST_DELAY_MAX_SEC))
    except (TypeError, ValueError):
        return 0.0


def _fallback_urls(metadata: Dict[str, Any]) -> List[str]:
    """URLs alternativas (fallbacks) da fonte, se o feed principal falhar."""
    raw = metadata.get("fallbacks")
    if not isinstance(raw, list):
        return []
    return [u.strip() for u in raw if isinstance(u, str) and u.strip().startswith("http")]


async def _fetch_feed_url(
    session: aiohttp.ClientSession,
    url: str,
    metadata: Dict[str, Any],
    http_cache: dict,
    timeout: aiohttp.ClientTimeout,
) -> Tuple[str, List[Any]]:
    """
    Busca UMA URL de feed com retentativas e evasão.
    Retorna (outcome, entries): _OK/_NOT_MODIFIED/_FAIL.
    """
    is_valid, _ = validate_url(url)
    if not is_valid:
        return _FAIL, []

    is_youtube = any(d in url for d in ["youtube.com", "youtu.be"])
    should_proxy = metadata.get("use_proxy", False) or any(d in url for d in _PROXY_CANDIDATE_DOMAINS)

    request_url = url
    if should_proxy and CLOUDFLARE_PROXY_URL:
        request_url = f"{CLOUDFLARE_PROXY_URL}{url}"
        scan_verbose(log, f"🛡️ [PROXY] Roteando via worker/Cloudflare → {url}")
    else:
        scan_verbose(log, f"🌐 [BUSCA DIRETA] {url}")

    for attempt in range(FEED_FETCH_MAX_ATTEMPTS):
        try:
            # User-Agent de navegador para feeds (evita bloqueios que barram bots)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": f"{urlparse(url).scheme}://{urlparse(url).netloc}/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Upgrade-Insecure-Requests": "1"
            }
            # Segredo do proxy só quando de fato roteando via worker (não vaza para a origem)
            if should_proxy and CLOUDFLARE_PROXY_URL and CLOUDFLARE_PROXY_SECRET:
                headers["X-Proxy-Secret"] = CLOUDFLARE_PROXY_SECRET

            cache_headers = get_cache_headers(url, http_cache)
            if cache_headers:
                scan_verbose_cache(log, url, cache_headers)
            headers.update(cache_headers)

            scan_verbose(
                log,
                f"🚀 [HTTP GET] tentativa {attempt + 1}/{FEED_FETCH_MAX_ATTEMPTS} → {request_url}",
            )
            async with session.get(request_url, headers=headers, timeout=timeout) as resp:
                scan_verbose(log, f"📥 [HTTP RESP] status {resp.status} ← {url}")
                if resp.status == 304:
                    stats.cache_hits_total += 1
                    scan_verbose(log, f"📦 [CACHE] 304 Not Modified (sem corpo novo): {url}")
                    return _NOT_MODIFIED, []

                if resp.status >= 400:
                    log.warning(f"HTTP {resp.status} para {url} (via proxy: {should_proxy})")

                    # YouTube/Trackers às vezes retornam 404/403 quando detectam bot; tratamos como retryable
                    retryable = resp.status in _FEED_RETRYABLE_STATUS or (is_youtube and resp.status == 404)

                    if retryable and attempt < FEED_FETCH_MAX_ATTEMPTS - 1:
                        delay = _delay_before_feed_retry(attempt)
                        scan_verbose(
                            log,
                            f"⏳ [RETRY] aguardando {delay:.1f}s antes da próxima tentativa → {url}",
                        )
                        await asyncio.sleep(delay)
                        continue
                    scan_verbose(log, f"❌ [ABORT] HTTP {resp.status} sem mais retries: {url}")
                    return _FAIL, []

                update_cache_state(url, resp.headers, http_cache)
                scan_verbose(log, f"✅ [HTTP OK] corpo recebido; parse RSS/XML: {url}")
                text = await resp.text(errors="ignore")

                scan_verbose(log, f"🧩 [PARSE] feedparser em executor → {url}")
                loop = asyncio.get_running_loop()
                feed = await loop.run_in_executor(None, feedparser.parse, text)
                entries = getattr(feed, "entries", [])
                entries_count = len(entries)
                scan_verbose(log, f"🎯 [FEED PRONTO] {entries_count} item(ns) em {url}")
                if is_youtube:
                    log.info(f"🎥 [YOUTUBE FEED] {entries_count} entrada(s) no Atom — {url}")
                return _OK, entries

        except Exception as e:
            scan_verbose(
                log,
                f"⚠️ [EXCEÇÃO] {url} (tentativa {attempt + 1}): {type(e).__name__}: {e}",
            )
            if attempt < FEED_FETCH_MAX_ATTEMPTS - 1:
                delay = _delay_before_feed_retry(attempt)
                scan_verbose(log, f"⏳ [RETRY EXCEÇÃO] {delay:.1f}s antes da próxima → {url}")
                await asyncio.sleep(delay)
            else:
                log.error(f"🔥 [FALHA TOTAL] Desistindo de {url} após {FEED_FETCH_MAX_ATTEMPTS} tentativas.")

    return _FAIL, []


async def fetch_feed(session: aiohttp.ClientSession, source_obj: Dict[str, Any], http_cache: dict) -> Optional[Tuple[str, List[Any]]]:
    """
    Busca e processa um feed: aplica first_request_delay_sec, tenta a URL principal
    e, em caso de falha, os fallbacks configurados. Mantém a URL canônica como chave
    (dedup/estatísticas), independentemente de qual fallback respondeu.
    """
    canonical_url = source_obj["url"]
    metadata = source_obj.get("metadata", {})

    # Prioridade para timeout: metadata > default, com teto de settings
    timeout_sec = float(metadata.get("http_timeout_sec", HTTP_TIMEOUT))
    timeout_sec = min(timeout_sec, float(FEED_HTTP_TIMEOUT_MAX_SEC))
    timeout = aiohttp.ClientTimeout(total=timeout_sec)

    # Atraso inicial opcional (fontes instáveis/anti-bot como Nyaa/YouTube)
    first_delay = _first_delay_seconds(metadata)
    if first_delay > 0:
        scan_verbose(log, f"⏱️ [FIRST DELAY] aguardando {first_delay:.1f}s antes de {canonical_url}")
        await asyncio.sleep(first_delay)

    urls_to_try = [canonical_url] + _fallback_urls(metadata)

    for i, candidate in enumerate(urls_to_try):
        if i > 0:
            scan_verbose(log, f"↩️ [FALLBACK] tentando URL alternativa {i}/{len(urls_to_try) - 1} para {canonical_url}: {candidate}")
        outcome, entries = await _fetch_feed_url(session, candidate, metadata, http_cache, timeout)
        if outcome == _OK:
            return canonical_url, entries
        if outcome == _NOT_MODIFIED:
            # 304: nada novo — não tenta fallback nem conta como falha.
            return None
        # _FAIL: tenta o próximo fallback, se houver

    # Esgotou principal + fallbacks
    stats.feeds_failed += 1
    return None
