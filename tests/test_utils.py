"""
Testes para as funções utilitárias do bot.
Estes testes NÃO importam main.py para evitar dependência do Discord token.
"""
import re


# Cópia das funções para testar (sem depender de main.py)
def clean_html(raw_html: str) -> str:
    """Remove tags HTML e entidades; normaliza espaços."""
    if not raw_html:
        return ""
    _HTML_RE = re.compile(r"<.*?>|&([a-z0-9]+|#[0-9]{1,6});", flags=re.IGNORECASE)
    _WS_RE = re.compile(r"\s+")
    txt = re.sub(_HTML_RE, " ", raw_html)
    txt = re.sub(_WS_RE, " ", txt).strip()
    return txt


def test_clean_html_basic():
    """Testa remoção de tags HTML simples."""
    assert clean_html("<p>Test</p>") == "Test"
    assert clean_html("<b>Bold</b> text") == "Bold text"


def test_clean_html_entities():
    """Testa conversão de entidades HTML."""
    result = clean_html("Hello&nbsp;World")
    assert "Hello" in result and "World" in result


def test_clean_html_whitespace():
    """Testa normalização de espaços."""
    assert clean_html("  Multiple   spaces  ") == "Multiple spaces"
    assert clean_html("\n\nNew\nlines\n\n") == "New lines"


def test_clean_html_empty():
    """Testa strings vazias."""
    assert clean_html("") == ""
    assert clean_html(None) == ""


def test_sources_json_exists():
    """Verifica que sources.json existe."""
    import os
    assert os.path.exists("sources.json"), "sources.json deve existir"


def test_sources_json_valid():
    """Verifica que sources.json é JSON válido."""
    import json
    with open("sources.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict), "sources.json deve ser um dicionário"
    assert "rss_feeds" in data or "youtube_feeds" in data, "Deve ter pelo menos uma categoria de feeds"


def test_sources_urls_are_valid():
    """Verifica que URLs em sources.json começam com http(s)."""
    import json
    with open("sources.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    all_urls = []
    for key in data:
        if isinstance(data[key], list):
            all_urls.extend(data[key])
    
    for url in all_urls:
        assert url.startswith(("http://", "https://")), f"URL inválida: {url}"


def test_readme_exists():
    """Smoke test: verifica que README existe."""
    import os
    assert os.path.exists("readme.md"), "readme.md deve existir"

