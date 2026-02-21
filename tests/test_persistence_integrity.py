"""
Teste de Persistência e Integridade de Dados.

Garante que o arquivo JSON não seja corrompido durante a escrita: salva um objeto
complexo, lê novamente e compara se todos os campos permanecem idênticos e se o
formato continua sendo JSON válido.
"""
import json
import os
import tempfile
import pytest
from utils.storage import load_json_safe, save_json_safe


# Objeto complexo análogo a evento/vulnerabilidade (Data, Severidade, Título)
COMPLEX_RECORD = {
    "Data": "2026-02-20T15:32:27",
    "Severidade": "alta",
    "Título": "Atualização crítica de segurança no sistema",
    "descrição": "Descrição com caracteres especiais: ç, ã, 日本語, emoji 🔒",
    "nested": {
        "lista": [1, 2, 3],
        "vazio": None,
        "numero": 3.14,
    },
}


class TestPersistenceIntegrity:
    """Valida parsing e integridade em disco (load/save round-trip)."""

    def test_save_and_read_all_fields_identical(self):
        """Salva objeto complexo, lê de volta e compara Data, Severidade, Título e demais campos."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            save_json_safe(filepath, COMPLEX_RECORD)
            loaded = load_json_safe(filepath, {})
            assert loaded is not None
            assert loaded["Data"] == COMPLEX_RECORD["Data"]
            assert loaded["Severidade"] == COMPLEX_RECORD["Severidade"]
            assert loaded["Título"] == COMPLEX_RECORD["Título"]
            assert loaded["descrição"] == COMPLEX_RECORD["descrição"]
            assert loaded["nested"] == COMPLEX_RECORD["nested"]
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_file_remains_valid_json(self):
        """Após escrita, o arquivo deve ser JSON válido (parseável por json.load)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            save_json_safe(filepath, COMPLEX_RECORD)
            with open(filepath, "r", encoding="utf-8") as f:
                parsed = json.load(f)
            assert isinstance(parsed, dict)
            assert parsed["Data"] == COMPLEX_RECORD["Data"]
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_round_trip_state_like_structure(self):
        """Round-trip de estrutura similar ao state.json (dedup, http_cache, html_hashes)."""
        state_like = {
            "dedup": {"https://feed.com": ["link1", "link2"]},
            "http_cache": {"https://feed.com": {"etag": "abc", "last_modified": "Wed, 20 Feb 2026"}},
            "html_hashes": {"https://site.com": "a1b2c3"},
            "last_cleanup": 1708457547.0,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            save_json_safe(filepath, state_like)
            loaded = load_json_safe(filepath, {})
            assert loaded["dedup"] == state_like["dedup"]
            assert loaded["http_cache"] == state_like["http_cache"]
            assert loaded["html_hashes"] == state_like["html_hashes"]
            assert loaded["last_cleanup"] == state_like["last_cleanup"]
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)
