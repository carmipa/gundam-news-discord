import json
import os

def merge_sources():
    old_path = "scratch/old_sources.json"
    current_path = "sources.json"
    
    try:
        with open(old_path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
    except:
        with open(old_path, "r", encoding="utf-16") as f:
            old_data = json.load(f)
        
    # Extrair todas as URLs do formato antigo (que eram listas de strings)
    old_urls = set()
    for key in ["rss_feeds", "youtube_feeds", "official_sites_reference_(not_rss)"]:
        if key in old_data:
            for url in old_data[key]:
                if isinstance(url, str) and url.startswith("http"):
                    old_urls.add(url.strip())

    # Estrutura base da v2.7
    new_data = {
        "meta": {
            "version": "2.7",
            "generated": "2026-05-02",
            "description": "Base TOTAL e ABSOLUTA Mafty - Restauração completa de 150+ fontes históricas e novas."
        },
        "rss_feeds": [],
        "youtube_feeds": [],
        "tracker_feeds": [
            { "name": "Nyaa.si – Gundam 1080p", "url": "https://nyaa.si/?page=rss&q=gundam+1080p&c=1_2&f=0", "category": "tracker", "enabled": True },
            { "name": "Tokyo Toshokan – Gundam", "url": "https://www.tokyotosho.info/rss.php?terms=gundam&type=1&search=1", "category": "tracker", "enabled": True }
        ],
        "official_sites": [],
        "filters": {
            "positive_keywords": ["gundam", "gunpla", "mobile suit", "hathaway", "seed freedom", "uc engage", "gundam breaker", "sd gundam", "tamashii", "metal build", "p-bandai", "premium bandai", "gundam base"],
            "negative_keywords": ["bootleg", "fake", "lego", "transformers", "macross", "evangelion", "pokemon", "dragon ball", "kamen rider", "one piece"]
        }
    }

    # Adicionar fontes específicas novas que não estavam no antigo
    new_urls = [
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCPjmdJSt7kxP5jjkRVuI-7A", # Sunrise Music
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCpRh2xmGtaVhFVuyCB271pw", # Lantis
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCbJM_Y06iuUOl3hVPqYcvng", # Sawano
        "http://ryokutya2089.com/feed",
        "http://hayamimi-gunpla.com/feed",
    ]
    for u in new_urls: old_urls.add(u)

    # Distribuir URLs nas categorias do novo formato
    for url in sorted(list(old_urls)):
        obj = {"url": url}
        
        if "youtube.com/feeds" in url:
            new_data["youtube_feeds"].append(obj)
        elif "/feed" in url or ".rdf" in url or ".rss" in url or "alt=rss" in url or "atom.xml" in url:
            new_data["rss_feeds"].append(obj)
        else:
            new_data["official_sites"].append(obj)

    with open(current_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)
    
    print(f"Sucesso! {len(old_urls)} URLs únicas consolidadas no sources.json.")

if __name__ == "__main__":
    merge_sources()
