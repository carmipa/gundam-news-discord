"""
Notifier module - Handles Discord embed construction and message dispatching.
"""
import logging
import aiohttp
import discord
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from utils.translator import translate_to_target, t
from utils.html import clean_html

from utils.opengraph import fetch_og_image

log = logging.getLogger("MaftyIntel.scanner")

def get_news_metadata(title: str) -> Tuple[str, discord.Color]:
    """Returns (prefix, color) based on Gundam news priority."""
    hot_kws = ["leak", "announcement", "new kit", "p-bandai", "exclusive", "release date", "unveiled"]
    info_kws = ["review", "unboxing", "tutorial", "custom", "build", "restock"]
    
    t_lower = title.lower()
    if any(k in t_lower for k in hot_kws):
        return ("🔥 **[HOT NEWS]**", discord.Color.from_rgb(255, 69, 0)) # OrangeRed
    elif any(k in t_lower for k in info_kws):
        return ("📘 **[INFO]**", discord.Color.from_rgb(30, 144, 255)) # DodgerBlue
    
    return ("📢 **[NEWS]**", discord.Color.from_rgb(0, 255, 127)) # SpringGreen

async def create_embed(bot: discord.Client, entry: Any, target_lang: str, guild_lang_map: Dict[str, str], session: Optional[aiohttp.ClientSession] = None) -> discord.Embed:
    """Builds the Gundam-styled embed with intelligent image fetching."""
    title = clean_html(entry.get("title", "No Title")).strip()
    summary = clean_html(entry.get("summary", "") or entry.get("description", "")).strip()[:2000]
    link = entry.get("link", "")
    
    # Translation
    t_translated = await translate_to_target(title, target_lang)
    s_translated = await translate_to_target(summary, target_lang)
    
    prefix, color = get_news_metadata(title)
    
    embed = discord.Embed(
        title=f"{prefix} {t_translated}"[:256],
        description=s_translated,
        url=link,
        color=color,
        timestamp=datetime.now()
    )
    
    author_name = t.get('embed.author', lang=target_lang)
    icon_url = bot.user.display_avatar.url if bot.user and bot.user.display_avatar else None
    embed.set_author(name=author_name, icon_url=icon_url)
    
    domain = urlparse(link).netloc
    footer = t.get('embed.source', lang=target_lang, source=domain)
    embed.set_footer(text=footer)
    
    # 🖼️ Image Logic
    thumbnail_url = None
    
    # 1. Try RSS standard thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        try:
            thumbnail_url = entry.media_thumbnail[0].get("url")
        except: pass
    elif "itunes_image" in entry:
         thumbnail_url = entry.itunes_image
    
    # 2. Smart Fallback (OpenGraph)
    is_youtube = any(x in link for x in ["youtube.com", "youtu.be"])
    if not thumbnail_url and session and link and not is_youtube:
        log.debug(f"Attempting OG fetch for: {link}")
        thumbnail_url = await fetch_og_image(link, session)
    
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
        
    return embed


