import json
from core.filters import match_intel

config = {"123": {"filters": ["todos", "gunpla", "musica"]}}

title = "アニメMV】ガンズ・アンド・ローゼズ - スウィート・チャイルド・オブ・マイン (『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』Ver.)"
summary = """大ヒット上映中！映画『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』エンディング主題歌
ガンズ・アンド・ローゼズ「スウィート・チャイルド・オブ・マイン」のアニメMVを公開。
"""
url = "https://www.youtube.com/watch?v=9AVujlNBFbs"

print("match_intel result:", match_intel("123", title, summary, config, url))
