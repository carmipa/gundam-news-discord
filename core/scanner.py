"""
Scanner module - Feed fetching and processing logic.
"""
import ssl
import asyncio
import logging
import feedparser
import aiohttp
import certifi
from datetime import datetime, timedelta
from typing import List, Set, Tuple, Dict, Any
from urllib.parse import urlparse

import discord
from discord.ext import tasks

from settings import LOOP_MINUTES
from utils.storage import p, load_json_safe, save_json_safe
from utils.html import clean_html
from utils.cache import load_http_state, save_http_state, get_cache_headers, update_cache_state
from utils.translator import translate_to_target, t
from core.stats import stats
from core.filters import match_intel

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


# =========================================================
# SCANNER LOGIC
# =========================================================

def _log_next_run() -> None:
    """Log explícito do próximo horário de varredura."""
    nxt = datetime.now() + timedelta(minutes=LOOP_MINUTES)
    log.info(f"⏳ Aguardando próxima varredura às {nxt:%Y-%m-%d %H:%M:%S} (em {LOOP_MINUTES} min)...")


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
            log.warning("⚠️ Nenhuma guild configurada com 'channel_id'. Use /dashboard para configurar.")
            _log_next_run()
            return
            
        urls = load_sources()
        if not urls:
            log.warning("Nenhuma URL válida em sources.json.")
            _log_next_run()
            return

        history_list, history_set = load_history()
        http_state = load_http_state()

        # SSL Configuration
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        base_headers = {"User-Agent": "Mozilla/5.0 MaftyIntel/2.1"}
        timeout = aiohttp.ClientTimeout(total=25)
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)

        sent_count = 0
        cache_hits = 0
        
        # Semáforo para concorrência
        MAX_CONCURRENT_FEEDS = 5
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)

        async def fetch_and_process_feed(session, url):
            nonlocal cache_hits, http_state
            
            async with semaphore:
                try:
                    request_headers = get_cache_headers(url, http_state)
                    
                    async with session.get(url, headers=request_headers) as resp:
                        if resp.status == 304:
                            cache_hits += 1
                            log.debug(f"📦 Cache hit: {url} (304)")
                            return None
                        
                        update_cache_state(url, resp.headers, http_state)
                        text = await resp.text(errors="ignore")
                    
                    # Parse do feed em thread pool (feedparser é bloqueante)
                    loop = asyncio.get_running_loop()
                    feed = await loop.run_in_executor(None, lambda: feedparser.parse(text))
                    
                    entries = getattr(feed, "entries", []) or []
                    return (url, entries)
                    
                except Exception as e:
                    log.error(f"Falha ao baixar feed '{url}': {e}")
                    return None

        async with aiohttp.ClientSession(connector=connector, headers=base_headers, timeout=timeout) as session:
            tasks = [fetch_and_process_feed(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
            
            for result in results:
                if result is None:
                    continue
                    
                url, entries = result
                
                for entry in entries:
                    link = entry.get("link") or ""
                    if not link or link in history_set:
                        continue

                    title = entry.get("title") or ""
                    summary = entry.get("summary") or entry.get("description") or ""

                    posted_anywhere = False

                    # Verifica cada guild
                    for gid, gdata in config.items():
                        if not isinstance(gdata, dict): continue
                        
                        channel_id = gdata.get("channel_id")
                        if not isinstance(channel_id, int): continue

                        if not match_intel(str(gid), title, summary, config):
                            continue

                        channel = bot.get_channel(channel_id)
                        if channel is None:
                            log.warning(f"Canal {channel_id} não encontrado na guild {gid}.")
                            continue

                        # Preparação do conteúdo
                        t_clean = clean_html(title).strip()
                        s_clean = clean_html(summary).strip()[:2000]

                        # Detecta idioma da guild
                        # Precisamos carregar o idioma configurado ou usar default
                        target_lang = "en_US"
                        if str(gid) in config and "language" in config[str(gid)]:
                            target_lang = config[str(gid)]["language"]
                        
                        # Tradução Dinâmica
                        # Se o idioma for en_US, o texto original (geralmente EN) é mantido se não houver tradução
                        # Mas como as fontes podem ser JP, sempre tentamos traduzir se não for o original
                        # Assumindo que translate_to_target lida com 'auto' source.
                        
                        t_translated = await translate_to_target(t_clean, target_lang)
                        s_translated = await translate_to_target(s_clean, target_lang)

                        try:
                            embed = discord.Embed(
                                title=t_translated[:256],
                                description=s_translated,
                                url=link,
                                color=discord.Color.from_rgb(255, 0, 32),
                                timestamp=datetime.now()
                            )
                            
                            # Strings localizadas
                            # Usa t.get com o idioma alvo
                            from utils.translator import t
                            
                            author_name = t.get('embed.author', lang=target_lang)
                            embed.set_author(
                                name=author_name,
                                icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
                            )
                            
                            source_domain = urlparse(link).netloc
                            footer_text = t.get('embed.source', lang=target_lang, source=source_domain)
                            embed.set_footer(text=footer_text)
                            
                            if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                                try:
                                    thumb_url = entry.media_thumbnail[0].get("url")
                                    if thumb_url:
                                        embed.set_thumbnail(url=thumb_url)
                                except: pass
                            
                            await channel.send(embed=embed)
                            posted_anywhere = True
                            sent_count += 1
                            await asyncio.sleep(1)

                        except Exception as e:
                            log.error(f"Falha ao enviar no canal {channel_id}: {e}")

                    if posted_anywhere:
                        history_set.add(link)
                        history_list.append(link)

        save_history(history_list)
        save_http_state(http_state)
        
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
        await run_scan_once(bot, trigger="loop")
    
    @intelligence_gathering.before_loop
    async def _before_loop():
        await bot.wait_until_ready()
    
    loop_task = intelligence_gathering
    loop_task.start()
    log.info(f"🔄 Agendador de tarefas iniciado ({LOOP_MINUTES} min).")
