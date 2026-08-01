"""
Runner manual: mostra como um item real do YouTube é classificado por filtro.

Uso: `python tests/test_user_news.py`

A função de verificação chama-se `check_item`, NÃO `test_item`: com o nome antigo
o pytest coletava-a como teste e tentava injetar `filters`, `title`, `summary` e
`source_url` como fixtures, que não existem — resultado, um ERROR fixo na suíte.
O corpo do script também corria durante o import, por não ter guarda `__main__`.
"""
import os
import sys

# Executado diretamente, sys.path[0] é tests/ e não a raiz — sem isto o import
# de core.filters falha (o pytest não precisa, resolve pela rootdir).
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.filters import match_intel  # noqa: E402


def check_item(filters, title, summary, source_url):
    config = {"123": {"filters": filters}}
    result = match_intel("123", title, summary, config, source_url)
    print(f"Filters {filters} -> Result: {result}")
    return result


TITLE = "[ヘッドホン推奨]『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』戦場体感PV"
SUMMARY = """ガンダムシリーズ最新作『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』大ヒット公開中！

先週より上映がスタートしたラージフォーマットDolby Cinema®（ドルビーシネマ）版に続き、MX4D™、4DX®の上映が決定しました。 
まるでモビルスーツのコックピットに乗り込んだかのような臨場感で味わう、全感覚で体感する『閃光のハサウェイ』体験を劇場でお楽しみください。 

本PVは、ぜひお手持ちのヘッドホンやイヤホンでご視聴ください。 

▼劇場情報はこちら
https://gundam-official.com/hathaway/...
▼作品公式サイト
https://gundam-official.com/hathaway
▼公式X
  / gundam_hathaway  

＜STORY＞ 
U.C.0105、シャアの反乱から12年——。
...
#閃光のハサウェイ #キルケーの魔女 #ガンダム
"""
URL = "https://www.youtube.com/watch?v=QbZE6LhdycY"


def main():
    print(f"Testing for title: {TITLE}")
    for filtros in (["todos"], ["filmes"], ["gunpla"], ["games"],
                    ["musica"], ["roupas"], ["hardware"]):
        check_item(filtros, TITLE, SUMMARY, URL)


if __name__ == "__main__":
    main()
