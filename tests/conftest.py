# Habilita pytest-asyncio para testes assíncronos
import pytest

pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async (pytest-asyncio)")


@pytest.fixture(autouse=True)
def _disjuntor_da_traducao_fechado():
    """O disjuntor do tradutor é estado de módulo: um teste que o abre não pode
    fazer o seguinte receber o original sem nem chamar o tradutor falso."""
    from utils.translator import _reset_disjuntor
    _reset_disjuntor()
    yield
    _reset_disjuntor()
