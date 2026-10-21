"""
Apresentação da imagem da notícia no embed: grande (set_image) ou miniatura.

Até 2026-10-21 só o YouTube saía com imagem grande; todo o resto ia para a
miniatura do canto, mesmo com foto de 1200x600 disponível. Medido no mesmo dia,
4 notícias por fonte: hayamimi 1200x600, Anime News Network 600x315, Reddit misto
(1200x630, 640x1137 e cortes de 140x140) e Google News SEMPRE a mesma imagem
300x300 — o logo do Google, que é o og:image da página de redirecionamento.
"""
import logging
import re
import struct
from collections import OrderedDict
from typing import Optional, Tuple
from urllib.parse import urlparse

import aiohttp

log = logging.getLogger("MaftyIntel.scanner")

# Abaixo disto, imagem grande sai borrada (esticada pelo Discord): fica miniatura.
LARGURA_MINIMA_GRANDE = 300
# Bytes lidos para descobrir as dimensões: o cabeçalho de JPEG/PNG/WebP/GIF cabe
# folgado; nunca se baixa a imagem inteira.
_BYTES_CABECALHO = 65536
_TIMEOUT_SONDA = aiohttp.ClientTimeout(total=8)
_CACHE_MAX = 512
_cache: "OrderedDict[str, Tuple[str, bool]]" = OrderedDict()

_REDDIT_PREVIEW = re.compile(r"^https://preview\.redd\.it/([A-Za-z0-9_-]+\.(?:jpe?g|png|gif|webp))\?", re.IGNORECASE)


def eh_link_do_google_news(link: str) -> bool:
    """
    True para link de notícia do Google News (news.google.com).

    O link aponta para uma página de redirecionamento do Google; o og:image dela
    é o logo do Google News, igual para TODA notícia. Buscar essa imagem só
    produzia o "G" colorido em cada card — e uma requisição a mais por notícia.
    """
    try:
        return (urlparse(link or "").hostname or "").lower() == "news.google.com"
    except ValueError:
        return False


def versao_cheia_do_reddit(url: Optional[str]) -> Optional[str]:
    """
    Troca o corte reduzido do Reddit pelo arquivo original.

    `preview.redd.it/<id>.jpeg?width=140&height=140&crop=...` é o recorte que o
    feed RSS entrega (140x140, medido); o original do mesmo arquivo mora em
    `i.redd.it/<id>.jpeg`. Devolve None quando a URL não é desse formato.
    """
    if not url:
        return None
    m = _REDDIT_PREVIEW.match(url.strip())
    return f"https://i.redd.it/{m.group(1)}" if m else None


def dimensoes(cabecalho: bytes) -> Optional[Tuple[int, int]]:
    """
    Largura e altura lidas do cabeçalho de PNG, JPEG, WebP ou GIF.

    PROPÓSITO DE NEGÓCIO:
        Decidir se a imagem aguenta ser exibida grande sem baixá-la inteira.

    INVARIANTES DO DOMÍNIO:
        - Só lê os bytes recebidos; nunca acessa rede nem disco.
        - Formato desconhecido ou cabeçalho truncado devolve None, nunca um
          tamanho inventado.

    COMPORTAMENTO EM CASO DE FALHA:
        Devolve None (sem levantar) para qualquer entrada não reconhecida.
    """
    b = cabecalho or b""
    try:
        if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
            w, h = struct.unpack(">II", b[16:24])
            return int(w), int(h)
        if b[:6] in (b"GIF87a", b"GIF89a") and len(b) >= 10:
            w, h = struct.unpack("<HH", b[6:10])
            return int(w), int(h)
        if b[:4] == b"RIFF" and b[8:12] == b"WEBP" and len(b) >= 30:
            tipo = b[12:16]
            if tipo == b"VP8X":
                return 1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")
            if tipo == b"VP8 ":
                w, h = struct.unpack("<HH", b[26:30])
                return w & 0x3FFF, h & 0x3FFF
            if tipo == b"VP8L" and len(b) >= 25:
                v = int.from_bytes(b[21:25], "little")
                return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
            return None
        if b[:2] == b"\xff\xd8":
            i = 2
            while i + 9 < len(b):
                if b[i] != 0xFF:
                    i += 1
                    continue
                marcador = b[i + 1]
                if marcador in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", b[i + 5:i + 9])
                    return int(w), int(h)
                if marcador in (0xD8, 0x01) or 0xD0 <= marcador <= 0xD7:
                    i += 2
                    continue
                i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    except (struct.error, IndexError):
        return None
    return None


