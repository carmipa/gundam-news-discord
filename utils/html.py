"""
HTML utilities - Text cleaning functions.
"""
import re


# Compiled regex patterns for performance
_HTML_RE = re.compile(r"<.*?>|&([a-z0-9]+|#[0-9]{1,6});", flags=re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def clean_html(raw_html: str) -> str:
    """
    Remove tags HTML e entidades; normaliza espaços.
    
    Args:
        raw_html: HTML bruto (pode conter tags e entidades)
    
    Returns:
        Texto limpo sem HTML
    
    Examples:
        >>> clean_html("<p>Hello</p>")
        'Hello'
        >>> clean_html("Test&nbsp;space")
        'Test space'
    """
    if not raw_html:
        return ""
    
    # Remove tags HTML e entidades
    txt = re.sub(_HTML_RE, " ", raw_html)
    
    # Normaliza múltiplos espaços em um só
    txt = re.sub(_WS_RE, " ", txt).strip()
    
    return txt
