"""
Teste de Idempotência (Evitar Duplicidade).

Essencial para bots que monitoram feeds: o bot não pode alertar sobre a mesma coisa
duas vezes. Valida que o id único (link) é verificado antes da escrita no dedup.
"""
import pytest
from utils.storage import get_state_stats


def _register_link_in_dedup(state: dict, feed_url: str, link: str) -> dict:
    """
    Simula a lógica do scanner: registra um link no dedup apenas se ainda não existir.
    Retorna o state atualizado (idempotente: mesmo link duas vezes = um registro).
    """
    state.setdefault("dedup", {})
    state["dedup"].setdefault(feed_url, [])
    if link not in state["dedup"][feed_url]:
        state["dedup"][feed_url].append(link)
    return state


class TestDedupIdempotency:
    """Garante que o tamanho da lista no dedup não aumenta ao registrar o mesmo evento duas vezes."""

    def test_same_link_twice_list_size_unchanged(self):
        """Registrar a mesma vulnerabilidade/evento duas vezes: tamanho da lista permanece 1."""
        feed_url = "https://example.com/feed.xml"
        link = "https://example.com/news/123"

        state = {"dedup": {}}
        state = _register_link_in_dedup(state, feed_url, link)
        stats_after_first = get_state_stats(state)
        assert stats_after_first["dedup_total_links"] == 1

        # Segunda vez: mesmo link não deve ser duplicado
        state = _register_link_in_dedup(state, feed_url, link)
        stats_after_second = get_state_stats(state)
        assert stats_after_second["dedup_total_links"] == 1, (
            "Idempotência falhou: o mesmo link foi registrado duas vezes."
        )

    def test_same_link_twice_dedup_list_unchanged(self):
        """Valida que a lista interna do feed permanece com um único elemento."""
        feed_url = "https://feed.example.com/rss"
        link = "https://feed.example.com/article/456"

        state = {"dedup": {}}
        for _ in range(3):  # Tentativa de registrar 3 vezes
            state = _register_link_in_dedup(state, feed_url, link)

        assert feed_url in state["dedup"]
        assert state["dedup"][feed_url] == [link]
        assert len(state["dedup"][feed_url]) == 1

    def test_different_links_increase_count(self):
        """Links diferentes aumentam o contador (comportamento esperado)."""
        feed_url = "https://example.com/feed"
        state = {"dedup": {}}

        for i in range(5):
            state = _register_link_in_dedup(state, feed_url, f"https://example.com/item/{i}")

        stats = get_state_stats(state)
        assert stats["dedup_total_links"] == 5
        assert len(state["dedup"][feed_url]) == 5
