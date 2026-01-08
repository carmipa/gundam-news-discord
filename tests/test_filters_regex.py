
import pytest
from core.filters import _contains_any

def test_contains_any_basic_match():
    """Test verification of basic keyword matches."""
    keywords = ["gundam", "zaku"]
    assert _contains_any("i love gundam", keywords) is True
    assert _contains_any("zaku is cool", keywords) is True
    assert _contains_any("no robots here", keywords) is False

def test_contains_any_word_boundaries():
    """Test that it respects word boundaries (no partial matches)."""
    keywords = ["wing", "seed"]
    
    # Should NOT match
    assert _contains_any("drawing a picture", keywords) is False
    assert _contains_any("seedy place", keywords) is False
    assert _contains_any("swinging", keywords) is False
    
    # Should MATCH
    assert _contains_any("gundam wing zero", keywords) is True
    assert _contains_any("gundam seed destiny", keywords) is True

def test_contains_any_plurals():
    """Test that regular plural check works (optional 's')."""
    # Note: The implementation plan decided to allow optional 's'
    # Implementation should handle: r'\bkeyword(?:s)?\b'
    keywords = ["gundam", "zaku", "wing"]
    
    assert _contains_any("look at those gundams", keywords) is True
    assert _contains_any("lots of zakus", keywords) is True
    assert _contains_any("broken wings", keywords) is True

def test_contains_any_00_edge_case():
    """Test specific edge case for '00' vs '12:00'."""
    keywords = ["00"]
    
    # Should NOT match time formats
    assert _contains_any("it is 12:00 now", keywords) is False
    assert _contains_any("03:00 pm", keywords) is False
    assert _contains_any("year 300", keywords) is False
    assert _contains_any("2000", keywords) is False
    
    # Should MATCH standalone 00
    assert _contains_any("gundam 00 is great", keywords) is True
    assert _contains_any("double 00", keywords) is True

def test_contains_any_char_edge_case():
    """Test 'char' vs 'charge'."""
    keywords = ["char"]
    
    assert _contains_any("char aznable", keywords) is True
    assert _contains_any("charge your phone", keywords) is False
    assert _contains_any("char's counterattack", keywords) is True

