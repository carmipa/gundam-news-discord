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

# Categorização exposta no dashboard. Cada categoria é um recorte do universo
# Mobile Suit Gundam — kits, anime/filmes, games, eventos, merch, música e roupas.
# Todas são avaliadas DEPOIS do portão que exige um termo Gundam no conteúdo, por
# isso podem conter palavras genéricas ("kit", "album", "cap") sem gerar ruído.
# Termos em japonês são casados por substring (ver _contains_any).
CAT_MAP = {
    "model_kits": [
        "gunpla", "hg", "mg", "rg", "pg", "eg", "model kit", "kit", "plamo",
        "option parts", "expansion set", "ver.ka", "master grade", "high grade",
        "real grade", "perfect grade", "entry grade", "full mechanics",
        "ガンプラ", "プラモデル", "キット",
    ],
    "anime_movies": [
        "anime", "movie", "series", "episode", "streaming", "netflix", "crunchyroll",
        "trailer", "teaser", "cast", "blu-ray", "dvd", "music", "song", "ost", "soundtrack",
        "filme", "série", "temporada", "episódio", "dublado", "legendado", "estreia",
        # 劇場/公開/上映/予告 cobrem o vocabulário real de estreia e sessão nos
        # comunicados japoneses — sem eles, um PV de filme como o de Hathaway
        # passava no portão Gundam e depois não caía em nenhuma categoria.
        "劇場版", "劇場", "アニメ", "映画", "配信", "最終回", "放送",
        "公開", "上映", "予告", "本編", "第1話",
    ],
    "games": [
        "game", "mobile game", "gundam evolution", "gbo2", "uc engage", "breaker",
        "platform", "update", "patch notes", "steam", "ps5", "nintendo", "gameplay",
        "dlc", "beta", "jogo", "ゲーム", "アプリ",
    ],
    "eventos": [
        "event", "exhibition", "gundam base", "statue", "yokohama", "shizuoka",
        "convention", "tamashii features", "hobby show", "evento", "exposição",
        "イベント", "展示", "開催",
    ],
    "merchandise": [
        "figure", "robot spirits", "metal build", "shfiguarts", "clothing",
        "apparel", "strict-g", "lifestyle", "accessory", "goods", "collectible",
        "figura", "colecionável", "グッズ", "フィギュア",
        # merchandise é o guarda-chuva: também apanha roupas e hardware.
        "t-shirt", "hoodie", "motherboard", "graphics card", "gpu", "ssd",
    ],
    # Música: trilhas, temas de abertura/encerramento, singles e shows. As keywords
    # musicais continuam também em anime_movies (superconjunto histórico), então
    # quem escolhe "Anime & Filmes" não perde cobertura ao ganhar esta categoria.
    "musica": [
        "music", "song", "ost", "soundtrack", "theme song", "opening theme",
        "ending theme", "single", "album", "concert", "live tour", "band",
        "composer", "score", "musica", "música", "trilha sonora", "cantora",
        "cantor", "主題歌", "サントラ", "音楽", "劇伴", "挿入歌", "ライブ",
    ],
    # Roupas e vestuário — a linha Strict-G e as colaborações de moda. Os termos
    # também vivem em merchandise, que continua a ser o guarda-chuva mais amplo.
    "roupas": [
        "clothing", "apparel", "t-shirt", "tshirt", "shirt", "hoodie", "jacket",
        "outerwear", "cap", "hat", "sneakers", "shoes", "uniform", "cosplay",
        "strict-g", "collab", "roupa", "camiseta", "moletom", "jaqueta", "boné",
        "vestuário", "アパレル", "Tシャツ", "服",
    ],
    # Hardware de PC em edição Gundam: raro, mas sai — placas ASUS ROG Strix,
    # GPUs Zotac, gabinetes Cooler Master, SSDs, teclados e periféricos temáticos.
    # Por serem lançamentos esporádicos, valem categoria própria: quem só quer
    # isto não precisa de assinar merchandise inteiro e ser soterrado de figuras.
    # Evitadas de propósito palavras que são unidade de medida ("gigabyte") ou
    # demasiado curtas/ambíguas ("ram", "pc") — o portão Gundam não chega para
    # segurar esse tipo de ruído.
    "hardware": [
        "motherboard", "graphics card", "gpu", "video card", "ssd", "keyboard",
        "mouse", "mousepad", "pc case", "power supply", "monitor", "headset",
        "laptop", "cooler", "gaming pc", "peripheral", "asus rog", "rog strix",
        "zotac", "cooler master", "msi gaming", "placa-mãe", "placa de vídeo",
        "teclado", "gabinete", "periférico", "マザーボード", "グラフィックボード",
        "キーボード", "ゲーミングpc", "自作pc",
    ],
}

