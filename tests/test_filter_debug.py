import asyncio
from core.filters import match_intel

# Dummy config that allows everything ("todos")
config = {
    "123": {
        "filters": ["games", "filmes"]
    }
}

titles = [
    ("Mesa redonda com spoilers", "ネタバレありの座談会#2｜『機動戦士ガンダム 閃光のハサウェイ』", "https://www.youtube.com/watch?v=V7RHA30GTXY"),
    ("GBO2", "「機動戦士ガンダム　バトルオペレーション２」PlayStation® Battle Operation Information Bureau | Março de 2026", "https://www.youtube.com/watch?v=4NXpZM-T_yY"),
    ("Gundam Wing EP 34", "MOBILE SUIT GUNDAM WING HD REMASTER - Episode 34", "https://www.youtube.com/watch?v=yF3NbJ_w62Y")
]

for name, title, url in titles:
    result = match_intel("123", title, "desc", config, url)
    print(f"{name}: {result}")

