"""
Scanner module - Feed fetching and processing logic.
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
from urllib.parse import urlparse, urlunparse
import time
import os

import discord
from discord.ext import tasks

from settings import LOOP_MINUTES
from utils.storage import p, load_json_safe, save_json_safe
from utils.html import clean_html
from utils.cache import load_http_state, save_http_state, get_cache_headers, update_cache_state
from utils.translator import translate_to_target, t
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
    except:
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
    except:
        pass
    
    # Fallback para struct_time do feedparser
    try:
        st = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if st:
            return datetime(*st[:6], tzinfo=timezone.utc)
    except:
        pass
        
    return None

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
        base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)

        sent_count = 0
        cache_hits = 0
        
        MAX_CONCURRENT_FEEDS = 5
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)

        async def fetch_and_process_feed(session, url):
            nonlocal cache_hits, state
            
            async with semaphore:
                try:
                    if "youtube.com" in url or "youtu.be" in url:
                        await asyncio.sleep(2)
                        
                    request_headers = get_cache_headers(url, http_cache)
                    
                    async with session.get(url, headers=request_headers) as resp:
                        if resp.status == 304:
                            cache_hits += 1
                            log.debug(f"📦 Cache hit: {url} (304)")
                            return None
                        
                        if resp.status == 431:
                            log.warning(f"⚠️ Twitter/X Error: Header value too long (431) - {url}")
                            return None

                        update_cache_state(url, resp.headers, http_cache)
                        text = await resp.text(errors="ignore")
                    
                    loop = asyncio.get_running_loop()
                    feed = await loop.run_in_executor(None, lambda: feedparser.parse(text))
                    
                    entries = getattr(feed, "entries", []) or []
                    
                    if not entries and resp.status == 200:
                         log.warning(f"⚠️ Feed retornou 200 OK mas 0 entradas: {url}")
                         
                    return (url, entries)
                    
                except Exception as e:
                    log.error(f"❌ Falha ao baixar feed '{url}': {e}")
                    log.debug(f"Traceback feed '{url}':", exc_info=True)
                    return None

        async with aiohttp.ClientSession(connector=connector, headers=base_headers, timeout=timeout) as session:
            tasks = [fetch_and_process_feed(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
            
            for result in results:
                if result is None:
                    continue
                    
                url, entries = result
                
                # Cold Start Check para este feed específico
                # Se a URL não estiver no dedup, é um cold start ou reset deste feed
                is_cold_start = url not in state["dedup"]
                if is_cold_start:
                    log.info(f"❄️ [Cold Start] Detectado para {url}. Ignorando travas de tempo para os 3 primeiros posts.")
                    state["dedup"][url] = []
                
                feed_posted_count = 0
                
                for entry in entries:
                    link = entry.get("link") or "" 
                    if not link: continue
                    
                    link = sanitize_link(link)
                    
                    # 1. Verifica no dedup específico do site (Prioridade)
                    if link in state["dedup"][url]:
                        continue
                        
                    # 2. Verifica histórico global (Legado/Fallback)
                    if link in history_set:
                        # Adiciona ao novo dedup para consistência
                        state["dedup"][url].append(link)
                        continue

                    # Cold Start Limit Check overrules everything
                    if is_cold_start and feed_posted_count >= 3:
                         continue

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

                    # Verifica cada guild
                    for gid, gdata in config.items():
                        if not isinstance(gdata, dict): continue
                        
                        channel_id = gdata.get("channel_id")
                        if not isinstance(channel_id, int): continue

                        if not match_intel(str(gid), title, summary, config):
                            log.debug(f"🛡️ [Filtro] Guild {gid} bloqueou: {title[:50]}...")
                            continue
                        
                        # Envio (código de envio inalterado abaixo)
                        log.info(f"✨ [Match] Guild {gid} aprovou: {title[:50]}...")

                        channel = bot.get_channel(channel_id)
                        if channel is None:
                            log.warning(f"Canal {channel_id} não encontrado.")
                            continue

                        t_clean = clean_html(title).strip()
                        s_clean = clean_html(summary).strip()[:2000]

                        # Tradução
                        target_lang = "en_US"
                        if str(gid) in config and "language" in config[str(gid)]:
                            target_lang = config[str(gid)]["language"]
                        
                        t_translated = await translate_to_target(t_clean, target_lang)
                        s_translated = await translate_to_target(s_clean, target_lang)

                        media_domains = ("youtube.com", "youtu.be", "twitch.tv", "soundcloud.com", "spotify.com")
                        is_media = False
                        try:
                            if any(d in link for d in media_domains):
                                is_media = True
                        except: pass

                        try:
                            if is_media:
                                msg_content = f"**{t_translated}**\n{link}"
                                await channel.send(content=msg_content)
                            else:
                                embed = discord.Embed(
                                    title=t_translated[:256],
                                    description=s_translated,
                                    url=link,
                                    color=discord.Color.from_rgb(255, 0, 32),
                                    timestamp=datetime.now()
                                )
                                from utils.translator import t
                                author_name = t.get('embed.author', lang=target_lang)
                                embed.set_author(name=author_name, icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None)
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
                            if is_cold_start:
                                feed_posted_count += 1
                            
                            await asyncio.sleep(1)

                        except Exception as e:
                            log.exception(f"❌ Falha ao enviar no canal {channel_id}: {e}")

                    if posted_anywhere:
                        # Adiciona ao dedup específico e global
                        state["dedup"][url].append(link)
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
                    for gid, gdata in config.items():
                        if not isinstance(gdata, dict): continue
                        channel_id = gdata.get("channel_id")
                        if not channel_id: continue
                        channel = bot.get_channel(channel_id)
                        if channel:
                            await channel.send(f"⚠️ **MAFTY INTEL ALERT**\n{u_title}\n{u_link}")
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
    log.info(f"🔄 Agendador de tarefas iniciado ({LOOP_MINUTES} min).")
