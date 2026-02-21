# Habilita pytest-asyncio para testes assíncronos
import pytest

pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async (pytest-asyncio)")
