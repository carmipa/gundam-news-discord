"""
Ferramenta manual: descobre o channelId de um vídeo do YouTube.

Uso: python scripts/dev/investigar_canal_youtube.py <url_do_video>

Morava em tests/test_channel.py e rodava a cada `pytest` (rede no import, sem
timeout). Não é teste: não afirma nada.
"""
import re
import sys
import urllib.request


def canal_do_video(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
    achado = re.search(r'"channelId":"(UC[\w-]+)"', html)
    return achado.group(1) if achado else ""


if __name__ == "__main__":
    alvo = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=9AVujlNBFbs"
    print("Channel ID:", canal_do_video(alvo) or "não encontrado")
