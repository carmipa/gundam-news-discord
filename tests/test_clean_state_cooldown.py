"""
Testes de regressão: o /clean_state tem de conhecer TODO o estado que existe.

Contexto: o cooldown do HTML Monitor (`html_monitor_posted`) foi acrescentado ao
state.json em 2026-08-01 e o `clean_state` não sabia dele. O efeito era subtil e
mau: limpar os hashes ("html_hashes" ou "tudo") fazia o ciclo seguinte
re-inicializar cada site — a deteção a seguir é legítima e devia gerar aviso —,
mas o cooldown sobrevivente suprimia esse aviso por 24h. E "tudo" deixava de
significar tudo.

O teste `test_nenhuma_chave_de_estado_fica_orfa` é a guarda genérica: qualquer
chave nova de estado que apareça no engine e não seja tratada aqui faz falhar.
"""
import importlib.util
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

_SPEC = importlib.util.spec_from_file_location(
    "_storage_under_test", os.path.join(_ROOT, "utils", "storage.py")
)
_storage = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_storage)
clean_state = _storage.clean_state
get_state_stats = _storage.get_state_stats


def state_cheio():
    """State com todas as chaves que o engine escreve, mais os metadados."""
    return {
        "dedup": {"https://feed.com": {"https://a.com/1": ["123"]}},
        "http_cache": {"https://feed.com": {"etag": "abc"}},
        "html_monitor": {"https://site.com": "hash1", "https://site2.com": "hash2"},
        "html_monitor_posted": {"https://site.com": 1754000000.0},
        "last_cleanup": 1753000000,
        "last_announced_hash": "abc1234",
    }


@pytest.fixture(autouse=True)
def _nao_toca_no_disco(tmp_path, monkeypatch):
    """clean_state zera history.json; redireciona para tmp em vez do repositório."""
    monkeypatch.setattr(_storage, "p", lambda nome: str(tmp_path / nome))


class TestCooldownEhLimpo:
    def test_html_hashes_limpa_o_cooldown_junto(self):
        novo, _ = clean_state(state_cheio(), "html_hashes")
        assert novo["html_monitor"] == {}
        assert novo["html_monitor_posted"] == {}, (
            "cooldown sobrevivente suprimiria por 24h o aviso da re-deteção "
            "legítima que a limpeza dos hashes provoca"
        )

    def test_tudo_limpa_o_cooldown(self):
        novo, _ = clean_state(state_cheio(), "tudo")
        assert novo["html_monitor_posted"] == {}

    def test_tudo_significa_tudo(self):
        novo, _ = clean_state(state_cheio(), "tudo")
        for chave in ("dedup", "http_cache", "html_monitor", "html_monitor_posted"):
            assert novo[chave] == {}, f"'{chave}' sobreviveu a uma limpeza 'tudo'"

    def test_dedup_nao_mexe_no_cooldown(self):
        # Limpezas cirúrgicas não podem ter efeitos colaterais noutras áreas.
        novo, _ = clean_state(state_cheio(), "dedup")
        assert novo["html_monitor_posted"] == {"https://site.com": 1754000000.0}
        assert novo["html_monitor"] != {}

    def test_http_cache_nao_mexe_no_cooldown(self):
        novo, _ = clean_state(state_cheio(), "http_cache")
        assert novo["html_monitor_posted"] == {"https://site.com": 1754000000.0}


class TestMetadadosPreservados:
    @pytest.mark.parametrize("tipo", ["dedup", "http_cache", "html_hashes", "tudo"])
    def test_metadados_sobrevivem(self, tipo):
        novo, _ = clean_state(state_cheio(), tipo)
        assert novo["last_cleanup"] == 1753000000
        assert novo["last_announced_hash"] == "abc1234"


class TestEstatisticas:
    def test_stats_contam_o_cooldown(self):
        stats = get_state_stats(state_cheio())
        assert stats["html_cooldown_sites"] == 1
        assert stats["html_hashes_sites"] == 2

    def test_stats_toleram_state_vazio(self):
        stats = get_state_stats({})
        assert stats["html_cooldown_sites"] == 0

    def test_stats_toleram_cooldown_malformado(self):
        stats = get_state_stats({"html_monitor_posted": "lixo"})
        assert stats["html_cooldown_sites"] == 0

    def test_stats_antes_refletem_o_estado_pre_limpeza(self):
        _, antes = clean_state(state_cheio(), "tudo")
        assert antes["dedup_total_links"] == 1
        assert antes["html_hashes_sites"] == 2


class TestContratoGenerico:
    def test_nenhuma_chave_de_estado_fica_orfa(self):
        """Guarda contra a próxima chave de estado esquecida no clean_state.

        Se o engine passar a escrever uma chave nova em state.json, ela tem de
        aparecer em `tratadas` (limpa) ou em `metadados` (preservada de propósito).
        Falhar aqui é o lembrete de decidir qual das duas.
        """
        tratadas = {"dedup", "http_cache", "html_monitor", "html_hashes",
                    "html_monitor_posted"}
        metadados = {"last_cleanup", "last_announced_hash"}

        origem = open(os.path.join(_ROOT, "core", "scanner", "engine.py"),
                      encoding="utf-8").read()
        import re
        escritas = set(re.findall(r'state\.setdefault\(\s*"([a-z_]+)"', origem))
        escritas |= set(re.findall(r'state\[\s*"([a-z_]+)"\s*\]\s*=', origem))

        orfas = escritas - tratadas - metadados
        assert not orfas, (
            f"chaves de state.json que o clean_state não trata: {sorted(orfas)}. "
            "Decida se devem ser limpas ou preservadas e atualize utils/storage.py."
        )
