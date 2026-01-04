"""
Smoke tests básicos para verificar que o projeto está configurado corretamente.
Não testa lógica complexa para evitar dependências do Discord token.
"""
import os
import json


def test_config_files_exist():
    """Verifica que arquivos de configuração existem."""
    assert os.path.exists("sources.json"), "sources.json deve existir"
    assert os.path.exists("settings.py"), "settings.py deve existir"
    assert os.path.exists("main.py"), "main.py deve existir"


def test_sources_json_structure():
    """Verifica estrutura básica do sources.json."""
    with open("sources.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert isinstance(data, dict), "sources.json deve ser um objeto"
    
    # Deve ter pelo menos rss_feeds ou youtube_feeds
    has_feeds = "rss_feeds" in data or "youtube_feeds" in data
    assert has_feeds, "Deve ter pelo menos rss_feeds ou youtube_feeds"
    
    # Se tiver rss_feeds, deve ser uma lista
    if "rss_feeds" in data:
        assert isinstance(data["rss_feeds"], list), "rss_feeds deve ser uma lista"
    
    # Se tiver youtube_feeds, deve ser uma lista
    if "youtube_feeds" in data:
        assert isinstance(data["youtube_feeds"], list), "youtube_feeds deve ser uma lista"


def test_no_invalid_youtube_urls():
    """Verifica que não há URLs do YouTube com @ (formato inválido)."""
    with open("sources.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    youtube_feeds = data.get("youtube_feeds", [])
    for url in youtube_feeds:
        # Não deve ter @ (que seria um handle, não um feed Atom)
        assert "@" not in url, f"YouTube URL inválida (use channel_id): {url}"


def test_requirements_has_dependencies():
    """Verifica que requirements.txt tem dependências essenciais."""
    # Tenta diferentes encodings (requirements.txt pode ser UTF-16 no Windows)
    for encoding in ["utf-8", "utf-16", "latin-1"]:
        try:
            with open("requirements.txt", "r", encoding=encoding) as f:
                content = f.read().lower()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    assert "discord" in content, "requirements.txt deve incluir discord.py"
    assert "feedparser" in content, "requirements.txt deve incluir feedparser"
    assert "aiohttp" in content, "requirements.txt deve incluir aiohttp"


def test_main_has_ssl_fix():
    """Verifica que main.py usa certifi para SSL."""
    with open("main.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Deve usar certifi
    assert "certifi" in content, "main.py deve importar certifi para SSL seguro"
    
    # NÃO deve ter CERT_NONE (inseguro)
    assert "CERT_NONE" not in content, "main.py não deve usar CERT_NONE (inseguro)"