async def _sondar(url: str, session: aiohttp.ClientSession) -> Optional[Tuple[int, int]]:
    """Baixa só o cabeçalho da imagem e devolve as dimensões; None se não der."""
    try:
        async with session.get(url, timeout=_TIMEOUT_SONDA, headers={"Range": f"bytes=0-{_BYTES_CABECALHO - 1}"}) as r:
            if r.status not in (200, 206):
                return None
            # `read(n)` devolve o que já chegou, ATÉ n — não exatamente n. Em
            # produção (2026-10-21) o primeiro pedaço tinha 16 KB e o marcador de
            # tamanho do JPEG estava em 23 KB, depois de 20 KB de EXIF: a imagem
            # de 1200x1600 virou "tamanho desconhecido" e saiu como miniatura.
            # Lê em laço até achar as dimensões, o teto ou o fim do corpo.
            lido = b""
            while len(lido) < _BYTES_CABECALHO:
                pedaco = await r.content.read(_BYTES_CABECALHO - len(lido))
                if not pedaco:
                    break
                lido += pedaco
                tamanho = dimensoes(lido)
                if tamanho:
                    return tamanho
            return dimensoes(lido)
    except Exception as e:
        log.debug(f"[IMG] Sonda de dimensão falhou para {url[:120]}: {type(e).__name__}: {e}")
        return None


async def apresentacao_da_imagem(url: str, session: Optional[aiohttp.ClientSession]) -> Tuple[str, bool]:
    """
    Escolhe a URL final e se a imagem vai GRANDE (True) ou como miniatura (False).

    PROPÓSITO DE NEGÓCIO:
        Aproveitar a foto da notícia em tamanho grande, como no bot de anime, sem
        esticar imagem pequena até ela borrar.

    INVARIANTES DO DOMÍNIO:
        - `url` já passou por `imagem_publicavel` (anti-SSRF); a versão cheia do
          Reddit é sempre `https://i.redd.it/...`, host público fixo.
        - Grande só com largura MEDIDA >= LARGURA_MINIMA_GRANDE.
        - Versão cheia do Reddit só substitui o corte se respondeu como imagem.
        - Uma sonda por URL: o resultado fica em cache (LRU de 512), porque o
          mesmo embed é montado uma vez por idioma.

    COMPORTAMENTO EM CASO DE FALHA:
        Sem sessão, sonda falha ou formato desconhecido: devolve (url, False) —
        a miniatura, que é exatamente o comportamento anterior. Nunca levanta.
    """
    if url in _cache:
        _cache.move_to_end(url)
        return _cache[url]

    resultado: Tuple[str, bool] = (url, False)
    if session is not None:
        cheia = versao_cheia_do_reddit(url)
        tamanho = await _sondar(cheia, session) if cheia else None
        if tamanho:
            resultado = (cheia, tamanho[0] >= LARGURA_MINIMA_GRANDE)
        else:
            tamanho = await _sondar(url, session)
            if tamanho:
                resultado = (url, tamanho[0] >= LARGURA_MINIMA_GRANDE)

        # Só se guarda o que foi decidido COM sessão: sem ela o resultado é o
        # padrão provisório, e uma chamada seguinte com sessão tem de sondar.
        _cache[url] = resultado
        if len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return resultado
