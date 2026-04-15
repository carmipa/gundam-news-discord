"""
Scanner module - Feed fetching and processing logic.

Responsabilidades:
- Carregar sources (RSS/YouTube) e state (dedup, http_cache, html_hashes).
- Executar varredura: buscar feeds, aplicar filtros (match_intel), enviar notícias e alertas de site.
- Rodar HTML Monitor para sites oficiais; salvar state e history ao final.
- Logs: INFO para início/fim de varredura e envios; WARNING para timeouts/canal ausente; ERROR para falhas de envio.
"""
import ssl
import asyncio
import logging
import feedparser
import aiohttp
import certifi
from datetime import datetime, timedelta, timezone
from dateutil import parser as dtparser
from typing import List, Set, Tuple, Dict, Any
from urllib.parse import urlparse, urlunparse, quote
import time
import os

import discord
from discord.ext import tasks

from settings import (
    LOOP_MINUTES,
    LOOP_INTERVAL_STR,
    HTTP_TIMEOUT,
    FEED_FETCH_MAX_ATTEMPTS,
    FEED_FETCH_RETRY_BACKOFF_SEC,
    FEED_FETCH_INTER_RETRY_DELAYS,
    FEED_HTTP_TIMEOUT_MAX_SEC,
    FEED_FIRST_DELAY_MAX_SEC,
)
from utils.storage import p, load_json_safe, save_json_safe
from utils.html import clean_html
from utils.cache import load_http_state, save_http_state, get_cache_headers, update_cache_state
from utils.translator import translate_to_target, t
from utils.security import validate_url
from core.stats import stats
from core.filters import match_intel
from core.html_monitor import check_official_sites

log = logging.getLogger("MaftyIntel")

# Lock global para impedir varreduras simultâneas
scan_lock = asyncio.Lock()


# =========================================================
# HISTORY MANAGEMENT
# =========================================================

def load_history() -> Tuple[List[str], Set[str]]:
    """Carrega history.json e devolve (lista, set) para dedupe rápido."""
    h = load_json_safe(p("history.json"), [])
    if not isinstance(h, list):
        log.warning("history.json inválido. Reiniciando histórico.")
        h = []
    
    # Filtra apenas strings para evitar erros
    h = [x for x in h if isinstance(x, str)]
    return h, set(h)


def save_history(history_list: List[str], limit: int = 2000) -> None:
    """Mantém histórico limitado para não crescer infinito."""
    save_json_safe(p("history.json"), history_list[-limit:])


# =========================================================
# SOURCE MANAGEMENT
# =========================================================

def load_sources() -> List[str]:
    """
    Carrega feeds de sources.json.
    Retorna lista única de URLs http(s).
    """
    sources_raw = load_json_safe(p("sources.json"), [])
    urls: List[str] = []

    def _add(u: Any):
        if isinstance(u, str):
            u = u.strip()
            if u.startswith(("http://", "https://")):
                urls.append(u)

    if isinstance(sources_raw, dict):
        for key in ("rss_feeds", "youtube_feeds", "official_sites", "feeds", "sources", "urls"):
            val = sources_raw.get(key, [])
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        _add(item)
                    elif isinstance(item, dict):
                        _add(item.get("url") or item.get("link"))

    elif isinstance(sources_raw, list):
        for item in sources_raw:
            if isinstance(item, str):
                _add(item)
            elif isinstance(item, dict):
                _add(item.get("url") or item.get("link"))

    # remove duplicados mantendo ordem
    seen = set()
    out: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# Cabeçalhos opcionais por feed (whitelist; chaves em sources.json podem ser qualquer capitalização)
_EXTRA_FEED_HEADER_KEYS = {
    "referer": "Referer",
    "origin": "Origin",
    "accept": "Accept",
    "accept-language": "Accept-Language",
    "accept-encoding": "Accept-Encoding",
    "cache-control": "Cache-Control",
    "pragma": "Pragma",
    # Alguns hosts (ex.: WordPress.com) fecham keep-alive de forma agressiva;
    # "close" evita reuso de conexão que às vezes gera "Server disconnected".
    "connection": "Connection",
}


def sanitize_feed_extra_headers(raw: Any) -> Dict[str, str]:
    """Filtra extra_headers do JSON contra whitelist e tamanho (anti-abuso)."""
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        key = k.strip().lower()
        if key not in _EXTRA_FEED_HEADER_KEYS:
            continue
        canon = _EXTRA_FEED_HEADER_KEYS[key]
        val = v.strip()
        if not val or len(val) > 512 or "\n" in val or "\r" in val:
            continue
        if canon == "Connection" and val.lower() != "close":
            continue
        out[canon] = val
    return out


