"""
Testes para o comando /clean_state e funções relacionadas.
"""
import pytest
import json
import os
import tempfile
import shutil
from datetime import datetime

from utils.storage import (
    load_json_safe,
    save_json_safe,
    create_backup,
    get_state_stats,
    clean_state,
    p,
)
from utils.exceptions import InvalidCleanTypeError


class TestStateStats:
    """Testes para get_state_stats."""
    
    def test_get_state_stats_empty(self):
        """Testa estatísticas de state vazio."""
        state = {}
        stats = get_state_stats(state)
        
        assert stats["dedup_feeds"] == 0
        assert stats["dedup_total_links"] == 0
        assert stats["http_cache_urls"] == 0
        assert stats["html_hashes_sites"] == 0
    
    def test_get_state_stats_with_data(self):
        """Testa estatísticas de state com dados."""
        state = {
            "dedup": {
                "https://feed1.com": ["link1", "link2", "link3"],
                "https://feed2.com": ["link4"]
            },
            "http_cache": {
                "https://feed1.com": {"etag": "abc123"},
                "https://feed2.com": {"etag": "def456"},
                "https://feed3.com": {"last_modified": "Wed, 13 Feb 2026"}
            },
            "html_hashes": {
                "https://site1.com": "hash1",
                "https://site2.com": "hash2"
            },
            "last_cleanup": 1707820800.0
        }
        
        stats = get_state_stats(state)
        
        assert stats["dedup_feeds"] == 2
        assert stats["dedup_total_links"] == 4
        assert stats["http_cache_urls"] == 3
        assert stats["html_hashes_sites"] == 2
        assert stats["last_cleanup"] is not None
    
    def test_get_state_stats_invalid_dedup(self):
        """Testa com dedup inválido (não é dict)."""
        state = {"dedup": "invalid"}
        stats = get_state_stats(state)
        
        assert stats["dedup_feeds"] == 0
        assert stats["dedup_total_links"] == 0


class TestCleanState:
    """Testes para clean_state."""
    
    def test_clean_dedup(self):
        """Testa limpeza apenas de dedup."""
        state = {
            "dedup": {"feed1": ["link1", "link2"]},
            "http_cache": {"feed1": {"etag": "abc"}},
            "html_hashes": {"site1": "hash1"},
            "last_cleanup": 1234567890.0
        }
        
        new_state, stats_before = clean_state(state, "dedup")
        
        assert new_state["dedup"] == {}
        assert new_state["http_cache"] == state["http_cache"]  # Mantido
        assert new_state["html_hashes"] == state["html_hashes"]  # Mantido
        assert new_state["last_cleanup"] == state["last_cleanup"]  # Mantido
    
    def test_clean_http_cache(self):
        """Testa limpeza apenas de http_cache."""
        state = {
            "dedup": {"feed1": ["link1"]},
            "http_cache": {"feed1": {"etag": "abc"}},
            "html_hashes": {"site1": "hash1"}
        }
        
        new_state, _ = clean_state(state, "http_cache")
        
        assert new_state["dedup"] == state["dedup"]  # Mantido
        assert new_state["http_cache"] == {}
        assert new_state["html_hashes"] == state["html_hashes"]  # Mantido
    
    def test_clean_html_hashes(self):
        """Testa limpeza apenas de html_hashes."""
        state = {
            "dedup": {"feed1": ["link1"]},
            "http_cache": {"feed1": {"etag": "abc"}},
            "html_hashes": {"site1": "hash1"}
        }
        
        new_state, _ = clean_state(state, "html_hashes")
        
        assert new_state["dedup"] == state["dedup"]  # Mantido
        assert new_state["http_cache"] == state["http_cache"]  # Mantido
        assert new_state["html_hashes"] == {}
    
    def test_clean_tudo(self):
        """Testa limpeza de tudo."""
        state = {
            "dedup": {"feed1": ["link1"]},
            "http_cache": {"feed1": {"etag": "abc"}},
            "html_hashes": {"site1": "hash1"},
            "last_cleanup": 1234567890.0,
            "last_announced_hash": "abc123"
        }
        
        new_state, _ = clean_state(state, "tudo")
        
        assert new_state["dedup"] == {}
        assert new_state["http_cache"] == {}
        assert new_state["html_hashes"] == {}
        # Metadados devem ser mantidos
        assert "last_cleanup" in new_state
        assert "last_announced_hash" in new_state
    
    def test_clean_invalid_type(self):
        """Testa limpeza com tipo inválido."""
        state = {"dedup": {"feed1": ["link1"]}}
        
        # InvalidCleanTypeError herda de ValueError (exceção personalizada didática)
        with pytest.raises(ValueError, match="Tipo de limpeza inválido"):
            clean_state(state, "invalid_type")
        with pytest.raises(InvalidCleanTypeError, match="Tipo de limpeza inválido"):
            clean_state(state, "outro_invalido")


class TestBackup:
    """Testes para create_backup."""
    
    def test_create_backup_success(self):
        """Testa criação de backup bem-sucedida."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Cria arquivo de teste
            test_file = os.path.join(tmpdir, "test.json")
            test_data = {"test": "data"}
            save_json_safe(test_file, test_data)
            
            # Cria backup
            backup_dir = os.path.join(tmpdir, "backups")
            backup_path = create_backup(test_file, backup_dir)
            
            assert backup_path is not None
            assert os.path.exists(backup_path)
            assert "backup" in os.path.basename(backup_path)
            
            # Verifica conteúdo
            backup_data = load_json_safe(backup_path, {})
            assert backup_data == test_data
    
    def test_create_backup_nonexistent_file(self):
        """Testa backup de arquivo que não existe."""
        backup_path = create_backup("nonexistent.json", "backups")
        assert backup_path is None
    
    def test_create_backup_creates_directory(self):
        """Testa que cria diretório de backup se não existir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.json")
            save_json_safe(test_file, {"test": "data"})
            
            backup_dir = os.path.join(tmpdir, "new_backups")
            backup_path = create_backup(test_file, backup_dir)
            
            assert backup_path is not None
            assert os.path.exists(backup_dir)


class TestStateIntegration:
    """Testes de integração do fluxo completo."""
    
    def test_full_clean_flow(self):
        """Testa fluxo completo: stats -> backup -> clean -> stats."""
        state = {
            "dedup": {
                "https://feed1.com": ["link1", "link2"],
                "https://feed2.com": ["link3"]
            },
            "http_cache": {
                "https://feed1.com": {"etag": "abc"}
            },
            "html_hashes": {
                "https://site1.com": "hash1"
            }
        }
        
        # Estatísticas antes
        stats_before = get_state_stats(state)
        assert stats_before["dedup_total_links"] == 3
        
        # Limpa
        new_state, _ = clean_state(state, "dedup")
        
        # Estatísticas depois
        stats_after = get_state_stats(new_state)
        assert stats_after["dedup_total_links"] == 0
        assert stats_after["http_cache_urls"] == stats_before["http_cache_urls"]  # Mantido
