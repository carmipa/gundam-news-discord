
import json
import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

SOURCES_FILE = "sources.json"
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
    "https://p-bandai.jp/global_newpc.html"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}

async def get_youtube_rss_url(client, url):
    try:
        # Check if it's already an RSS feed or has channel_id
        parsed = urlparse(url)
        if "feeds/videos.xml" in url:
            return url
        
        # If it's a channel ID based URL
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) > 1 and path_parts[0] == "channel":
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={path_parts[1]}"
            
        print(f"🕵️ Fetching YouTube Channel ID for: {url}")
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        
        # Try to find channel_id in meta tags or canonical URL
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Meta tag search
        meta_id = soup.find("meta", itemprop="channelId")
        if meta_id:
            channel_id = meta_id["content"]
            print(f"   ✅ Found Channel ID (meta): {channel_id}")
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            
        # Regex search in scripts (fallback)
        id_match = re.search(r'"channelId":"(UC[\w-]+)"', resp.text)
        if id_match:
            channel_id = id_match.group(1)
            print(f"   ✅ Found Channel ID (regex): {channel_id}")
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

        print(f"   ❌ Could not find Channel ID for {url}")
        return None
    except Exception as e:
        print(f"   ❌ Error fetching YouTube ID: {e}")
        return None

def normalize_url(url):
    # Remove fragments
    u = urlparse(url)
    return u._replace(fragment="").geturl()

async def main():
    print("📂 Loading sources.json...")
    try:
        with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ sources.json not found!")
        return

    # Normalize existing sources for dedup
    existing_rss = set(normalize_url(u) for u in data.get("rss_feeds", []))
    existing_yt = set(normalize_url(u) for u in data.get("youtube_feeds", []))
    existing_html = set(normalize_url(u) for u in data.get("official_sites_reference_(not_rss)", []))
    
    all_existing = existing_rss | existing_yt | existing_html
    
    tasks = []
    
    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0) as client:
        for url in NEW_URLS:
            clean_url = normalize_url(url)
            
            # Simple dedup check
            if clean_url in all_existing:
                print(f"⚠️ Skipping duplicate: {clean_url}")
                continue
            
            # Categorize
            domain = urlparse(clean_url).netloc.lower()
            
            if "youtube.com" in domain or "youtu.be" in domain:
                # Need async resolution
                tasks.append((url, "youtube"))
            elif clean_url.endswith(".xml") or clean_url.endswith(".rss") or clean_url.endswith(".atom") or "feed" in clean_url:
                # Likely RSS
                print(f"➕ Adding RSS: {clean_url}")
                data["rss_feeds"].append(clean_url)
                all_existing.add(clean_url)
            else:
                # Default to HTML Monitor
                print(f"➕ Adding HTML Monitor: {clean_url}")
                data.setdefault("official_sites_reference_(not_rss)", []).append(clean_url)
                all_existing.add(clean_url)

        # Process YouTube tasks
        for url, _type in tasks:
            if _type == "youtube":
                rss_url = await get_youtube_rss_url(client, url)
                if rss_url:
                    if rss_url in existing_yt:
                         print(f"⚠️ YouTube Feed already exists: {rss_url}")
                    else:
                        print(f"➕ Adding YouTube Feed: {rss_url}")
                        data["youtube_feeds"].append(rss_url)
                        existing_yt.add(rss_url)

    print("💾 Saving sources.json...")
    with open(SOURCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())
