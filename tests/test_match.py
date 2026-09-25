"""
Caso real que motivou o antigo script de depuração tests/test_match.py (que só
imprimia o resultado e não afirmava nada).

Fundamento do esperado (A3), independente da implementação: o título traz
「機動戦士ガンダム 閃光のハサウェイ」 — o nome oficial da obra (Mobile Suit Gundam:
Hathaway's Flash). É conteúdo Gundam; com o filtro "todos" tem de passar. O
controle negativo é o MESMO clipe descrito sem nenhuma referência a Gundam: a
música é de terceiros (Guns N' Roses) e sozinha não é notícia Gundam.
"""
from core.filters import match_intel

CONFIG = {"123": {"filters": ["todos", "gunpla", "musica"]}}
URL = "https://www.youtube.com/watch?v=9AVujlNBFbs"

TITULO_GUNDAM = (
    "アニメMV】ガンズ・アンド・ローゼズ - スウィート・チャイルド・オブ・マイン "
    "(『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』Ver.)"
)
RESUMO_GUNDAM = (
    "大ヒット上映中！映画『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』エンディング主題歌\n"
    "ガンズ・アンド・ローゼズ「スウィート・チャイルド・オブ・マイン」のアニメMVを公開。"
)


def test_mv_de_hathaway_em_japones_passa():
    assert match_intel("123", TITULO_GUNDAM, RESUMO_GUNDAM, CONFIG, URL) is True


def test_mesmo_clipe_sem_referencia_a_gundam_nao_passa():
    assert match_intel(
        "123",
        "Guns N' Roses - Sweet Child O' Mine (official video)",
        "rock classic",
        CONFIG,
        URL,
    ) is False