def load_feed_fetch_overrides() -> Dict[str, Dict[str, Any]]:
    """
    Opcional em sources.json: chave feed_fetch_overrides →
    { "https://.../feed": { unstable, http_timeout_sec, first_request_delay_sec,
    extra_headers, note } }.
    """
    sources_raw = load_json_safe(p("sources.json"), [])
    if not isinstance(sources_raw, dict):
        return {}
    raw = sources_raw.get("feed_fetch_overrides")
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in raw.items():
        if isinstance(k, str) and k.startswith(("http://", "https://")):
            if isinstance(v, dict):
                out[k.strip()] = v
    return out


def load_feed_url_fallbacks() -> Dict[str, List[str]]:
    """
    Opcional em sources.json: feed_url_fallbacks →
    { "https://primario/feed/": ["https://fallback/feed/", ...] }.
    O dedup e http_cache do primário usam a URL canónica (chave); fallbacks só para GET.
    """
    sources_raw = load_json_safe(p("sources.json"), [])
    if not isinstance(sources_raw, dict):
        return {}
    raw = sources_raw.get("feed_url_fallbacks")
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, List[str]] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not k.startswith(("http://", "https://")):
            continue
        if not isinstance(v, list):
            continue
        chain = [
            x.strip()
            for x in v
            if isinstance(x, str) and x.strip().startswith(("http://", "https://"))
        ]
        if chain:
            out[k.strip()] = chain
    return out


def sanitize_link(link: str) -> str:
    """
    Remove parâmetros de rastreamento (utm_, etc) para evitar duplicação no histórico.
    Mantém parâmetros úteis (id, v, article).
    """
    try:
        parsed = urlparse(link)
        # Se for YouTube, não mexe na query string (pode quebrar v=...)
        if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
            return link
            
        # Filtra query params
        q_pairs = parsed.query.split('&')
        cleaned_pairs = [
            pair for pair in q_pairs 
            if not pair.startswith(('utm_', 'ref', 'source', 'fbclid', 'timestamp'))
            and pair # remove vazios
        ]
        new_query = '&'.join(cleaned_pairs)
        
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
    except Exception as e:
        log.debug(f"Erro ao sanitizar link '{link[:50]}...': {e}. Retornando link original.")
        return link

def parse_entry_dt(entry: Any) -> datetime:
    """
    Tenta extrair a data de publicação de forma robusta.
    Retorna datetime (com tzinfo se possível) ou None.
    """
    try:
        # Tenta dateutil primeiro (ISO 8601 do YouTube)
        s = getattr(entry, "published", None) or getattr(entry, "updated", None)
        if s:
            return dtparser.isoparse(s)
    except (ValueError, TypeError, AttributeError) as e:
        log.debug(f"Falha ao parsear data ISO8601: {e}. Tentando fallback...")
    
    # Fallback para struct_time do feedparser
    try:
        st = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if st:
            return datetime(*st[:6], tzinfo=timezone.utc)
    except (ValueError, TypeError, AttributeError) as e:
        log.debug(f"Falha ao parsear data struct_time: {e}")
        
    return None

# Cores e ícones por tipo de alerta (notícias de feed):
# - LEAK:   🚨 [LEAK]     → RGB(255, 69, 0)  (vermelho-laranja)
# - RUMOR:  🕵️ [RUMOR]    → RGB(255, 140, 0) (laranja escuro)
# - Padrão: (sem prefixo) → RGB(255, 0, 32)  (vermelho INTEL)
def get_news_metadata(title: str, url: str) -> tuple[str, discord.Color]:
    """
    Retorna (prefixo, cor) baseado em keywords e source url.
    Implementa a lógica de Leaks (🚨) e Rumores (🕵️).
    """
    leak_keywords = ["leak", "riiku", "vazamento", "rumor", "uwasa", "sokuhou", "速報", "リーク", "新型"]
    leak_sources = ["hobbynotoriko", "reddit.com/r/Gunpla", "dengeki", "weibo", "5ch"]

    title_lower = title.lower()

    # 1. LEAK — palavras-chave no título
    if any(k in title_lower for k in leak_keywords):
        return ("🚨 **[LEAK]**", discord.Color.from_rgb(255, 69, 0))

    # 2. RUMOR — fonte de rumores na URL
    elif any(src in url for src in leak_sources):
        return ("🕵️ **[RUMOR]**", discord.Color.from_rgb(255, 140, 0))

    # 3. Padrão — notícia normal
    return ("", discord.Color.from_rgb(255, 0, 32))

