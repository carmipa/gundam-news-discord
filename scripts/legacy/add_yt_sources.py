import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_FILE = PROJECT_ROOT / "sources.json"

KNOWN_IDS = {
    "@GundamInfo": "UCejtUitnpnf8Be-v5NuDSLw",
    "c/GUNDAM": "UC7wu64jFsV02bbu6UHUd7JA",
}


def update_sources():
    try:
        with SOURCES_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        current_yt = set(data.get("youtube_feeds", []))
        new_feeds = [
            f"https://www.youtube.com/feeds/videos.xml?channel_id={KNOWN_IDS['@GundamInfo']}",
            f"https://www.youtube.com/feeds/videos.xml?channel_id={KNOWN_IDS['c/GUNDAM']}",
        ]

        added = 0
        for feed in new_feeds:
            if feed in current_yt:
                print(f"Feed ja existe: {feed}")
                continue
            data["youtube_feeds"].append(feed)
            print(f"Adicionado YouTube Feed: {feed}")
            added += 1

        if added > 0:
            with SOURCES_FILE.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("sources.json atualizado.")
    except Exception as e:
        print(f"Erro: {e}")


if __name__ == "__main__":
    update_sources()
