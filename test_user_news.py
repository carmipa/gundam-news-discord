
import json
from core.filters import match_intel

def test_item(filters, title, summary, source_url):
    config = {"123": {"filters": filters}}
    result = match_intel("123", title, summary, config, source_url)
    print(f"Filters {filters} -> Result: {result}")
    return result

title = "[ヘッドホン推奨]『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』戦場体感PV"
summary = """ガンダムシリーズ最新作『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』大ヒット公開中！

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
url = "https://www.youtube.com/watch?v=QbZE6LhdycY"

print(f"Testing for title: {title}")
test_item(["todos"], title, summary, url)
test_item(["filmes"], title, summary, url)
test_item(["gunpla"], title, summary, url)
test_item(["games"], title, summary, url)
test_item(["musica"], title, summary, url)
