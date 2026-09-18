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

from utils.opengraph import fetch_og_image, imagem_publicavel

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
    except Exception as e:
        # Extrair id de vídeo é enfeite (miniatura); falhar aqui não impede o
        # envio. Mas o motivo fica registado: falha invisível é falha que ninguém
        # corrige.
        log.debug(f"Não foi possível extrair o id do vídeo de {link!r}: {type(e).__name__}: {e}")
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
        except Exception as e:
            log.debug(f"media_thumbnail em formato inesperado: {type(e).__name__}: {e}")
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


# Limites do Discord para embeds. Estourar qualquer um devolve
# `400 Bad Request (error code: 50035): Invalid Form Body` — e a notícia NUNCA sai.
# Medido em produção em 2026-08-30: o mesmo item falhou de hora em hora durante
# dias na guild 417746665219424277, porque a falha não marca o link no dedup e o
# ciclo seguinte tenta outra vez. Retentar para sempre um envio impossível.
#
# A causa concreta: o resumo é cortado a 2000 caracteres ANTES de traduzir, e a
# tradução EXPANDE — japonês para português cresce com folga, e 2000 caracteres
# de kanji viram muito mais que os 4096 permitidos na descrição.
_LIMITE_TITULO = 256
_LIMITE_DESCRICAO = 4096
_LIMITE_AUTOR = 256
_LIMITE_RODAPE = 2048
# O Discord também limita a SOMA de todos os campos textuais.
_LIMITE_TOTAL = 6000


def _limitar(texto: Any, maximo: int) -> str:
    """
    Corta um texto ao limite do Discord, sinalizando visivelmente que foi cortado.

    PROPÓSITO DE NEGÓCIO:
        Garante que o embed é aceite. Uma notícia truncada é lida; uma notícia
        recusada pela API não existe para o leitor.

    INVARIANTES DO DOMÍNIO:
        - O resultado NUNCA excede `maximo`, incluindo o marcador de corte.
        - Devolve sempre str: None e tipos inesperados viram "".
        - Texto dentro do limite sai intacto, sem marcador.

    COMPORTAMENTO EM CASO DE FALHA:
        Não levanta. `maximo` menor que o marcador degrada para um corte simples.
    """
    if texto is None:
        return ""
    if not isinstance(texto, str):
        texto = str(texto)
    if len(texto) <= maximo:
        return texto
    marcador = "…"
    if maximo <= len(marcador):
        return texto[:maximo]
    return texto[: maximo - len(marcador)] + marcador


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

    titulo_final = _limitar(f"{prefix} {t_translated}", _LIMITE_TITULO)
    descricao_final = _limitar(s_translated, _LIMITE_DESCRICAO)
    author_name = _limitar(t.get('embed.author', lang=target_lang), _LIMITE_AUTOR)
    domain = urlparse(link).netloc
    footer = _limitar(t.get('embed.source', lang=target_lang, source=domain), _LIMITE_RODAPE)

    # Teto da SOMA: o Discord recusa o embed inteiro se o total passar de 6000,
    # mesmo com cada campo dentro do seu limite. A descrição é a que cede.
    excedente = (
        len(titulo_final) + len(descricao_final) + len(author_name) + len(footer)
    ) - _LIMITE_TOTAL
    if excedente > 0:
        descricao_final = _limitar(
            descricao_final, max(0, len(descricao_final) - excedente)
        )

    embed = discord.Embed(
        title=titulo_final,
        description=descricao_final,
        url=link,
        color=color,
        timestamp=datetime.now()
    )

    icon_url = bot.user.display_avatar.url if bot.user and bot.user.display_avatar else None
    embed.set_author(name=author_name, icon_url=icon_url)
    embed.set_footer(text=footer)

    # 🖼️ Image Logic — reaproveita thumbnail resolvido pelo chamador, se houver.
    if thumbnail_url is _THUMB_UNSET:
        thumbnail_url = await resolve_thumbnail(entry, session)

    # Guarda: URL de imagem invalida faz o Discord recusar o EMBED INTEIRO
    # (50035) -- a noticia falharia em todas as guilds, nao entraria no dedup e o
    # ciclo repetiria para sempre. O notifier ja trata as causas de TAMANHO do
    # 50035; esta linha fecha o vetor de URL (portado do anime-news, 2026-09-18).
    # Noticia sem imagem e lida; recusada nao existe.
    imagem_ok = imagem_publicavel(thumbnail_url)
    if thumbnail_url and not imagem_ok:
        log.warning(
            f"[EMBED] Imagem descartada por URL invalida, "
            f"noticia segue sem ela: {str(thumbnail_url)[:120]}"
        )
    if imagem_ok:
        # Em vídeo, imagem maior melhora leitura no Discord.
        is_youtube = any(x in link for x in ["youtube.com", "youtu.be"])
        if is_youtube:
            embed.set_image(url=imagem_ok)
        else:
            embed.set_thumbnail(url=imagem_ok)

    return embed


