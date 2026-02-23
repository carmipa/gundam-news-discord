"""
Verificação de todas as fontes em sources.json (RSS, YouTube, HTML Monitor).
Uso: python tests/test_sources.py   (a partir da raiz do projeto)
Gera: verification_results.txt com resultado por URL e resumo ao final.
"""
import json
import asyncio
import sys
from pathlib import Path

import httpx
import feedparser
from bs4 import BeautifulSoup

try:
    import certifi
except ImportError:
    certifi = None

# Ajuste encoding no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Raiz do projeto = pasta que contém sources.json
ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MaftyIntel-Verify/1.0; +https://github.com/carmipa/gundam-news-discord)"
}
SSL_VERIFY = certifi.where() if certifi else True

async def check_rss(client, url):
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        feed = feedparser.parse(resp.content)
        if feed.bozo and not getattr(feed, "entries", None):
            return False, f"Parse error: {getattr(feed, 'bozo_exception', 'invalid')}"
        entries = getattr(feed, "entries", []) or []
        if not entries:
            return False, "0 entradas (feed vazio)"
        last_date = "N/A"
        first = entries[0]
        for key in ("published", "updated", "created"):
            if getattr(first, key, None):
                last_date = getattr(first, key)
                break
        return True, f"OK — {len(entries)} entradas, último: {last_date}"
    except Exception as e:
        return False, f"Erro: {type(e).__name__}: {e}"

async def check_html(client, url):
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        if len(resp.text) < 200:
            return False, f"Conteúdo muito curto ({len(resp.text)} bytes)"
        soup = BeautifulSoup(resp.text, "html.parser")
        title = (soup.title.string or "").strip() if soup.title else "Sem título"
        return True, f"OK — título: {title[:60]}{'…' if len(title) > 60 else ''}"
    except Exception as e:
        return False, f"Erro: {type(e).__name__}: {e}"

async def main():
    print("📂 Carregando sources.json...")
    try:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ sources.json não encontrado. Execute a partir da raiz do projeto.")
        return

    out_path = ROOT / "verification_results.txt"
    stats = {"rss_ok": 0, "rss_fail": 0, "yt_ok": 0, "yt_fail": 0, "html_ok": 0, "html_fail": 0}

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=25.0, verify=SSL_VERIFY, follow_redirects=True
    ) as client:
        with open(out_path, "w", encoding="utf-8") as outfile:
            def log(text):
                print(text)
                outfile.write(text + "\n")

            log("=" * 60)
            log("REVISÃO DE FONTES — sources.json")
            log("=" * 60)

            # RSS
            log("\n--- FEEDS RSS ---")
            for url in data.get("rss_feeds", []):
                ok, msg = await check_rss(client, url)
                if ok:
                    stats["rss_ok"] += 1
                else:
                    stats["rss_fail"] += 1
                log(f"{'✅' if ok else '❌'} {url}\n   └── {msg}")

            # YouTube
            log("\n--- CANAIS YOUTUBE (RSS) ---")
            for url in data.get("youtube_feeds", []):
                ok, msg = await check_rss(client, url)
                if ok:
                    stats["yt_ok"] += 1
                else:
                    stats["yt_fail"] += 1
                log(f"{'✅' if ok else '❌'} {url}\n   └── {msg}")

            # HTML Monitor
            log("\n--- HTML MONITOR (SITES OFICIAIS) ---")
            for url in data.get("official_sites_reference_(not_rss)", []):
                ok, msg = await check_html(client, url)
                if ok:
                    stats["html_ok"] += 1
                else:
                    stats["html_fail"] += 1
                log(f"{'✅' if ok else '❌'} {url}\n   └── {msg}")

            # Resumo
            log("\n" + "=" * 60)
            log("RESUMO")
            log("=" * 60)
            log(f"RSS:    {stats['rss_ok']} OK, {stats['rss_fail']} falhas")
            log(f"YouTube: {stats['yt_ok']} OK, {stats['yt_fail']} falhas")
            log(f"HTML:   {stats['html_ok']} OK, {stats['html_fail']} falhas")
            total_ok = stats["rss_ok"] + stats["yt_ok"] + stats["html_ok"]
            total_fail = stats["rss_fail"] + stats["yt_fail"] + stats["html_fail"]
            log(f"TOTAL:  {total_ok} OK, {total_fail} falhas")
            log(f"\nRelatório salvo em: {out_path}")

if __name__ == "__main__":
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Interrompido pelo usuário.")
    except Exception as e:
        print(f"❌ Erro: {e}")
        raise
