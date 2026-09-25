"""
Ferramenta manual: mostra, entrada a entrada, se um feed do YouTube passa no filtro.

Uso: python scripts/dev/investigar_feed_youtube.py [url_do_feed]

Morava em tests/test_feed.py e rodava a cada `pytest`: baixava o feed no import
e DESLIGAVA a verificação TLS do processo inteiro dos testes
(`ssl._create_default_https_context = ssl._create_unverified_context`). A
verificação TLS fica ligada aqui também.
"""
import os
import sys

import feedparser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.filters import match_intel  # noqa: E402

CONFIG = {"123": {"filters": ["todos", "gunpla", "musica"]}}


def main(url: str) -> None:
    feed = feedparser.parse(url)
    for entry in feed.entries:
        titulo = entry.get("title") or ""
        resumo = entry.get("summary") or entry.get("description") or ""
        print(f"TITLE: {titulo}")
        print(f"MATCH: {match_intel('123', titulo, resumo, CONFIG, url)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         "https://www.youtube.com/feeds/videos.xml?channel_id=UCl2aT0nRejTCQO_LHZAftBw")
