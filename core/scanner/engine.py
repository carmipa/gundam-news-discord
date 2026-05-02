"""
Engine module - The main orchestration logic for the scanning process.
"""
import asyncio
import logging
import time
import aiohttp
import ssl
import certifi
from datetime import datetime
from typing import Dict, Any

import discord
from discord.ext import tasks

from settings import LOOP_MINUTES, LOOP_INTERVAL_STR
from utils.storage import p, load_json_safe, save_json_safe, load_config_cached
from core.stats import stats
from core.filters import match_intel

# Novas importacoes modularizadas
from .fetcher import load_sources, fetch_feed
from .processor import load_history, save_history, sanitize_link, parse_entry_dt, is_recent
from .notifier import create_embed

log = logging.getLogger("MaftyScanner")
scan_lock = asyncio.Lock()

async def run_scan_once(bot: discord.Client, trigger: str = "manual") -> None:
    """Executes a single scanning cycle."""
    if scan_lock.locked():
        log.info(f"Scan skipped (already running). Trigger: {trigger}")
        return

    async with scan_lock:
        log.info(f"Starting scan (trigger={trigger})...")
        config = load_config_cached({})
        if not config: return

        urls = load_sources()
        state_file = p("state.json")
        state = load_json_safe(state_file, {})
        state.setdefault("dedup", {})
        state.setdefault("http_cache", {})
        
        history_list, history_set = load_history()
        
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        
        sent_count = 0
        cache_hits = 0
        
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks_list = [fetch_feed(session, url, state["http_cache"]) for url in urls]
            results = await asyncio.gather(*tasks_list)
            
            for result in results:
                if not result: continue
                url, entries = result
                
                # Dedup per feed
                if url not in state["dedup"]: state["dedup"][url] = {}
                is_cold_start = not state["dedup"][url]
                
                for entry in entries[:10]:
                    link = sanitize_link(entry.get("link", ""))
                    if not link or link in history_set: continue
                    
                    # Dedup per guild (new logic)
                    if link in state["dedup"][url] and "LEGACY" in state["dedup"][url][link]:
                        continue

                    # Filter by date
                    entry_dt = parse_entry_dt(entry)
                    if not is_cold_start and not is_recent(entry_dt):
                        continue

                    posted_anywhere = False
                    if link not in state["dedup"][url]: state["dedup"][url][link] = []

                    for gid, gdata in config.items():
                        if gid in state["dedup"][url][link]: continue
                        
                        channel_id = gdata.get("channel_id")
                        if not channel_id: continue
                        
                        if not match_intel(str(gid), entry.get("title", ""), entry.get("summary", ""), config, source_url=url):
                            continue

                        channel = bot.get_channel(channel_id)
                        if not channel: continue

                        # Notify
                        try:
                            target_lang = gdata.get("language", "en_US")
                            embed = await create_embed(bot, entry, target_lang, config)
                            await channel.send(embed=embed)
                            
                            # Media handling
                            if any(d in link for d in ("youtube.com", "youtu.be", "twitch.tv")):
                                await channel.send(link)
                            
                            state["dedup"][url][link].append(str(gid))
                            posted_anywhere = True
                            sent_count += 1
                        except Exception as e:
                            log.error(f"Error sending to guild {gid}: {e}")

                    if posted_anywhere:
                        history_set.add(link)
                        history_list.append(link)

        # Cleanup and Save
        save_history(history_list)
        save_json_safe(state_file, state)
        
        stats.scans_completed += 1
        stats.news_posted += sent_count
        stats.last_scan_time = datetime.now()
        
        log.info(f"Scan finished. Sent: {sent_count}. Cache hits: {cache_hits}")

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
    log.info(f"Scheduler started ({LOOP_MINUTES} min).")
