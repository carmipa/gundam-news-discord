"""
Teste de Timeout e Resiliência de API.

Valida que o cliente HTTP possui timeouts de conexão e leitura configurados
(no máximo 10 segundos) e testa o comportamento quando a API externa não responde,
evitando que o bot "congele".
"""
import asyncio
import pytest
import aiohttp
from settings import HTTP_TIMEOUT


class TestHttpTimeoutConfig:
    """Timeouts de conexão e leitura devem estar configurados."""

    def test_http_timeout_configured_max_10_seconds(self):
        """Valida que HTTP_TIMEOUT existe e é no máximo 10 segundos."""
        assert hasattr(HTTP_TIMEOUT, "__int__") or isinstance(HTTP_TIMEOUT, (int, float))
        timeout_sec = int(HTTP_TIMEOUT)
        assert timeout_sec > 0, "Timeout deve ser positivo."
        assert timeout_sec <= 10, "Timeout deve ser no máximo 10 segundos para manter disponibilidade."

    def test_aiohttp_timeout_usage(self):
        """Garante que o timeout é aplicado em quem faz o pedido HTTP.

        A asserção olhava o código de `run_scan_once`, mas o refactor `01ba2c9`
        moveu a construção do ClientTimeout para `fetch_feed`, em
        core/scanner/fetcher.py. O teste passou a falhar sem que nada estivesse
        de facto errado — invariante certa, sítio errado.
        """
        import inspect
        from core.scanner.fetcher import fetch_feed, _fetch_feed_url

        origem = inspect.getsource(fetch_feed)
        assert "ClientTimeout" in origem, (
            "fetch_feed deve construir um aiohttp.ClientTimeout."
        )
        assert "FEED_HTTP_TIMEOUT_MAX_SEC" in origem, (
            "O timeout por fonte deve ser limitado pelo teto de settings."
        )
        # E o timeout tem de chegar ao pedido em si, não só ser calculado.
        assert "timeout=timeout" in inspect.getsource(_fetch_feed_url), (
            "O GET deve receber o timeout construído."
        )

        t = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        assert t.total == HTTP_TIMEOUT


class TestHttpResilienceWhenApiDoesNotRespond:
    """Comportamento quando a API externa não responde."""

    @pytest.mark.asyncio
    async def test_client_raises_timeout_when_server_hangs(self):
        """Cliente com timeout deve levantar TimeoutError quando o servidor não responde."""
        # Servidor local que aceita conexão mas nunca envia resposta
        async def no_response_server(reader, writer):
            await asyncio.sleep(100)

        server = await asyncio.start_server(no_response_server, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        url = f"http://127.0.0.1:{port}/"

        timeout = aiohttp.ClientTimeout(total=1)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                with pytest.raises((asyncio.TimeoutError, aiohttp.ServerTimeoutError, aiohttp.ClientError, OSError)):
                    await session.get(url)
        finally:
            server.close()
            await server.wait_closed()
