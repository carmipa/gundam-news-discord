
import pytest
import os
import sys

# Garante que o diretório raiz está no path para importar core.filters
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.filters import match_intel

# Configuração fictícia para os testes
# No config.json real, os filtros são listas de strings: "gunpla", "filmes", "games", "musica", "todos"
MOCK_CONFIG = {
    "123": {
        "filters": ["todos", "gunpla", "filmes", "games", "musica"]
    }
}

@pytest.mark.parametrize("title, summary, expected", [
    # CASO 1: Hathaway / Kirke's Witch (O que você pediu)
    ("[PV] Hathaway's Flash: Kirke's Witch", "New trailer for the upcoming movie", True),
    ("『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』", "Nova atualização do filme", True),
    
    # CASO 2: Blacklist (Deve ser bloqueado SEMPRE, mesmo com termo Gundam)
    ("One Piece Live Action News", "Gundam style animation in One Piece", False),
    ("Naruto vs Boruto", "Comparison with Gundam battles", False),
    
    # CASO 3: Gunpla (Passa pelo termo e pela categoria)
    ("New HG 1/144 Zaku II Release", "Premium Bandai exclusive model kit", True),
    
    # CASO 4: Falsos Positivos (00 em horários vs série)
    ("News at 12:00", "No gundam terms here", False),
    ("Gundam 00 Movie", "The world is changing", True),
    
    # CASO 5: Termos CJK (Japonês)
    ("ガンダムの最新ニュース", "Gundam news in Japanese", True),
])
def test_gundam_matching_logic(title, summary, expected):
    """Testa a lógica principal de match (filtros, blacklist, core terms)."""
    result = match_intel("123", title, summary, MOCK_CONFIG)
    assert result == expected

def test_specific_guild_filters():
    """Testa se os filtros específicos de cada guild (servidor) funcionam isoladamente."""
    # Guild 456 só quer Gunpla
    custom_config = {"456": {"filters": ["gunpla"]}}
    
    # Notícia de filme (Hathaway) NÃO deve passar se o filtro for apenas 'gunpla'
    # No match_intel atual, se não tiver 'todos', ele verifica cada categoria no CAT_MAP
    assert match_intel("456", "Hathaway Movie News", "Coming soon PV trailer", custom_config) == False
    
    # Notícia de Gunpla (Kit) DEVE passar
    assert match_intel("456", "New MG Gundam Ver.Ka", "Model kit", custom_config) == True

def test_blacklist_strong_blocking():
    """Garante que a blacklist bloqueia mesmo se houver muitos termos Gundam."""
    config = {"123": {"filters": ["todos"]}}
    title = "Gundam vs Dragon Ball: The ultimate crossover"
    summary = "Gundam amuro char zaku zeon fighting Goku in Dragon Ball Super"
    
    # Deve ser False porque 'dragon ball' está na Blacklist
    assert match_intel("123", title, summary, config) == False

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))
