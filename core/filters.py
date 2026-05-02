"""
Filters module - Gundam & Gunpla Intelligence filtering and categorization logic.
"""
from typing import Dict, List, Any
import re
from utils.html import clean_html


# =========================================================
# GUNDAM & GUNPLA INTELLIGENCE FILTERS
# =========================================================

# Essential terms that define if a news item is relevant to the bot's scope
GUNDAM_CORE = [
    "gundam", "gunpla", "bandai", "sunrise", "p-bandai", "mobile suit", "mobilesuit",
    "universal century", "hguc", "mgex", "ver.ka", "plamo", "model kit", "g-structure",
    "witch from mercury", "iron-blooded orphans", "seed freedom", "gundam base",
    "premium bandai", "tamashii nations", "metal build", "robot spirits"
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
        "trailer", "teaser", "cast", "blu-ray", "dvd"
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

    # Block blacklist (always)
    if _contains_any(content, BLACKLIST):
        return False

    # Check for core relevance
    if not _contains_any(content, GUNDAM_CORE):
        return False

    # Source-specific strict rules
    if source_url:
        for src_key, strict_pattern in SPECIAL_SOURCE_RULES.items():
            if src_key in source_url:
                if not re.search(strict_pattern, content):
                    return False

    # "todos" allows everything (that passed the core check)
    if "todos" in filters:
        return True

    # Check specific categories
    for f in filters:
        kws = CAT_MAP.get(f, [])
        if kws and _contains_any(content, kws):
            return True

    return False