# =========================================================
# SCANNER LOGIC
# =========================================================

def _log_next_run() -> None:
    """Log explícito do próximo horário de varredura."""
    nxt = datetime.now() + timedelta(minutes=LOOP_MINUTES)
    log.info(f"⏳ Aguardando próxima varredura às {nxt:%Y-%m-%d %H:%M:%S} (em {LOOP_INTERVAL_STR})...")


async def run_scan_once(bot: discord.Client, trigger: str = "manual") -> None:
    """
    Executa UMA varredura completa.
    
    Args:
        bot: Instância do bot Discord
        trigger: Quem disparou ("loop", "dashboard", "manual")
    """

    if scan_lock.locked():
        log.info(f"⏭️ Varredura ignorada (já existe uma em execução). Trigger: {trigger}")
        return

    async with scan_lock:
        log.info(f"🔎 Iniciando varredura de inteligência... (trigger={trigger})")

        config = load_json_safe(p("config.json"), {})
        
        # Verifica se há guilds configuradas
        if not config or not any(isinstance(v, dict) and v.get("channel_id") for v in config.values()):
            log.warning("⚠️ Nenhuma guild configurada com 'channel_id'. Use /set_canal ou /dashboard para configurar.")
            _log_next_run()
            return
            
        urls = load_sources()
        feed_overrides = load_feed_fetch_overrides()
        feed_fallbacks = load_feed_url_fallbacks()

        # Injeta fallbacks automáticos do RSSHub para burlar bloqueios "404" do YouTube WAF
        for u in urls:
            if "youtube.com/feeds/videos.xml?channel_id=" in u.lower():
                cid = u.split("channel_id=")[-1].split("&")[0]
                rsshub_mirror = f"https://rsshub.app/youtube/channel/{cid}"
                if u not in feed_fallbacks:
                    feed_fallbacks[u] = []
                if rsshub_mirror not in feed_fallbacks[u]:
                    feed_fallbacks[u].append(rsshub_mirror)

        def _feed_timeout_for_url(url: str) -> aiohttp.ClientTimeout:
            total = float(HTTP_TIMEOUT)
            o = feed_overrides.get(url)
            if isinstance(o, dict) and o.get("http_timeout_sec") is not None:
                try:
                    total = float(o["http_timeout_sec"])
                except (TypeError, ValueError):
                    total = float(HTTP_TIMEOUT)
            total = max(1.0, min(total, float(FEED_HTTP_TIMEOUT_MAX_SEC)))
            return aiohttp.ClientTimeout(total=total)

        def _feed_is_unstable(url: str) -> bool:
            o = feed_overrides.get(url)
            return isinstance(o, dict) and bool(o.get("unstable"))

        def _feed_extra_headers(url: str) -> Dict[str, str]:
            o = feed_overrides.get(url)
            if not isinstance(o, dict):
                return {}
            return sanitize_feed_extra_headers(o.get("extra_headers"))

        def _feed_first_request_delay_sec(url: str) -> float:
            o = feed_overrides.get(url)
            if not isinstance(o, dict) or o.get("first_request_delay_sec") is None:
                return 0.0
            try:
                d = float(o["first_request_delay_sec"])
            except (TypeError, ValueError):
                return 0.0
            return max(0.0, min(d, float(FEED_FIRST_DELAY_MAX_SEC)))

        if not urls:
            log.warning(
                "Nenhuma URL válida em sources.json. "
                "Verifique o arquivo sources.json (chaves: rss_feeds, feeds, official_sites_reference_(not_rss), etc.)."
            )
            _log_next_run()
            return

        # =========================================================
        # UNIFIED STATE MANAGEMENT & AUTO-CLEANUP
        # =========================================================
        # Carrega o estado unificado (HTTP Cache + HTML Monitor + Deduplication + Cleanup)
        state_file = p("state.json")
        state = load_json_safe(state_file, {})
        
        # Garante estruturas básicas
        state.setdefault("dedup", {})
        state.setdefault("http_cache", {})
        state.setdefault("html_hashes", {})
        state.setdefault("last_cleanup", 0)

        # Regra de Auto-Limpeza (Cleanup) a cada 7 dias
        now_ts = time.time()
        last_clean = state.get("last_cleanup", 0)
        CLEANUP_INTERVAL = 604800  # 7 dias em segundos

        if now_ts - last_clean > CLEANUP_INTERVAL:
            log.info("🧹 [Auto-Cleanup] Executando limpeza de cache (Ciclo de 7 dias)")
            state["dedup"] = {}  # Limpa histórico de mensagens enviadas para forçar refresh se necessário
            state["last_cleanup"] = now_ts
            # Nota: Não limpamos http_cache para manter eficiência, apenas o dedup de posts
        
        # Referências locais para facilitar acesso
        http_cache = state["http_cache"]
        html_hashes = state["html_hashes"]
        # history_set ainda usado como fallback global, mas dedup por site é prioritário
        history_list, history_set = load_history()

        # SSL Configuration
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        import random
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]
        
        base_headers = {
            "User-Agent": random.choice(user_agents),
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/rss+xml;q=0.8,*/*;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Upgrade-Insecure-Requests": "1"
        }
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)

        sent_count = 0
        cache_hits = 0
        # Evita log repetido "Canal X não encontrado" por (guild, channel) por varredura
        invalid_channels_this_scan = set()

        MAX_CONCURRENT_FEEDS = 1
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)

        max_retry_index = max(0, FEED_FETCH_MAX_ATTEMPTS - 1)

        def _feed_retry_sleep(attempt_index: int) -> float:
            delays = FEED_FETCH_INTER_RETRY_DELAYS[:max_retry_index]
            if attempt_index < len(delays):
                return delays[attempt_index]
            if delays:
                return delays[-1]
            return min(FEED_FETCH_RETRY_BACKOFF_SEC * (2 ** attempt_index), 30.0)

        async def fetch_and_process_feed(session, canonical_url: str):
            nonlocal cache_hits, state

            async with semaphore:
                chain = [canonical_url] + feed_fallbacks.get(canonical_url, [])
                last_exc: BaseException | None = None
                last_status: int | None = None
                last_ctype: str | None = None

                for chain_idx, fetch_url in enumerate(chain):
                    if chain_idx > 0:
                        log.info(f"↪️ Fallback de feed ({canonical_url}): tentando {fetch_url}")

                    for attempt in range(FEED_FETCH_MAX_ATTEMPTS):
                        try:
                            is_valid, error_msg = validate_url(fetch_url)
                            if not is_valid:
                                log.warning(f"🔒 URL bloqueada por segurança: {fetch_url} - {error_msg}")
                                break

                            if attempt == 0 and ("youtube.com" in fetch_url or "youtu.be" in fetch_url):
                                import random
                                await asyncio.sleep(random.uniform(4.0, 7.0))

                            if attempt == 0:
                                delay_first = _feed_first_request_delay_sec(fetch_url)
                                if delay_first > 0:
                                    await asyncio.sleep(delay_first)

                            request_headers = get_cache_headers(fetch_url, http_cache)
                            if canonical_url not in state.get("dedup", {}):
                                request_headers = {}
                            extra_h = _feed_extra_headers(fetch_url)
                            if extra_h:
                                request_headers = {**request_headers, **extra_h}

                            if "youtube.com/feeds/videos.xml" in fetch_url.lower():
                                request_headers = {
                                    k: v
                                    for k, v in request_headers.items()
                                    if k.lower() not in ("if-none-match", "if-modified-since")
                                }

                            req_timeout = _feed_timeout_for_url(fetch_url)
                            async with session.get(
                                fetch_url, headers=request_headers, timeout=req_timeout
                            ) as resp:
                                status = resp.status
                                last_status = status
                                try:
                                    last_ctype = resp.headers.get("Content-Type", "") or None
                                except Exception:
                                    last_ctype = None

                                if status == 304:
                                    cache_hits += 1
                                    log.debug(f"📦 Cache hit: {fetch_url} (304)")
                                    return None

                                if status == 431:
                                    log.warning(
                                        f"⚠️ Twitter/X Error: Header value too long (431) - {fetch_url}"
                                    )
                                    return None

                                if status == 403:
                                    log.warning(
                                        f"🚫 Acesso Negado (403): '{fetch_url}'. "
                                        f"Content-Type: {last_ctype!r}. Tentando URL alternativa se houver."
                                    )
                                    break

                                if status == 404:
                                    log.warning(
                                        f"👻 Não Encontrado (404): '{fetch_url}'. "
                                        f"Content-Type: {last_ctype!r}"
                                    )
                                    break

                                if status == 429:
                                    log.warning(
                                        f"⏳ Rate Limit (429): '{fetch_url}'. "
                                        f"Content-Type: {last_ctype!r}"
                                    )
                                    break

                                if status >= 500:
                                    if attempt < FEED_FETCH_MAX_ATTEMPTS - 1:
                                        log.warning(
                                            f"⏳ Retry feed {attempt + 1}/{FEED_FETCH_MAX_ATTEMPTS} "
                                            f"(HTTP {status}): {fetch_url}"
                                        )
                                        await asyncio.sleep(_feed_retry_sleep(attempt))
                                        continue
                                    log.warning(
                                        f"🔥 HTTP {status} após {FEED_FETCH_MAX_ATTEMPTS} tentativas: {fetch_url} "
                                        f"(Content-Type: {last_ctype!r})"
                                    )
                                    break

                                if status >= 400:
                                    log.warning(
                                        f"⚠️ Erro HTTP ({status}): '{fetch_url}'. "
                                        f"Content-Type: {last_ctype!r}"
                                    )
                                    break

                                update_cache_state(fetch_url, resp.headers, http_cache)
                                text = await resp.text(errors="ignore")

                            loop = asyncio.get_running_loop()
                            feed = await loop.run_in_executor(None, lambda: feedparser.parse(text))

                            entries = getattr(feed, "entries", []) or []

                            if not entries and status == 200:
                                log.warning(
                                    f"⚠️ Feed 200 OK mas 0 entradas: {fetch_url} "
                                    f"(Content-Type: {last_ctype!r})"
                                )
                                break

                            return (canonical_url, entries)

                        except aiohttp.ClientError as e:
                            last_exc = e
                            if attempt < FEED_FETCH_MAX_ATTEMPTS - 1:
                                log.warning(
                                    f"⏳ Retry feed {attempt + 1}/{FEED_FETCH_MAX_ATTEMPTS} (conexão): "
                                    f"{fetch_url} — {e}"
                                )
                                await asyncio.sleep(_feed_retry_sleep(attempt))
                                continue
                            break

                        except asyncio.TimeoutError as e:
                            last_exc = e
                            if attempt < FEED_FETCH_MAX_ATTEMPTS - 1:
                                log.warning(
                                    f"⏳ Retry feed {attempt + 1}/{FEED_FETCH_MAX_ATTEMPTS} (timeout): {fetch_url}"
                                )
                                await asyncio.sleep(_feed_retry_sleep(attempt))
                                continue
                            break

                        except Exception as e:
                            log.error(
                                f"❌ Falha inesperada ao processar feed '{fetch_url}': "
                                f"{type(e).__name__}: {e}",
                                exc_info=True,
                            )
                            break

                detail_parts: List[str] = []
                if last_status is not None:
                    detail_parts.append(f"status={last_status}")
                if last_ctype:
                    detail_parts.append(f"Content-Type={last_ctype!r}")
                if last_exc is not None:
                    detail_parts.append(f"exc={type(last_exc).__name__}: {last_exc}")
                tail = f" ({'; '.join(detail_parts)})" if detail_parts else ""

                if _feed_is_unstable(canonical_url):
                    log.warning(
                        f"⚠️ Fonte instável — todas as URLs falharam para {canonical_url}{tail}"
                    )
                else:
                    log.error(f"❌ Falha ao baixar feed (incl. fallbacks): {canonical_url}{tail}")
                return None

        async with aiohttp.ClientSession(connector=connector, headers=base_headers, timeout=timeout) as session:
            tasks = [fetch_and_process_feed(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
            
            for result in results:
                if result is None:
                    continue
                    
                url, entries = result
                
                # Cold Start Check para este feed específico
                # Retro-compatibilidade: converte lista antiga para dict (link -> ["LEGACY"])
                if url in state["dedup"] and isinstance(state["dedup"][url], list):
                    state["dedup"][url] = {l: ["LEGACY"] for l in state["dedup"][url]}

                # Se a URL não estiver no dedup, é um cold start ou reset deste feed
                is_cold_start = url not in state["dedup"]
                if is_cold_start:
                    log.info(f"❄️ [Cold Start] Detectado para {url}. Processando todos os posts disponíveis na feed inicial (sem limite de quantidade).")
                    state["dedup"][url] = {}
                
                feed_posted_count = 0
                
                for entry in entries:
                    link = entry.get("link") or "" 
                    if not link: continue
                    
                    link = sanitize_link(link)
                    
                    # 1. Verifica no dedup geral (Se LEGACY, foi processado de forma global na versão antiga)
                    if link in state["dedup"][url] and "LEGACY" in state["dedup"][url][link]:
                        continue
                        
                    # 2. Verifica histórico global (Legado/Fallback)
                    if link in history_set:
                        # Adiciona ao novo dedup como LEGACY para acelerar próximos loops
                        if link not in state["dedup"][url]:
                            state["dedup"][url][link] = []
                        if "LEGACY" not in state["dedup"][url][link]:
                            state["dedup"][url][link].append("LEGACY")
                        continue

                    # Cold Start Limit Check overrules everything (Removido a pedido para liberar tudo)
                    # O limite 'feed_posted_count >= 3' existia para evitar flood no Discord.
                    # Manteve-se o feed_posted_count local para controle de insercoes no if final.

                    # Filtragem por data
                    entry_dt = parse_entry_dt(entry)
                    if entry_dt:
                        now = datetime.now(entry_dt.tzinfo) if entry_dt.tzinfo else datetime.now()
                        age = now - entry_dt
                        
                        # Se NÃO for Cold Start, aplica regra de 7 dias
                        if not is_cold_start:
                            if age.days > 7:
                                log.debug(f"👴 [Old] Ignorado (idade {age.days}d): {link}")
                                continue

                    title = entry.get("title") or ""
                    summary = entry.get("summary") or entry.get("description") or ""

                    posted_anywhere = False
                    if link not in state["dedup"][url]:
                        state["dedup"][url][link] = []

                    # Verifica cada guild
                    for gid, gdata in config.items():
                        gid_str = str(gid)
                        
                        # Verifica histórico per-guild (Anti-Flood e Evita Skips por Falha de Acesso)
                        if gid_str in state["dedup"][url][link]:
                            continue

                        if not isinstance(gdata, dict): continue
                        
                        channel_id = gdata.get("channel_id")
                        if not isinstance(channel_id, int): continue

                        if not match_intel(str(gid), title, summary, config, source_url=url):
                            log.debug(f"🛡️ [Filtro] Guild {gid} bloqueou: {title[:50]}... | fonte: {url}")
                            continue

                        # Valida canal antes de processar (evita trabalho inútil + log repetido)
                        channel = bot.get_channel(channel_id)
                        if channel is None:
                            key = (str(gid), channel_id)
                            if key not in invalid_channels_this_scan:
                                invalid_channels_this_scan.add(key)
                                guild_name = ""
                                try:
                                    g = bot.get_guild(int(gid))
                                    if g:
                                        guild_name = f" (servidor: {g.name})"
                                except (ValueError, TypeError):
                                    pass
                                log.warning(
                                    f"⚠️ Canal {channel_id} não encontrado — Guild {gid}{guild_name}. "
                                    f"Removendo do configuration automaticamente para evitar falhas contínuas."
                                )
                                config[str(gid)]["channel_id"] = None
                                save_json_safe(p("config.json"), config)
                            continue

                        # Envio (código de envio inalterado abaixo)
                        log.info(f"✨ [Match] Guild {gid} aprovou: {title[:50]}... | fonte: {url}")

                        t_clean = clean_html(title).strip()
                        s_clean = clean_html(summary).strip()[:2000]

                        # Tradução
                        target_lang = "en_US"
                        if str(gid) in config and "language" in config[str(gid)]:
                            target_lang = config[str(gid)]["language"]
                        
                        t_translated = await translate_to_target(t_clean, target_lang)
                        s_translated = await translate_to_target(s_clean, target_lang)

                        # Detecção de Leaks/Rumores (Refined Logic via Helper)
                        prefix, embed_color = get_news_metadata(t_clean, link)
                        
                        if prefix:
                            t_translated = f"{prefix} {t_translated}"


                        # Verifica se é mídia para expor o link e gerar player
                        media_domains = ("youtube.com", "youtu.be", "twitch.tv", "soundcloud.com", "spotify.com")
                        is_media = False
                        try:
                            if any(d in link for d in media_domains):
                                is_media = True
                        except Exception as e:
                            log.debug(f"Erro ao verificar domínio de mídia para '{link[:50]}...': {e}")

                        try:
                            # Sempre usa Embed para manter a identidade INTEL MAFTY
                            embed = discord.Embed(
                                title=t_translated[:256],
                                description=s_translated,
                                url=link,
                                color=embed_color,
                                timestamp=datetime.now()
                            )
                            from utils.translator import t
                            author_name = t.get('embed.author', lang=target_lang)
                            # Usa avatar do bot se disponível
                            icon_url = bot.user.avatar.url if bot.user and bot.user.avatar else None
                            embed.set_author(name=author_name, icon_url=icon_url)
                            
                            source_domain = urlparse(link).netloc
                            footer_text = t.get('embed.source', lang=target_lang, source=source_domain)
                            embed.set_footer(text=footer_text)
                            
                            if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                                try:
                                    thumb_url = entry.media_thumbnail[0].get("url")
                                    if thumb_url:
                                        embed.set_thumbnail(url=thumb_url)
                                except (IndexError, AttributeError, KeyError) as e:
                                    log.debug(f"Erro ao obter thumbnail da entrada: {e}")
                                except Exception as e:
                                    log.warning(f"Erro inesperado ao processar thumbnail: {e}")
                            
                            now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
                            
                            # Para mídias (YouTube, Twitch, etc.), precisamos de UM embed customizado
                            # + UMA mensagem separada apenas com o link para o Discord criar o player nativo.
                            if is_media:
                                msg_content = f"📺 **{t_translated}**\n🕒 Postado em: {now_str}"
                                embed_to_send = embed  # mantém cor e identidade do alerta
                            else:
                                msg_content = f"🕒 Postado em: {now_str}"
                                embed_to_send = embed
                            
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                url=link[:512],
                                label="Leia Mais",
                                emoji="📖"
                            ))
                            wa_text = f"Confira essa notícia:\n{t_translated}\n{link}"
                            view.add_item(discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                url=f"https://api.whatsapp.com/send?text={quote(wa_text)}"[:512],
                                label="WhatsApp",
                                emoji="🟢"
                            ))
                            
                            email_subj = t_translated[:100]
                            email_body = f"Confira essa notícia:\n{link}"
                            view.add_item(discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                url=f"https://mail.google.com/mail/?view=cm&fs=1&su={quote(email_subj)}&body={quote(email_body)}"[:512],
                                label="E-mail",
                                emoji="✉️"
                            ))
                            
                            # 1) Mensagem estilizada com embed + botões
                            await channel.send(content=msg_content, embed=embed_to_send, view=view)

                            # 2) Se for mídia, manda o link puro em outra mensagem para o Discord exibir o player nativo
                            if is_media:
                                await channel.send(link)

                            posted_anywhere = True
                            sent_count += 1
                            
                            # Registra o envio com sucesso para ESSA guilda especificamente
                            if gid_str not in state["dedup"][url][link]:
                                state["dedup"][url][link].append(gid_str)
                            
                            if is_cold_start:
                                feed_posted_count += 1
                                await asyncio.sleep(2.5)  # Atraso agressivo em cold start (Evita 429 Discord)
                            else:
                                await asyncio.sleep(1)

                        except discord.Forbidden as e:
                            log.error(f"🚫 Sem permissão para enviar mensagem no canal {channel_id} (guild {gid}): {e}")
                        except discord.HTTPException as e:
                            log.error(f"🌐 Erro HTTP ao enviar mensagem no canal {channel_id}: {e.status} - {e.text}")
                        except ValueError as e:
                            log.error(f"⚠️ Argumento inválido ao criar embed/mensagem: {e}")
                        except Exception as e:
                            log.exception(f"❌ Falha inesperada ao enviar no canal {channel_id} (guild {gid}): {type(e).__name__}: {e}")

                    if posted_anywhere:
                        # Adiciona ao global legacy apenas para consistência, se não estiver
                        if link not in history_set:
                            history_set.add(link)
                            history_list.append(link)

        # =========================================================
        # HTML MONITOR RUN (SITE WATCHER)
        # =========================================================
        try:
            log.info("🔎 Verificando sites oficiais (HTML Watcher)...")
            # Passa apenas o dicionário de hashes para o monitor
            # Se check_official_sites retornar updates, atualizamos o state principal
            html_updates, new_hashes = await check_official_sites(html_hashes)
            
            if html_updates:
                log.info(f"✨ {len(html_updates)} atualizações em sites oficiais detectadas!")
                state["html_hashes"] = new_hashes
                # Dispatch updates
                for update in html_updates:
                    u_title = update["title"]
                    u_link = update["link"]
                    u_summary = update.get("summary", "")
                    
                    for gid, gdata in config.items():
                        if not isinstance(gdata, dict): continue
                        
                        channel_id = gdata.get("channel_id")
                        if not channel_id: continue

                        try:
                            channel = bot.get_channel(int(channel_id))
                        except Exception as e:
                            log.warning(f"⚠️ Erro ao obter canal '{channel_id}' para guilda '{gid}': {e}")
                            channel = None
                        
                        # APLICA FILTRO DE INTELIGÊNCIA TAMBÉM NO MONITOR HTML
                        # Isso impede que sites genéricos (Mantan, Eiga) spammem mudanças irrelevantes
                        if not match_intel(str(gid), u_title, u_summary, config, source_url=u_link):
                            log.debug(f"🛡️ [Filtro HTML] Guild {gid} bloqueou site: {u_title[:50]}... | página: {u_link}")
                            continue

                        if channel:
                            now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
                            # Alerta: atualização de site — ⚠️ MAFTY INTEL ALERT, teal RGB(26,188,156)
                            SITE_UPDATE_COLOR = discord.Color.from_rgb(26, 188, 156)
                            site_embed = discord.Embed(
                                title=u_title[:256],
                                description=(
                                    f"🕒 **Postado em:** {now_str}\n\n"
                                    f"{u_summary or 'Content updated.'}\n\n{u_link}"
                                ),
                                url=u_link,
                                color=SITE_UPDATE_COLOR,
                                timestamp=datetime.now()
                            )
                            site_embed.set_author(
                                name="⚠️ MAFTY INTEL ALERT",
                                icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
                            )
                            site_embed.set_footer(text=f"🔄 Page updated | {now_str}")

                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                url=u_link[:512],
                                label="Leia Mais",
                                emoji="📖"
                            ))
                            wa_alert_text = f"Update:\n{u_title}\n{u_link}"
                            view.add_item(discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                url=f"https://api.whatsapp.com/send?text={quote(wa_alert_text)}"[:512],
                                label="WhatsApp",
                                emoji="🟢"
                            ))
                            view.add_item(discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                url=f"https://mail.google.com/mail/?view=cm&fs=1&su={quote('Site update')}&body={quote(u_link)}"[:512],
                                label="E-mail",
                                emoji="✉️"
                            ))
                            # 1) Mensagem com embed (estilo Site update)
                            await channel.send(embed=site_embed, view=view)
                            # 2) Mensagem só com o link para o Discord exibir preview com imagens/vídeos
                            await channel.send(u_link)
                            sent_count += 1
            else:
                 if new_hashes != html_hashes:
                     state["html_hashes"] = new_hashes
                     
        except Exception as e:
            log.error(f"❌ Erro no HTML Monitor: {e}")

        # Salva TUDO em um único arquivo de forma atômica/safe
        save_history(history_list)
        save_json_safe(state_file, state)
        # Removido save_http_state duplicado que causava race condition
        
        stats.scans_completed += 1
        stats.news_posted += sent_count
        stats.cache_hits_total += cache_hits
        stats.last_scan_time = datetime.now()
        
        log.info(f"✅ Varredura concluída. (enviadas={sent_count}, cache_hits={cache_hits}/{len(urls)}, trigger={trigger})")
        _log_next_run()


# =========================================================
# LOOP MANAGEMENT
# =========================================================

# Loop global que será iniciado pelo bot
loop_task = None

def start_scheduler(bot: discord.Client):
    """Inicia o loop agendado."""
    global loop_task
    
    @tasks.loop(minutes=LOOP_MINUTES)
    async def intelligence_gathering():
        try:
            await run_scan_once(bot, trigger="loop")
        except Exception as e:
            log.exception(f"🔥 Erro não tratado dentro do loop 'intelligence_gathering': {e}")
            # Importante: O loop do discord.ext.tasks pode parar se o erro subir.
            # Este try/except garante que o erro seja logado e a task continue no próximo intervalo.

    @intelligence_gathering.error
    async def intelligence_gathering_error(error):
        log.exception(f"💀 Erro Fatal no Loop (tasks.loop): {error}")
        # Tenta reiniciar o loop se ele tiver morrido
        # (Nota: intelligence_gathering.restart() não é método padrão documentado, melhor apenas logar)
    
    @intelligence_gathering.before_loop
    async def _before_loop():
        await bot.wait_until_ready()
    
    loop_task = intelligence_gathering
    loop_task.start()
    log.info(f"🔄 Agendador de tarefas iniciado ({LOOP_INTERVAL_STR}).")
