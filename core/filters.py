"""
Filters module - Gundam & Gunpla Intelligence filtering and categorization logic.
"""
from typing import Dict, List, Any
import re
from utils.html import clean_html


# =========================================================
# GUNDAM & GUNPLA INTELLIGENCE FILTERS
# =========================================================

# Terms that are DEFINITELY Gundam/Gunpla
GUNDAM_SPECIFIC = [
    "gundam", "gunpla", "zaku", "mobilesuit", "mobile suit", "nu gundam", "sazabi",
    "strike freedom", "hathaway", "witch from mercury", "iron-blooded orphans",
    "seed freedom", "hguc", "mgex", "ver.ka", "master grade", "high grade",
    "real grade", "perfect grade", "entry grade", "sd gundam", "plamo", "g-structure",
    "universal century", "ad stella", "cosmic era", "post disaster", "after war",
    "機動戦士ガンダム", "ガンダムseed", "水星の魔女", "閃光のハサウェイ", "逆襲のシャア"
]

# Generic company terms (must be paired with GUNDAM_SPECIFIC for generic sources)
COMPANY_TERMS = ["bandai", "sunrise", "p-bandai", "premium bandai", "tamashii nations"]

# Core list for general relevance
GUNDAM_CORE = GUNDAM_SPECIFIC + COMPANY_TERMS

# YouTube e feeds genéricos: títulos só em JP não passam em _contains_any(\b gundam \b).
# Substring simples (sem word-boundary) para kanji/katakana.
GUNDAM_JP_HINTS = (
    "ガンダム",
    "ガンプラ",
    "機動戦士",
    "閃光のハサウェイ",
    "水星の魔女",
    "逆襲のシャア",
    "ＧＵＮＤＡＭ",  # fullwidth latin sometimes in JP titles
)

# Explicitly block non-Gundam franchises from the same companies
NEGATIVE_KEYWORDS = [
    "one piece", "one-piece", "dragoner", "apex legends", "apex", "brain powered",
    "daitarn", "ryu knight", "witch hunter robin", "machine robo", "digimon",
    "naruto", "dragon ball", "demon slayer", "blue lock", "sand land", "spy x family"
]

# Generic noise to ignore
BLACKLIST = [
    "giveaway", "deal of the day", "stock market", "celebrity", "politics"
]

# Categorization for the user dashboard
CAT_MAP = {
    "model_kits": [
        "gunpla", "hg", "mg", "rg", "pg", "eg", "model kit", "plamo", "option parts",
        "expansion set", "ver.ka", "master grade", "high grade", "real grade"
    ],
    "anime_movies": [
        "anime", "movie", "series", "episode", "streaming", "netflix", "crunchyroll",
        "trailer", "teaser", "cast", "blu-ray", "dvd", "music", "song", "ost", "soundtrack"
    ],
    "games": [
        "game", "mobile game", "gundam evolution", "gbo2", "uc engage", "breaker",
        "platform", "update", "patch notes", "steam", "ps5", "nintendo"
    ],
    "eventos": [
        "event", "exhibition", "gundam base", "statue", "yokohama", "shizuoka",
        "convention", "tamashii features", "hobby show"
    ],
    "merchandise": [
        "figure", "robot spirits", "metal build", "shfiguarts", "clothing",
        "apparel", "strict-g", "lifestyle", "accessory"
    ]
}

# Source-specific strict filters (Regex)
SPECIAL_SOURCE_RULES = {
    "reddit.com": r"(?i)(gundam|gunpla|bandai|mobile suit|hg|mg|rg|pg|ver.ka)",
    "hobby.dengeki.com": r"(?i)(ガンダム|ガンプラ|バンダイ)"
}

FILTER_OPTIONS = {
    "todos": ("TUDO", "🤖"),
    "model_kits": ("Model Kits & Gunpla", "🛠️"),
    "anime_movies": ("Anime & Filmes", "🎬"),
    "games": ("Games", "🎮"),
    "eventos": ("Eventos & Estátuas", "📍"),
    "merchandise": ("Merch & Figuras", "🧸"),
}

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def _contains_any(text: str, keywords: List[str]) -> bool:
    """
    Checks if any keyword is present in the text using flexible Regex.
    """
    if not keywords:
        return False

    patterns = []
    for k in keywords:
        escaped = re.escape(k)
        patterns.append(r'\b' + escaped + r's?\b')

    pattern_str = r'(?:' + '|'.join(patterns) + r')'
    return bool(re.search(pattern_str, text, re.IGNORECASE))


def match_intel(
    guild_id: str,
    title: str,
    summary: str,
    config: Dict[str, Any],
    source_url: str | None = None,
) -> bool:
    """
    Decides if the news item should be posted to the guild.
    """
    g = config.get(str(guild_id), {})
    filters = g.get("filters", [])

    if not isinstance(filters, list) or not filters:
        return False

    content = f"{clean_html(title)} {clean_html(summary)}".lower()

    # 1. Block explicit blacklist and negative keywords (One Piece, etc)
    if _contains_any(content, BLACKLIST) or _contains_any(content, NEGATIVE_KEYWORDS):
        return False

    # 2. Source-Specific Strictness
    # For generic aggregators like Google News or generic YouTube channels, 
    # we REQUIRE a specific Gundam term to avoid spam.
    is_generic_source = any(s in (source_url or "") for s in ["news.google.com", "youtube.com", "bandai", "sunrise"])
    
    if is_generic_source:
        has_en = _contains_any(content, GUNDAM_SPECIFIC)
        has_jp = any(h in content for h in GUNDAM_JP_HINTS)
        if not has_en and not has_jp:
            return False
    else:
        # For specialized Gundam sites, any core term (including Bandai) is okay
        if not _contains_any(content, GUNDAM_CORE):
            return False

    # 3. Source-specific regex rules
    if source_url:
        for src_key, strict_pattern in SPECIAL_SOURCE_RULES.items():
            if src_key in source_url:
                if not re.search(strict_pattern, content):
                    return False

    # 4. Filter categories
    if "todos" in filters:
        return True

    for f in filters:
        kws = CAT_MAP.get(f, [])
        if kws and _contains_any(content, kws):
            return True

    return False

