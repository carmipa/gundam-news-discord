"""
Filters module - News filtering and categorization logic.
"""
from typing import Dict, List, Any
from utils.html import clean_html


# =========================================================
# FILTROS / CATEGORIAS
# =========================================================

GUNDAM_CORE = [
    # Termos Gerais
    "gundam", "gunpla", "zeon", "zaku", "mobile suit", "haropla", "sdcs", 
    "amuro ray", "char aznable", "mafty", "minovsky", "newtype", "cyber newtype",
    
    # Universal Century (U.C.)
    "rx-78", "08th ms team", "0080", "war in the pocket", "0083", "stardust memory",
    "zeta gundam", "zz gundam", "char's counterattack", "cca", "hathaway's flash", 
    "hathaway noa", "xi gundam", "penelope", "unicorn gundam", "rx-0", "banshee", 
    "narrative", "gundam f91", "victory gundam", "cucuruz doan", "cucuruz doan's island",
    "thunderbolt", "requiem for vengeance", "gundam the origin", "u.c. engage", "engage", "uce",
    
    # Alternate Universes (A.U.)
    "g gundam", "gundam wing", "endless waltz", "gundam x", "turn a gundam",
    "gundam seed", "seed destiny", "seed freedom", "astray", "stargazer", 
    "gundam 00", "double 00", "gundam age", "g reconguista", "iron-blooded orphans", 
    "ibo", "barbatos", "witch from mercury", "suletta", "miorine", "aerial",
    
    # Build Series & SD
    "build fighters", "build divers", "build metaverse", "sd gundam", "gundam breakers",
    
    # Japanese Terms
    "ガンダム", "機動戦士", "ハサウェイ", "マフティー", "閃光のハサウェイ", "エンゲージ", "ガンプラ"
]

BLACKLIST = [
    "one piece", "dragon ball", "naruto", "bleach",
    "my hero academia", "boku no hero", "hunter x hunter",
    "pokemon", "digimon", "attack on titan",
    "jujutsu", "demon slayer"
]

CAT_MAP = {
    "gunpla":  ["gunpla", "model kit", "kit", "ver.ka", "p-bandai", "premium bandai", "hg ", "mg ", "rg ", "pg ", "sd ", "fm ", "re/100", "perfect grade", "real grade", "high grade", "master grade", "metal build", "robot spirits", "ガンプラ"],
    "filmes":  ["anime", "episode", "episódio", "episodio", "movie", "film", "pv", "trailer", "teaser", "series", "season", "seed freedom", "witch from mercury", "hathaway", "requiem for vengeance", "cucuruz doan"],
    "games":   ["game", "steam", "ps5", "xbox", "gbo2", "battle operation", "breaker", "gundam breaker", "uc engage", "crossrays", "maxiboost", "extreme vs"],
    "musica":  ["music", "ost", "soundtrack", "album", "opening", "ending"],
    "fashion": ["fashion", "clothing", "apparel", "t-shirt", "hoodie", "jacket", "merch"],
}

# =========================================================
# SPECIAL SOURCE RULES (Advanced Filtering)
# =========================================================
# Mapeia ID do canal -> Regex que DEVE dar match no título para ser aprovado.
# Útil para canais oficiais que postam muito lixo (gameplay, trailers de outros jogos)
# e queremos apenas conteúdo específico (ex: cutscenes de história).

SPECIAL_SOURCE_RULES = {
    # Gundam Channel (Official) -> Apenas U.C. Engage (Story/Animation)
    # ID: UC7wu64jFsV02bbu6UHUd7JA (Gundam Channel)
    # ID: UC7wu64jGxCwSuxOR7XfS88g (Gundam Channel - Another URL format, same channel?)
    # Let's support both just in case, or list the specific one we are adding.
    # The user provided: UC7wu64jGxCwSuxOR7XfS88g
    "UC7wu64jFsV02bbu6UHUd7JA": r"(?i)(UCE|ENGAGE|エンゲージ|story|cutscene|アニメ|epis[oó]dio|episode|第\d+話)", 
    "UC7wu64jGxCwSuxOR7XfS88g": r"(?i)(UCE|ENGAGE|エンゲージ|story|cutscene|アニメ|epis[oó]dio|episode|第\d+話)"
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
    Verifica se alguma keyword está presente no texto usando Regex flexível.
    
    1. Se for Japonês (CJK), não usa 'word boundaries' (\\b), pois o Python 're' falha.
    2. Se for uma palavra chave central muito importante e passível de aglutinação
       (ex: 'gundam' em 'suitgundam', 'gunpla', 'zeon'), também removemos a borda rígida.
    3. Para as demais, usa word boundaries (\\b) para evitar 'wing' no meio de 'drawing'.
    Protege '00' de match em horários (12:00) usando negative lookbehind (?<!:).
    
    Args:
        text: Texto a verificar (já em lowercase)
        keywords: Lista de palavras-chave (em lowercase)
    
    Returns:
        True se pelo menos uma keyword foi encontrada
    """
    if not keywords:
        return False

    patterns = []
    
    # Palavras centrais que podem ser aglutinadas facilmente pelo usuário ou fonte
    core_agglutinable = ["gundam", "gunpla", "zaku", "zeon"]
    
    for k in keywords:
        escaped = re.escape(k)
        
        # Caracteres CJK ou Japonês - Não usar \\b pois falha no Python re
        is_cjk = re.search(r'[^\x00-\x7F]', k)
        
        if k in core_agglutinable:
             patterns.append(escaped + r's?')
        elif is_cjk:
             patterns.append(escaped)
        else:
             # Lookbehind para 00 (ex: 12:00)
             patterns.append(r'(?<!:)\b' + escaped + r's?\b')

    pattern_str = r'(?:' + '|'.join(patterns) + r')'
    
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
