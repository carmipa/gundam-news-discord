"""
Engine module - The main orchestration logic for the scanning process.
"""
import asyncio
import logging
import time
import aiohttp
import ssl
import certifi
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import discord
from discord.ext import tasks

from settings import (
    LOOP_MINUTES, 
    LOOP_INTERVAL_STR, 
    MAX_CONCURRENT_FEEDS,
    FEED_FETCH_JITTER_MIN,
    FEED_FETCH_JITTER_MAX,
    MAX_ENTRIES_PER_FEED,
    MAX_YOUTUBE_ENTRIES_PER_FEED,
)
from utils.storage import p, load_json_safe, save_json_safe, load_config_cached
from core.stats import stats
from core.filters import match_intel

# Novas importacoes modularizadas
from .fetcher import load_sources, fetch_feed
from .logutil import scan_verbose
from .processor import load_history, save_history, sanitize_link, parse_entry_dt, is_recent
from .notifier import create_embed
from core.html_monitor import check_official_sites

log = logging.getLogger("MaftyIntel.scanner")
scan_lock = asyncio.Lock()


def _log_next_run() -> None:
    """Próximo horário estimado após o fim de uma varredura (alinhado ao intervalo LOOP_MINUTES)."""
    nxt = datetime.now() + timedelta(minutes=LOOP_MINUTES)
    log.info(
        f"⏳ Aguardando próxima varredura às {nxt:%Y-%m-%d %H:%M:%S} "
        f"(em {LOOP_INTERVAL_STR})..."
    )

