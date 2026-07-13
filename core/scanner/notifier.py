"""
Notifier module - Handles Discord embed construction and message dispatching.
"""
import logging
import aiohttp
import discord
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from utils.translator import translate_to_target, t
from utils.html import clean_html

from utils.opengraph import fetch_og_image

log = logging.getLogger("MaftyIntel.scanner")


def _extract_youtube_video_id(link: str) -> Optional[str]:
    """Extracts YouTube video_id from watch/short/youtu.be URLs."""
    if not link:
        return None
    try:
        parsed = urlparse(link)
        host = parsed.netloc.lower()
        path = (parsed.path or "").strip("/")

        if "youtu.be" in host and path:
            return path.split("/")[0]

        if "youtube.com" in host:
            if path == "watch":
                q = parse_qs(parsed.query or "")
                video_id = (q.get("v") or [None])[0]
                return video_id
            if path.startswith("shorts/"):
                return path.split("/", 1)[1].split("/")[0]
            if path.startswith("embed/"):
                return path.split("/", 1)[1].split("/")[0]
    except Exception:
        return None
    return None


def _youtube_thumbnail_url(link: str) -> Optional[str]:
    """Builds a stable YouTube thumbnail URL without page scraping."""
    video_id = _extract_youtube_video_id(link)
    if not video_id:
        return None
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

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

# Sentinela: distingue "thumbnail não informado" (resolver) de "informado como None".
_THUMB_UNSET = object()


async def resolve_thumbnail(entry: Any, session: Optional[aiohttp.ClientSession] = None) -> Optional[str]:
    """
    Resolve a imagem do item (independente de idioma), então pode ser computada
    UMA vez por notícia e reaproveitada entre servidores/idiomas.
    Ordem: media_thumbnail/itunes → thumb do YouTube → OpenGraph (fallback).
    """
    link = entry.get("link", "") if hasattr(entry, "get") else ""
    thumbnail_url = None

    # 1. Try RSS standard thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        try:
            thumbnail_url = entry.media_thumbnail[0].get("url")
        except Exception:
            pass
    elif "itunes_image" in entry:
        thumbnail_url = entry.itunes_image

    # 2. Fallback específico para YouTube (sem scraping de HTML)
    is_youtube = any(x in link for x in ["youtube.com", "youtu.be"])
    if not thumbnail_url and is_youtube:
        thumbnail_url = _youtube_thumbnail_url(link)

    # 3. Smart Fallback (OpenGraph)
    if not thumbnail_url and session and link and not is_youtube:
        log.debug(f"Attempting OG fetch for: {link}")
        thumbnail_url = await fetch_og_image(link, session)

    return thumbnail_url


async def create_embed(bot: discord.Client, entry: Any, target_lang: str, guild_lang_map: Dict[str, str], session: Optional[aiohttp.ClientSession] = None, thumbnail_url: Any = _THUMB_UNSET) -> discord.Embed:
    """
    Builds the Gundam-styled embed.

    thumbnail_url: se informado (inclusive None), evita re-resolver a imagem — o
    chamador (engine) resolve uma vez por notícia e passa aqui, evitando fetch OG
    duplicado por servidor.
    """
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

    # 🖼️ Image Logic — reaproveita thumbnail resolvido pelo chamador, se houver.
    if thumbnail_url is _THUMB_UNSET:
        thumbnail_url = await resolve_thumbnail(entry, session)

    if thumbnail_url:
        # Em vídeo, imagem maior melhora leitura no Discord.
        is_youtube = any(x in link for x in ["youtube.com", "youtu.be"])
        if is_youtube:
            embed.set_image(url=thumbnail_url)
        else:
            embed.set_thumbnail(url=thumbnail_url)

    return embed


