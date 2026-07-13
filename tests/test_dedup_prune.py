"""
Testes para a auto-poda do dedup do state.json (prune_dedup).

Garante que o state.json não cresça indefinidamente: o dedup é alinhado à
janela dos últimos HISTORY_LIMIT links enviados (definida pelo history).
"""
import importlib.util
import os

# Carrega processor.py isoladamente para não puxar core.scanner.__init__ (que
# importa o engine -> discord). prune_dedup é lógica pura (utils/settings apenas).
_PROC_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "scanner", "processor.py")
_spec = importlib.util.spec_from_file_location("_processor_under_test", _PROC_PATH)
_processor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_processor)
prune_dedup = _processor.prune_dedup


class TestPruneDedup:
    def test_removes_links_outside_history_window(self):
        """Links que não estão no history (ex.: vistos mas filtrados) são descartados."""
        dedup = {
            "https://feed1.com": {
                "https://a.com/1": ["123"],   # postado -> está no history
                "https://a.com/2": [],        # visto mas filtrado -> lixo
            },
            "https://feed2.com": {
                "https://b.com/9": [],        # lixo
            },
        }
        keep = {"https://a.com/1"}

        before, after = prune_dedup(dedup, keep)

        assert before == 3
        assert after == 1
        assert dedup == {"https://feed1.com": {"https://a.com/1": ["123"]}}

    def test_empty_feed_is_removed(self):
        """Feed que fica sem links é removido por completo."""
        dedup = {"https://feed.com": {"https://x.com/1": []}}
        before, after = prune_dedup(dedup, keep_links=set())

        assert (before, after) == (1, 0)
        assert dedup == {}

    def test_keeps_posted_links_in_window(self):
        """Links dentro da janela permanecem intactos (proteção anti-repost)."""
        dedup = {
            "https://feed.com": {
                "https://x.com/1": ["100", "200"],
                "https://x.com/2": ["300"],
            }
        }
        keep = {"https://x.com/1", "https://x.com/2"}
        before, after = prune_dedup(dedup, keep)

        assert (before, after) == (2, 2)
        assert dedup["https://feed.com"]["https://x.com/1"] == ["100", "200"]

    def test_ignores_malformed_feed_entries(self):
        """Entradas malformadas (não-dict) são removidas sem quebrar."""
        dedup = {
            "https://ok.com": {"https://x.com/1": ["1"]},
            "https://bad.com": ["not", "a", "dict"],
        }
        before, after = prune_dedup(dedup, {"https://x.com/1"})

        assert after == 1
        assert "https://bad.com" not in dedup

    def test_non_dict_input_is_safe(self):
        """Entrada inesperada não levanta exceção."""
        assert prune_dedup(None, {"x"}) == (0, 0)
        assert prune_dedup([], {"x"}) == (0, 0)