async def run_scan_once(bot: discord.Client, trigger: str = "manual") -> None:
    """Executes a single scanning cycle."""
    if scan_lock.locked():
        log.info(f"Scan skipped (already running). Trigger: {trigger}")
        return

    async with scan_lock:
        log.info(f"🔎 Iniciando varredura de inteligência... (trigger={trigger})")
        config = load_config_cached({})
        if not config: return

        sources = load_sources()
        scan_verbose(log, f"📋 [FILA] {len(sources)} fonte(s) RSS/agregada(s) carregada(s).")
        state_file = p("state.json")
        state = load_json_safe(state_file, {})
        state.setdefault("dedup", {})
        state.setdefault("http_cache", {})
        state.setdefault("html_monitor", {})
        
        history_list, history_set = load_history()
        
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        
        sent_count = 0
        cache_hits = 0
        
        async with aiohttp.ClientSession(connector=connector) as session:
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)
            
            async def throttled_fetch(src_obj):
                url_log = src_obj.get("url", "Desconhecida")
                scan_verbose(
                    log,
                    f"⏳ [SEMAFORO] {url_log} aguardando liberação na fila "
                    f"(máx. {MAX_CONCURRENT_FEEDS} simultâneos)...",
                )
                async with semaphore:
                    jitter = random.uniform(FEED_FETCH_JITTER_MIN, FEED_FETCH_JITTER_MAX)
                    scan_verbose(
                        log,
                        f"🎲 [JITTER] Aguardando {jitter:.2f}s antes de buscar: {url_log}",
                    )
                    await asyncio.sleep(jitter)
                    return await fetch_feed(session, src_obj, state["http_cache"])

            tasks_list = [throttled_fetch(src) for src in sources]
            results = await asyncio.gather(*tasks_list)
            
            for result in results:
                if not result: continue
                url, entries = result
                
                # Dedup per feed
                if url not in state["dedup"]: state["dedup"][url] = {}
                is_cold_start = not state["dedup"][url]
                
                is_youtube_feed = ("youtube.com" in url or "youtu.be" in url)
                max_items = (
                    MAX_YOUTUBE_ENTRIES_PER_FEED
                    if is_youtube_feed
                    else MAX_ENTRIES_PER_FEED
                )
                if is_youtube_feed and max_items <= 0:
                    max_items = len(entries)

                limit_label = "sem limite" if (is_youtube_feed and MAX_YOUTUBE_ENTRIES_PER_FEED <= 0) else str(max_items)
                scan_verbose(
                    log,
                    f"📊 [PROCESSANDO] Até {limit_label} entradas de {len(entries)} em {url} "
                    f"(cold start: {is_cold_start})",
                )
                for entry in entries[:max_items]:
                    link = sanitize_link(entry.get("link", ""))
                    if not link or link in history_set: continue
                    
                    # Dedup per guild (new logic)
                    if link in state["dedup"][url] and "LEGACY" in state["dedup"][url][link]:
                        continue

                    # Filter by date
                    entry_dt = parse_entry_dt(entry)
                    if not is_cold_start and not is_recent(entry_dt):
                        scan_verbose(
                            log,
                            f"⏭️ [IGNORADO] Notícia antiga ou fora da janela: {link}",
                        )
                        continue

                    posted_anywhere = False
                    if link not in state["dedup"][url]: state["dedup"][url][link] = []

                    for gid, gdata in config.items():
                        if gid in state["dedup"][url][link]: continue
                        
                        channel_id = gdata.get("channel_id")
                        if not channel_id: continue
                        
                        if not match_intel(
                            str(gid),
                            entry.get("title", ""),
                            entry.get("summary", ""),
                            config,
                            source_url=url,
                        ):
                            scan_verbose(
                                log,
                                f"🚫 [FILTRO] Item não passou em match_intel (guild={gid}): "
                                f"{(entry.get('title') or '')[:100]} | {link[:120]}",
                            )
                            continue

                        channel = bot.get_channel(channel_id)
                        if not channel: continue

                        # Notify
                        try:
                            target_lang = gdata.get("language", "en_US")
                            embed = await create_embed(bot, entry, target_lang, config, session=session)
                            
                            # ✨ Especial handling for YouTube (show the video player)
                            msg_content = None
                            if any(x in link for x in ["youtube.com", "youtu.be"]):
                                msg_content = f"🎥 **Assistir Vídeo:** {link}"
                                
                            await channel.send(content=msg_content, embed=embed)
                            
                            # Media handling
                            if any(d in link for d in ("youtube.com", "youtu.be", "twitch.tv")):
                                await channel.send(link)

                            if any(x in link for x in ("youtube.com", "youtu.be")):
                                title_snip = (entry.get("title") or "")[:140]
                                log.info(
                                    f"🎥 [YOUTUBE POST] guild={gid} canal={channel_id} "
                                    f"| {title_snip} | {link}"
                                )

                            state["dedup"][url][link].append(str(gid))
                            posted_anywhere = True
                            sent_count += 1
                        except Exception as e:
                            log.error(f"Error sending to guild {gid}: {e}")

                    if posted_anywhere:
                        history_set.add(link)
                        history_list.append(link)

            # --- HTML MONITOR (Official Sites) ---
            log.info("🔎 Verificando sites oficiais (HTML Watcher)...")
            html_updates, new_html_state = await check_official_sites(state["html_monitor"])
            state["html_monitor"] = new_html_state
            
            for update in html_updates:
                # Trata atualizações de HTML como entradas de feed para processamento uniforme
                # check_official_sites já retorna dicts compatíveis com create_embed
                for gid, gdata in config.items():
                    channel_id = gdata.get("channel_id")
                    if not channel_id: continue
                    
                    # Filtra por palavras-chave (opcional, mas recomendado)
                    if not match_intel(str(gid), update.get("title", ""), update.get("summary", ""), config):
                        continue
                        
                    channel = bot.get_channel(int(channel_id))
                    if not channel: continue
                    
                    try:
                        target_lang = gdata.get("language", "en_US")
                        # Para sites oficiais, passamos um entry fake
                        embed = await create_embed(bot, update, target_lang, config, session=session)
                        await channel.send(embed=embed)
                        sent_count += 1
                    except Exception as e:
                        log.error(f"Error sending HTML update to guild {gid}: {e}")

        # Cleanup and Save
        save_history(history_list)
        save_json_safe(state_file, state)
        
        stats.scans_completed += 1
        stats.news_posted += sent_count
        stats.last_scan_time = datetime.now()
        
        log.info(
            f"✅ Varredura concluída. (enviadas={sent_count}, cache_hits={cache_hits}, trigger={trigger})"
        )
        _log_next_run()

def start_scheduler(bot: discord.Client):
    @tasks.loop(minutes=LOOP_MINUTES)
    async def intelligence_gathering():
        try:
            await run_scan_once(bot, trigger="loop")
        except Exception as e:
            log.exception(f"Loop error: {e}")

    @intelligence_gathering.before_loop
    async def _before(): await bot.wait_until_ready()
    
    intelligence_gathering.start()
    log.info(
        f"🛰️ Scanner de Inteligência ativado! Ciclo: {LOOP_INTERVAL_STR} "
        f"({LOOP_MINUTES} min entre execuções do loop)."
    )
    _log_next_run()
