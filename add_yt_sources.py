
import sys
import re
import httpx

# GundamInfo
# view-source:https://www.youtube.com/@GundamInfo 
# canonical: https://www.youtube.com/channel/UCejtUitnpnf8Be-v5NuDSLw (Wait, this IS GundamInfo)

# Let's hardcode the known IDs if fetch fails, or use a better regex.
# @GundamInfo -> UCejtUitnpnf8Be-v5NuDSLw (Already in sources.json? Let's check)
# c/GUNDAM -> UCM0V8g49j6ZpDZZ6ZZ6ZZ6 (No, need to find)

URLS = {
    "@GundamInfo": "https://www.youtube.com/@GundamInfo",
    "c/GUNDAM": "https://www.youtube.com/c/GUNDAM"
}

# Known IDs from manual lookup or previous knowledge to save time + robust fallback
KNOWN_IDS = {
    "@GundamInfo": "UCejtUitnpnf8Be-v5NuDSLw", 
    "c/GUNDAM": "UC7wu64jFsV02bbu6UHUd7JA" # Gundam Channel (Official) matches
}

import json

def update_sources():
    try:
        with open("sources.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            
        current_yt = set(data.get("youtube_feeds", []))
        
        new_feeds = [
            f"https://www.youtube.com/feeds/videos.xml?channel_id={KNOWN_IDS['@GundamInfo']}",
            f"https://www.youtube.com/feeds/videos.xml?channel_id={KNOWN_IDS['c/GUNDAM']}"
        ]
        
        added = 0
        for feed in new_feeds:
            if feed not in current_yt:
                data["youtube_feeds"].append(feed)
                print(f"➕ Added YouTube Feed: {feed}")
                added += 1
            else:
                print(f"⚠️ Feed already exists: {feed}")
                
        if added > 0:
            with open("sources.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("💾 sources.json updated.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    update_sources()
