"""
OpenGraph utility - Extracts images from meta tags.
"""
import aiohttp
import logging
from bs4 import BeautifulSoup
from typing import Optional

log = logging.getLogger("MaftyIntel.scanner")

async def fetch_og_image(url: str, session: aiohttp.ClientSession) -> Optional[str]:
    """
    Fetches the OpenGraph or Twitter image from a URL article.
    """
    if not url or not url.startswith("http"):
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
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. OpenGraph
            og = soup.find("meta", attrs={"property": "og:image"}) or \
                 soup.find("meta", attrs={"name": "og:image"}) or \
                 soup.find("meta", attrs={"property": "og:image:secure_url"})
            
            if og and og.get("content"):
                return og["content"]
            
            # 2. Twitter Card
            tw = soup.find("meta", attrs={"name": "twitter:image"}) or \
                 soup.find("meta", attrs={"property": "twitter:image"})
            if tw and tw.get("content"):
                return tw["content"]
                
            # 3. Itemprop
            ip = soup.find("meta", attrs={"itemprop": "image"})
            if ip and ip.get("content"):
                return ip["content"]
            
            # 4. Link rel image_src
            ls = soup.find("link", rel="image_src")
            if ls and ls.get("href"):
                return ls["href"]

            return None
            
    except Exception as e:
        log.debug(f"OG fetch error for {url}: {e}")
        return None
