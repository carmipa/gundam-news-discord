import feedparser
import ssl
from core.filters import match_intel

config = {"123": {"filters": ["todos", "gunpla", "musica"]}}

url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCl2aT0nRejTCQO_LHZAftBw"

if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

feed = feedparser.parse(url)

for entry in feed.entries:
    title = entry.get("title") or ""
    summary = entry.get("summary") or entry.get("description") or ""
    link = entry.get("link") or "" 
    print(f"TITLE: {title}")
    # print(f"SUMMARY: {summary[:100]}...")
    matched = match_intel("123", title, summary, config, url)
    print(f"MATCH: {matched}")
    if "9AVujlNBFbs" in link:
        print("^^^ FOUND THE TARGET VIDEO ^^^")