# Source-specific strict filters (Regex)
SPECIAL_SOURCE_RULES = {
    "reddit.com": r"(?i)(gundam|gunpla|bandai|mobile suit|hg|mg|rg|pg|ver.ka)",
    "hobby.dengeki.com": r"(?i)(ガンダム|ガンプラ|バンダイ)"
}

# Ordem importa: o dashboard põe os 5 primeiros na linha 0 e o resto na linha 1
# (Discord permite 5 botões por linha, 5 linhas; idiomas ficam na 2 e controles na 3).
FILTER_OPTIONS = {
    "todos": ("TUDO", "🤖"),
    "model_kits": ("Model Kits & Gunpla", "🛠️"),
    "anime_movies": ("Anime & Filmes", "🎬"),
    "games": ("Games", "🎮"),
    "eventos": ("Eventos & Estátuas", "📍"),
    "merchandise": ("Merch & Figuras", "🧸"),
    "musica": ("Músicas & Trilhas", "🎵"),
    "roupas": ("Roupas & Vestuário", "👕"),
    "hardware": ("Hardware & PC", "💻"),
}

# Nomes de categoria antigos que ainda vivem em config.json de servidores que
# escolheram os filtros antes da renomeação para as chaves de FILTER_OPTIONS.
#
# Sem este mapa, `CAT_MAP.get("gunpla", [])` devolve lista vazia e match_intel
# rejeita TUDO em silêncio. Medido na produção em 2026-08-01: 4 guilds filtravam
# só por nomes legados (2 delas com canal ativo, recebendo zero notícias desde a
# renomeação) e 1 tinha cobertura parcial (`["filmes", "games"]` — só "games"
# funcionava). Nenhum log denunciava: filtro sem keywords é indistinguível de
# "nada casou".
#
# "musica" NÃO está aqui — deixou de ser nome órfão e virou categoria própria.
LEGACY_FILTER_ALIASES = {
    "gunpla": "model_kits",
    "filmes": "anime_movies",
}

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def normalize_filters(filters: Any) -> List[str]:
    """
    Traduz nomes de filtro legados para as chaves atuais de FILTER_OPTIONS.

    PROPÓSITO DE NEGÓCIO:
        O dashboard desenha um botão por chave de FILTER_OPTIONS e pinta de verde
        as que estão no config.json. Uma guild que guardou "gunpla" via de ver
        "Model Kits & Gunpla" apagado apesar de o filtro funcionar — e ao carregar
        no botão gravava um segundo nome para a mesma categoria. Normalizar na
        leitura mantém o painel fiel e migra o config no primeiro save.

    INVARIANTES DO DOMÍNIO:
        - Preserva a ordem de escolha e remove duplicados criados pela tradução
          (["gunpla", "model_kits"] colapsa para ["model_kits"]).
        - Nomes desconhecidos passam intactos: não é a função que decide o que é
          válido, e descartar aqui esconderia erro de configuração.
        - Entradas não-string são descartadas.

    COMPORTAMENTO EM CASO DE FALHA:
        Nunca levanta. Entrada None, string solta ou de tipo errado devolve [].
    """
    if not isinstance(filters, list):
        return []
    saida = [
        LEGACY_FILTER_ALIASES.get(f, f)
        for f in filters
        if isinstance(f, str) and f.strip()
    ]
    return list(dict.fromkeys(saida))


def _has_cjk(text: str) -> bool:
    """True se o texto tem kana, kanji ou pontuação/latino de largura total."""
    return any(
        "　" <= ch <= "鿿" or "＀" <= ch <= "￯"
        for ch in text
    )


