"""
Filters module - News filtering and categorization logic.
"""
from typing import Dict, List, Any
from utils.html import clean_html


# =========================================================
# FILTROS / CATEGORIAS
# =========================================================

GUNDAM_CORE = [
    "gundam", "gunpla", "zeon", "zaku", "mobile suit",
    "rx-78", "gundam seed", "seed freedom", "seed destiny",
    "gundam wing", "endless waltz",
    "gundam 00", "double 00",
    "char aznable", "amuro ray",
    "hathaway", "mafty", "xi gundam", "penelope",
    "unicorn gundam", "banshee", "rx-0",
    "witch from mercury", "suletta", "miorine", "aerial"
]

BLACKLIST = [
    "one piece", "dragon ball", "naruto", "bleach",
    "my hero academia", "boku no hero", "hunter x hunter",
    "pokemon", "digimon", "attack on titan",
    "jujutsu", "demon slayer"
]

CAT_MAP = {
    "gunpla":  ["gunpla", "model kit", "kit", "ver.ka", "p-bandai", "premium bandai", "hg ", "mg ", "rg ", "pg ", "sd ", "fm ", "re/100"],
    "filmes":  ["anime", "episode", "movie", "film", "pv", "trailer", "teaser", "series", "season", "seed freedom", "witch from mercury", "hathaway"],
    "games":   ["game", "steam", "ps5", "xbox", "gbo2", "battle operation", "breaker", "gundam breaker"],
    "musica":  ["music", "ost", "soundtrack", "album", "opening", "ending"],
    "fashion": ["fashion", "clothing", "apparel", "t-shirt", "hoodie", "jacket", "merch"],
}

FILTER_OPTIONS = {
    "todos": ("TUDO", "🌟"),
    "gunpla": ("Gunpla", "🤖"),
    "filmes": ("Filmes", "🎬"),
    "games": ("Games", "🎮"),
    "musica": ("Música", "🎵"),
    "fashion": ("Fashion", "👕"),
}


# =========================================================
# HELPER FUNCTIONS
# =========================================================

import re

def _contains_any(text: str, keywords: List[str]) -> bool:
    """
    Verifica se alguma keyword está presente no texto usando Regex.
    
    Usa word boundaries (\b) para evitar matches parciais (ex: 'wing' em 'drawing').
    Suporta plural opcional ('s?').
    Protege '00' de match em horários (12:00) usando negative lookbehind (?<!:).
    
    Args:
        text: Texto a verificar (já em lowercase)
        keywords: Lista de palavras-chave (em lowercase)
    
    Returns:
        True se pelo menos uma keyword foi encontrada
    """
    if not keywords:
        return False

    # Escapa keywords para segurança no regex
    # Monta padrão: (?<!:)\b(?:kw1|kw2|...|kwn)s?\b
    escaped_kws = [re.escape(k) for k in keywords]
    pattern_str = r'(?<!:)\b(?:' + '|'.join(escaped_kws) + r')s?\b'
    
    return bool(re.search(pattern_str, text))


def match_intel(guild_id: str, title: str, summary: str, config: Dict[str, Any]) -> bool:
    """
    Decide se notícia deve ir para a guild.
    
    Lógica:
      1. Exige filtros configurados
      2. Corta blacklist (animes não-Gundam)
      3. Exige termos Gundam core
      4. "todos" libera tudo
      5. Senão, precisa bater em categoria selecionada
    
    Args:
        guild_id: ID da guild
        title: Título da notícia
        summary: Resumo da notícia
        config: Configuração carregada
    
    Returns:
        True se notícia deve ser postada
    """
    g = config.get(str(guild_id), {})
    filters = g.get("filters", [])

    if not isinstance(filters, list) or not filters:
        return False

    content = f"{clean_html(title)} {clean_html(summary)}".lower()

    # Bloqueia blacklist
    if _contains_any(content, BLACKLIST):
        return False

    # Exige pelo menos um termo Gundam
    if not _contains_any(content, GUNDAM_CORE):
        return False

    # "todos" libera tudo
    if "todos" in filters:
        return True

    # Verifica categorias específicas
    for f in filters:
        kws = CAT_MAP.get(f, [])
        if kws and _contains_any(content, kws):
            return True

    return False
