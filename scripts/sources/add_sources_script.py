import json
import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_FILE = PROJECT_ROOT / "sources.json"

NEW_URLS = [
    "https://p-bandai.com/us/",
    "https://en.gundam-official.com/news/jy757u7j45nlih4nip2rzfxn",
    "https://www.bandainamcoent.com/",
    "https://store.bandainamcoent.com/",
    "https://en.gundam-official.com/",
    "https://en.gundam-official.com/news",
    "https://en.gundam.info/content/special-collaboration/#",
    "https://www.youtube.com/@GundamInfo",
    "https://www.bandainamco.co.jp/en/gundam-next-future-pavilion/index.php",
    "https://www.bandainamco.co.jp/en/gundam-next-future-pavilion/withfans/index.php",
    "https://www.youtube.com/c/GUNDAM",
    "https://x.com/GUNDAMPAVILION",
    "https://global.bandai-hobby.net/es/series/gundam/",
    "https://global.bandai-hobby.net/es/",
    "https://en.gundam-official.com/series",
    "https://gundam-uce.ggame.jp/en/",
    "https://www.gundam-ab.com/",
    "http://gundam-ab.com/news/",
    "https://www.gundam-base.net/",
    "https://www.gundamplanet.com/",
    "https://www.gundam-zz.net/",
    "https://gundam.fandom.com/wiki/Mobile_Suit_Gundam",
    "https://www.instagram.com/mobilesuitgundam_oficial/",
    "https://en.gundam.info/about-gundam/series-pages/buildmetaverse/",
    "https://www.strict-g.com/",
    "https://p-bandai.jp/global_newpc.html",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )
}


async def get_youtube_rss_url(client: httpx.AsyncClient, url: str):
    try:
        parsed = urlparse(url)
        if "feeds/videos.xml" in url:
            return url

        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) > 1 and path_parts[0] == "channel":
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={path_parts[1]}"

        print(f"Buscando Channel ID para: {url}")
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        meta_id = soup.find("meta", itemprop="channelId")
        if meta_id:
            channel_id = meta_id["content"]
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

        id_match = re.search(r'"channelId":"(UC[\w-]+)"', resp.text)
        if id_match:
            channel_id = id_match.group(1)
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

        print(f"Nao foi possivel encontrar Channel ID para {url}")
        return None
    except Exception as e:
        print(f"Erro ao buscar YouTube ID: {e}")
        return None


def normalize_url(url: str):
    u = urlparse(url)
    return u._replace(fragment="").geturl()


async def main():
    print("Carregando sources.json...")
    try:
        with SOURCES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("sources.json nao encontrado.")
        return

    existing_rss = set(normalize_url(u) for u in data.get("rss_feeds", []))
    existing_yt = set(normalize_url(u) for u in data.get("youtube_feeds", []))
    existing_html = set(normalize_url(u) for u in data.get("official_sites_reference_(not_rss)", []))
    all_existing = existing_rss | existing_yt | existing_html
    tasks = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0) as client:
        for url in NEW_URLS:
            clean_url = normalize_url(url)
            if clean_url in all_existing:
                print(f"Pulando duplicado: {clean_url}")
                continue

            domain = urlparse(clean_url).netloc.lower()
            if "youtube.com" in domain or "youtu.be" in domain:
                tasks.append((url, "youtube"))
            elif clean_url.endswith((".xml", ".rss", ".atom")) or "feed" in clean_url:
                print(f"Adicionando RSS: {clean_url}")
                data["rss_feeds"].append(clean_url)
                all_existing.add(clean_url)
            else:
                print(f"Adicionando HTML monitor: {clean_url}")
                data.setdefault("official_sites_reference_(not_rss)", []).append(clean_url)
                all_existing.add(clean_url)

        for url, source_type in tasks:
            if source_type != "youtube":
                continue
            rss_url = await get_youtube_rss_url(client, url)
            if not rss_url:
                continue
            if rss_url in existing_yt:
                print(f"YouTube feed ja existe: {rss_url}")
                continue
            print(f"Adicionando YouTube feed: {rss_url}")
            data["youtube_feeds"].append(rss_url)
            existing_yt.add(rss_url)

    print("Salvando sources.json...")
    with SOURCES_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Concluido.")


if __name__ == "__main__":
    asyncio.run(main())
