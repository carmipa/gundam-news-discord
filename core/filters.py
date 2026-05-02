"""
Filters module - Cybersecurity Intelligence filtering and categorization logic.
"""
from typing import Dict, List, Any
import re
from utils.html import clean_html


# =========================================================
# CYBERSECURITY INTELLIGENCE FILTERS
# =========================================================

# Essential terms that define if a news item is relevant to the bot's scope
CYBER_CORE = [
    "cybersecurity", "infosec", "hacker", "hacking", "exploit", "vulnerability",
    "zero-day", "0-day", "malware", "ransomware", "phishing", "data breach",
    "data leak", "cyberattack", "cyber attack", "cve-", "critical patch",
    "security advisory", "threat intelligence", "apt group", "cyber warfare",
    "security researcher", "penetration testing", "pentest", "red team", "blue team",
    "encryption", "cryptography", "social engineering", "backdoor", "trojan",
    "botnet", "spyware", "stealer", "rootkit", "rce", "sqli", "xss", "csrf"
]

# Generic noise to ignore (to reduce false positives from general tech news)
BLACKLIST = [
    "gaming news", "gameplay", "trailer", "movie review", "smartphone review",
    "giveaway", "deal of the day", "crypto price", "stock market", "celebrity"
]

# Categorization for the user dashboard
CAT_MAP = {
    "vulnerabilidades": [
        "cve", "vulnerability", "exploit", "zero-day", "0-day", "rce", "sqli", "xss",
        "bypass", "patch", "advisory", "update", "poc", "proof of concept"
    ],
    "malware": [
        "ransomware", "trojan", "spyware", "botnet", "phishing", "loader", "stealer",
        "crypter", "virus", "worm", "wiper", "malicious", "adware"
    ],
    "vazamentos": [
        "data breach", "leak", "dump", "credentials", "database", "exposed", 
        "breached", "pwned", "dark web", "intel leak"
    ],
    "ameacas": [
        "apt", "threat actor", "hacker group", "state-sponsored", "campaign",
        "espionage", "lazarus", "lockbit", "fancy bear", "sandworm", "cl0p"
    ],
    "pesquisa": [
        "deep dive", "analysis", "whitepaper", "reverse engineering", "writeup",
        "forensics", "dfir", "technical report", "security research"
    ]
}

# Source-specific strict filters (Regex)
SPECIAL_SOURCE_RULES = {
    "reddit.com": r"(?i)(cve|exploit|vulnerability|malware|breach|leak|hack|apt|zero-day|0-day)",
    "wired.com": r"(?i)(security|hacker|hack|breach|cyber|vulnerability|surveillance|privacy)"
}

FILTER_OPTIONS = {
    "todos": ("TUDO", "🛡️"),
    "vulnerabilidades": ("Vulnerabilidades", "🐛"),
    "malware": ("Malware & Ransomware", "🦠"),
    "vazamentos": ("Vazamentos & Brechas", "🔓"),
    "ameacas": ("Atores & Ameaças", "👥"),
    "pesquisa": ("Pesquisa & Writeups", "📝"),
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
    if not _contains_any(content, CYBER_CORE):
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
