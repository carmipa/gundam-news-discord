"""
Teste de Concorrência (Thread-Safety) — Python.

Simula várias threads/coroutines adicionando registros simultaneamente ao mesmo
serviço de persistência (state/JSON). Valida que não há perda de dados nem
exceções de concorrência (ex.: race ao escrever o mesmo arquivo).
"""
import asyncio
import json
import os
import tempfile
import pytest
from utils.storage import load_json_safe, save_json_safe


# Lock compartilhado simula o scan_lock usado no scanner
_storage_lock = asyncio.Lock()


async def add_record_under_lock(filepath: str, feed_url: str, link: str) -> None:
    """Lê state, adiciona um link ao dedup do feed, salva. Deve ser chamado com lock no scanner."""
    async with _storage_lock:
        state = load_json_safe(filepath, {})
        state.setdefault("dedup", {})
        state["dedup"].setdefault(feed_url, [])
        if link not in state["dedup"][feed_url]:
            state["dedup"][feed_url].append(link)
        save_json_safe(filepath, state)


def _count_links(state: dict) -> int:
    total = 0
    dedup = state.get("dedup", {})
    if isinstance(dedup, dict):
        for links in dedup.values():
            if isinstance(links, list):
                total += len(links)
    return total


class TestConcurrency:
    """Garante que travas de leitura/escrita evitam perda de dados e exceções."""

    @pytest.mark.asyncio
    async def test_100_concurrent_adds_no_data_loss(self):
        """Simula 100 coroutines adicionando registros ao mesmo arquivo com lock."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            save_json_safe(filepath, {"dedup": {}})
            feed_url = "https://concurrent.test/feed"

            async def add_one(i: int) -> None:
                await add_record_under_lock(filepath, feed_url, f"https://test.com/item/{i}")

            tasks = [add_one(i) for i in range(100)]
            await asyncio.gather(*tasks)

            state = load_json_safe(filepath, {})
            total = _count_links(state)
            assert total == 100, f"Perda de dados: esperado 100 registros, obtido {total}"
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    @pytest.mark.asyncio
    async def test_concurrent_writes_no_exception(self):
        """Múltiplas escritas concorrentes não devem levantar exceção de concorrência."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            save_json_safe(filepath, {"dedup": {"https://x.com": []}})

            async def write_once(i: int) -> None:
                state = load_json_safe(filepath, {})
                state.setdefault("dedup", {})
                state["dedup"].setdefault("https://x.com", []).append(f"link-{i}")
                save_json_safe(filepath, state)

            # Sem lock propositalmente para testar que save_json_safe não quebra
            # (pode haver sobrescrita, mas não exceção)
            tasks = [write_once(i) for i in range(20)]
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                pytest.fail(f"Exceção de concorrência inesperada: {e}")

            # Arquivo deve continuar JSON válido
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "dedup" in data
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)

    def test_threaded_save_json_safe_no_corruption(self):
        """Várias threads chamando save_json_safe no mesmo arquivo: resultado final é JSON válido."""
        import threading
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            save_json_safe(filepath, {"counter": 0})

            def write_n_times(n: int) -> None:
                for _ in range(n):
                    data = load_json_safe(filepath, {"counter": 0})
                    data["counter"] = data.get("counter", 0) + 1
                    save_json_safe(filepath, data)

            threads = [threading.Thread(target=write_n_times, args=(10,)) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert "counter" in data
            assert isinstance(data["counter"], (int, float))
        finally:
            if os.path.exists(filepath):
                os.unlink(filepath)
