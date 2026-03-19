import json
import urllib.request
import xml.etree.ElementTree as ET

with open('sources.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('yt_channels.txt', 'w', encoding='utf-8') as out:
    for url in data.get('youtube_feeds', []):
        try:
            req = urllib.request.urlopen(url)
            xml_data = req.read()
            root = ET.fromstring(xml_data)
            title = root.find('{http://www.w3.org/2005/Atom}title').text
            out.write(f"TITLE: {title} URL: {url}\n")
        except Exception as e:
            out.write(f"Error reading {url}: {e}\n")
