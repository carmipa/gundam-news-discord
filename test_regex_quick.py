import re

def _contains_any(text, keywords):
    if not keywords: return False
    patterns = []
    for k in keywords:
        escaped = re.escape(k)
        if k in ["gundam", "gunpla", "zaku", "zeon"]:
            patterns.append(escaped + r's?')
        elif re.search(r'[^\x00-\x7F]', k): # CJK
            patterns.append(escaped)
        else:
            patterns.append(r'(?<!:)\b' + escaped + r's?\b')
            
    pattern_str = r'(?:' + '|'.join(patterns) + r')'
    return bool(re.search(pattern_str, text))

GUNDAM_CORE = ["gundam", "mobile suit", "ガンダム", "機動戦士"]
CAT_MAP_FILMES = ["anime", "episode", "episódio", "episodio", "movie", "film"]
SPECIAL_SOURCE_RULES = {
    "UC7wu64jFsV02bbu6UHUd7JA": r"(?i)(UCE|ENGAGE|エンゲージ|story|cutscene|アニメ|epis[oó]dio|episode|第\d+話)", 
    "UC7wu64jGxCwSuxOR7XfS88g": r"(?i)(UCE|ENGAGE|エンゲージ|story|cutscene|アニメ|epis[oó]dio|episode|第\d+話)"
}

print("1. mobile suitgundam with gundam:")
print(_contains_any("episódio 13 | mobile suitgundam [gunchan]", GUNDAM_CORE))

print("2. js character no bounds:")
print(_contains_any("機動戦士ガンダム", GUNDAM_CORE))

print("3. episódio vs episode:")
print(_contains_any("episódio 49 | força sd gundam [gunchan]", CAT_MAP_FILMES))

print("4. SPECIAL_SOURCE_RULES on Episode 13:")
print(bool(re.search(SPECIAL_SOURCE_RULES["UC7wu64jGxCwSuxOR7XfS88g"], "Episódio 13 | Mobile SuitGundam [Gunchan]")))

print("5. SPECIAL_SOURCE_RULES on Japanese title:")
print(bool(re.search(SPECIAL_SOURCE_RULES["UC7wu64jGxCwSuxOR7XfS88g"], "第49話 | SDガンダムフォース 【ガンチャン】")))
