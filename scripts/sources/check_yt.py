import json
import xml.etree.ElementTree as ET
from pathlib import Path
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCES_FILE = PROJECT_ROOT / "sources.json"
OUTPUT_FILE = PROJECT_ROOT / "yt_channels.txt"


def main():
    with SOURCES_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        for url in data.get("youtube_feeds", []):
            try:
                req = urllib.request.urlopen(url)
                xml_data = req.read()
                root = ET.fromstring(xml_data)
                title = root.find("{http://www.w3.org/2005/Atom}title").text
                out.write(f"TITLE: {title} URL: {url}\n")
            except Exception as e:
                out.write(f"Error reading {url}: {e}\n")


if __name__ == "__main__":
    main()