def _contains_any(text: str, keywords: List[str]) -> bool:
    """
    Verifica se alguma keyword aparece no texto, respeitando fronteiras de palavra.

    PROPÓSITO DE NEGÓCIO:
        É o motor de decisão de todos os filtros: define se uma notícia é sobre
        Gundam e a que categoria pertence. Um falso positivo aqui vira spam em 21
        servidores; um falso negativo faz a notícia nunca ser publicada.

    INVARIANTES DO DOMÍNIO:
        - Casa palavra inteira, não substring: "wing" não pode casar "drawing".
        - Aceita plural simples ("gundams" casa a keyword "gundam").
        - Keywords NUMÉRICAS ("00", de Gundam 00) não podem casar dentro de
          horários nem de números maiores. `\\b00\\b` casaria "12:00", porque o
          ":" conta como fronteira de palavra — daí a fronteira estrita, que
          também rejeita "." (versões) e dígitos vizinhos ("2000", "300").
          Keywords de texto mantêm o `\\b` clássico: apertar a fronteira delas
          quebraria casos legítimos como "Novidade:Gundam".
        - Comparação sempre case-insensitive.

    COMPORTAMENTO EM CASO DE FALHA:
        Lista de keywords vazia ou None devolve False (nunca levanta). Keywords
        são escapadas com re.escape, então caracteres especiais são literais e
        não conseguem quebrar o regex.
    """
    if not keywords:
        return False

    patterns = []
    for k in keywords:
        escaped = re.escape(k)
        if _has_cjk(k):
            # Japonês não separa palavras com espaço e kana/kanji contam como \w,
            # então \b nunca casa no meio de uma frase ("アニメ主題歌決定").
            # Substring é o único critério que funciona — mesma razão de GUNDAM_JP_HINTS.
            patterns.append(escaped)
        elif k.isdigit():
            # ":" e "." colam o número a horários (12:00) e versões (1.00);
            # \w cobre os dígitos vizinhos de "2000" e "300".
            patterns.append(r'(?<![\w:.])' + escaped + r'(?![\w:.])')
        else:
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

    clean_title = clean_html(title).lower()
    clean_summary = clean_html(summary).lower()
    content = f"{clean_title} {clean_summary}"

    # 1. Block explicit blacklist and negative keywords (One Piece, etc)
    if _contains_any(content, BLACKLIST) or _contains_any(content, NEGATIVE_KEYWORDS):
        return False

    # 2. Source-Specific Strictness
    # For generic aggregators like Google News or generic YouTube channels, 
    # we REQUIRE a specific Gundam term to avoid spam.
    is_generic_source = any(s in (source_url or "") for s in ["news.google.com", "youtube.com", "bandai", "sunrise"])
    
    if is_generic_source:
        # Em fontes genéricas (especialmente YouTube), descrição pode citar Gundam
        # sem que o vídeo/notícia seja de fato sobre Gundam.
        if "youtube.com" in (source_url or "") or "youtu.be" in (source_url or ""):
            has_en_title = _contains_any(clean_title, GUNDAM_SPECIFIC)
            has_jp_title = any(h in clean_title for h in GUNDAM_JP_HINTS)
            if not has_en_title and not has_jp_title:
                return False
        else:
            has_en = _contains_any(content, GUNDAM_SPECIFIC)
            has_jp = any(h in content for h in GUNDAM_JP_HINTS)
            if not has_en and not has_jp:
                return False
    else:
        # For specialized Gundam sites, any core term (including Bandai) is okay.
        # Muitos feeds especializados são só em japonês (Esuteru, Hayamimi, Ryokutya,
        # Hobby Dengeki, Gundam Base JP, Tamashii...): também aceitamos os hints em kana/kanji,
        # senão itens só-em-japonês seriam silenciosamente descartados.
        has_en = _contains_any(content, GUNDAM_CORE)
        has_jp = any(h in content for h in GUNDAM_JP_HINTS)
        if not has_en and not has_jp:
            return False

    # 3. Source-specific regex rules
    if source_url:
        for src_key, strict_pattern in SPECIAL_SOURCE_RULES.items():
            if src_key in source_url:
                if not re.search(strict_pattern, content):
                    return False

    # 4. Filter categories (resolvendo nomes legados antes de consultar o CAT_MAP)
    if "todos" in filters:
        return True

    for f in filters:
        categoria = LEGACY_FILTER_ALIASES.get(f, f)
        kws = CAT_MAP.get(categoria, [])
        if kws and _contains_any(content, kws):
            return True

    return False

