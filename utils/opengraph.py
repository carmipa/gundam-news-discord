"""
OpenGraph utility - Extracts images from meta tags.
"""
import asyncio
import aiohttp
import logging
from bs4 import BeautifulSoup
from typing import Optional

from utils.security import validate_url

log = logging.getLogger("MaftyIntel.scanner")

async def fetch_og_image(url: str, session: aiohttp.ClientSession) -> Optional[str]:
    """
    Fetches the OpenGraph or Twitter image from a URL article.
    """
    if not url or not url.startswith("http"):
        return None

    # Anti-SSRF: só segue links http(s) para hosts públicos (o link vem de feeds externos)
    is_valid, error_msg = validate_url(url)
    if not is_valid:
        log.debug(f"OG fetch bloqueado por segurança para {url}: {error_msg}")
        return None

    try:
        # Simulate a social media crawler to trigger SSR for OG tags
        headers = {
            "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
        
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), headers=headers) as resp:
            if resp.status != 200:
                return None
            
            html = await resp.text()
            # Parse em executor: BeautifulSoup é CPU-bound e correria no event
            # loop, atrasando o heartbeat do gateway. Aqui o custo multiplica pelo
            # número de notícias enviadas no ciclo, não pelo catálogo.
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _extrair_imagem, html)

    except Exception as e:
        log.debug(f"OG fetch error for {url}: {e}")
        return None


def _extrair_imagem(html: str) -> Optional[str]:
    """
    Extrai a URL da imagem de destaque do HTML. SÍNCRONA de propósito.

    PROPÓSITO DE NEGÓCIO:
        Dá ao embed do Discord a miniatura da notícia. É enfeite: a notícia sai
        na mesma sem ela.

    INVARIANTES DO DOMÍNIO:
        - É CPU-bound e NÃO corre no event loop; quem chama usa run_in_executor.
        - Ordem de preferência fixa: OpenGraph > Twitter Card > itemprop >
          link rel=image_src. A primeira que existir ganha.

    COMPORTAMENTO EM CASO DE FALHA:
        Devolve None quando nenhuma tag serve. HTML malformado propaga para o
        chamador, que já converte em None — miniatura ausente nunca impede o envio.
    """
    soup = BeautifulSoup(html, 'html.parser')

    og = soup.find("meta", attrs={"property": "og:image"}) or          soup.find("meta", attrs={"name": "og:image"}) or          soup.find("meta", attrs={"property": "og:image:secure_url"})
    if og and og.get("content"):
        return og["content"]

    tw = soup.find("meta", attrs={"name": "twitter:image"}) or          soup.find("meta", attrs={"property": "twitter:image"})
    if tw and tw.get("content"):
        return tw["content"]

    ip = soup.find("meta", attrs={"itemprop": "image"})
    if ip and ip.get("content"):
        return ip["content"]

    ls = soup.find("link", rel="image_src")
    if ls and ls.get("href"):
        return ls["href"]

    return None
