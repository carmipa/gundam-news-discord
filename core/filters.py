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
    "hathaway noa", "xi gundam", "gundam penelope", "unicorn gundam", "rx-0", "gundam banshee", 
    "gundam narrative", "gundam f91", "victory gundam", "cucuruz doan", "cucuruz doan's island",
    "gundam thunderbolt", "requiem for vengeance", "gundam the origin", "u.c. engage", "gundam engage", "uce",
    
    # Alternate Universes (A.U.)
    "g gundam", "gundam wing", "endless waltz", "gundam x", "turn a gundam",
    "gundam seed", "seed destiny", "seed freedom", "gundam astray", "gundam stargazer", 
    "gundam 00", "double 00", "gundam age", "g reconguista", "iron-blooded orphans", 
    "ibo", "barbatos", "witch from mercury", "suletta", "miorine", "gundam aerial",
    
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
# FONTES GUNDAM-DEDICADAS (referência; não usado na lógica atual)
# =========================================================
# Regra atual: SEMPRE exige termo Gundam (GUNDAM_CORE) no título/resumo, em todas as fontes.
# Lista abaixo mantida apenas como referência (ex.: usagundamstore, hobby.dengeki postam
# conteúdo não-Gundam; por isso a palavra Gundam é obrigatória na matéria).
TRUSTED_GUNDAM_SOURCE_DOMAINS = [
    # Notícias e blogs Gundam
    "gundamnews.org", "gunpla101.com", "gunjap.net", "usagundamstore.com",
    "gundamkitscollection.com", "gundam-base.net", "gundamplanet.com",
    "vcagundam.com", "gundamworld.it", "gundamhangar.com", "planetagundam.com",
    "gundamplacestore.com", "gundam-ab.com", "strict-g.com",
    # Oficiais e séries
    "gundam-official.com", "gundam.info", "gundam.jp", "gundam-seed.net",
    "gundam-tb.net", "gundam-the-origin.net", "g-tekketsu.com", "gundam-unicorn.net",
    "g-reco.net", "gundam-bf.net", "gundam-age.net", "gundam00.net", "gundam-san.net",
    "gundam-zz.net", "g-twilight-axis.net", "gundam-gcg.com", "gundamfc.com",
    "gundam-next-future-pavilion", "gundam-navi", "unicorn-gundam-statue",
    "gundam_ch", "gundam_hathaway", "gundam-uce.ggame.jp",
    # Bandai / Hobby / Tamashii
    "p-bandai.com", "tamashiiweb.com", "bandai-hobby.net", "bandai.com/blog",
    "hobby.dengeki.com", "bandainamco.co.jp", "gmpj.bn-ent.net",
    "bandai.co.jp/candy/gundam", "bandai.co.jp/candy/gunpla",
    # Sunrise / Sotsu (estúdio e direitos Gundam)
    "sunrise-inc.co.jp", "sunrise-music.co.jp", "sotsu.co.jp",
    # Jogos Gundam (GBO2, etc.)
    "bo2.ggame.jp", "gget.ggame.jp", "gb.ggame.jp",
    # Reddit e lojas/hobby
    "reddit.com/r/Gundam", "reddit.com/r/Gunpla",
    "1999.co.jp/eng/gundam", "bandaibrasil.com.br/collections/gundam",
]


def is_trusted_gundam_source(source_url: str) -> bool:
    """True se a URL é de fonte Gundam-dedicada. Não usado na lógica atual (sempre exigimos termo Gundam)."""
    if not source_url:
        return False
    url_lower = source_url.lower()
    return any(domain in url_lower for domain in TRUSTED_GUNDAM_SOURCE_DOMAINS)


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


def match_intel(
    guild_id: str,
    title: str,
    summary: str,
    config: Dict[str, Any],
    source_url: str | None = None,
) -> bool:
    """
    Decide se notícia deve ir para a guild.

    Lógica:
      1. Exige filtros configurados
      2. Corta blacklist (animes não-Gundam)
      3. Exige sempre pelo menos um termo Gundam (GUNDAM_CORE) no título/resumo em todas as fontes
      4. "todos" libera tudo (desde que passe 2 e 3)
      5. Senão, precisa bater em categoria selecionada

    Args:
        guild_id: ID da guild
        title: Título da notícia
        summary: Resumo da notícia
        config: Configuração carregada
        source_url: URL do feed/fonte (opcional, reservado para uso futuro).

    Returns:
        True se notícia deve ser postada
    """
    g = config.get(str(guild_id), {})
    filters = g.get("filters", [])

    if not isinstance(filters, list) or not filters:
        return False

    content = f"{clean_html(title)} {clean_html(summary)}".lower()

    # Bloqueia blacklist (sempre)
    if _contains_any(content, BLACKLIST):
        return False

    # Exige sempre pelo menos um termo Gundam no título/resumo (todas as fontes)
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
