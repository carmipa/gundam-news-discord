"""
Notifier module - Handles Discord embed construction and message dispatching.
"""
import logging
import discord
from datetime import datetime
from typing import Dict, Any, Tuple
from urllib.parse import urlparse

from utils.translator import translate_to_target, t
from utils.html import clean_html

log = logging.getLogger("CyberIntel")

def get_news_metadata(title: str) -> Tuple[str, discord.Color]:
    """Returns (prefix, color) based on cybersecurity keywords."""
    critical_kws = ["zero-day", "0-day", "exploit", "active attack", "critical rce", "ransomware attack", "major leak"]
    vuln_kws = ["cve-", "vulnerability", "patch", "security update", "advisory", "bug", "fix"]
    
    t_lower = title.lower()
    if any(k in t_lower for k in critical_kws):
        return ("🚨 **[CRITICAL]**", discord.Color.from_rgb(255, 0, 0))
    elif any(k in t_lower for k in vuln_kws) or "cve-" in t_lower:
        return ("🐛 **[VULN]**", discord.Color.from_rgb(255, 165, 0))
    
    return ("⚠️ **[ALERT]**", discord.Color.from_rgb(0, 255, 255))

async def create_embed(bot: discord.Client, entry: Any, target_lang: str, guild_lang_map: Dict[str, str]) -> discord.Embed:
    """Builds the CyberIntel styled embed."""
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
    
    # Thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        try:
            embed.set_thumbnail(url=entry.media_thumbnail[0].get("url"))
        except: pass
        
    return embed
