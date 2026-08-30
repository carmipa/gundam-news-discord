"""
Guarda do event loop (classe de defeito 3.8).

BeautifulSoup é CPU-bound e síncrono. Chamado de dentro de uma corrotina, prende
o event loop: enquanto corre, nada mais é despachado — incluindo o heartbeat do
gateway do Discord. Perder o heartbeat faz o Discord derrubar a conexão, e a
reconexão redispara o `on_ready` (classe 3.3).

Medido nesta VPS em 2026-08-30, com 12 páginas reais do catálogo: 2,88s de
bloqueio acumulado, pior caso 611ms numa página de 295KB. Extrapolado para os
~120 sites vigiados dá ~29s de loop parado por ciclo, contra ~41s de intervalo
de heartbeat.

A PROPRIEDADE MEDIDA é o atraso do event loop — não "se o parse acontece".
Foi essa a lição de um bot irmão: um teste afirmava "o async não chama
socket.getaddrinfo" e era falso, porque `loop.getaddrinfo` também chama, só que
noutra thread. A pergunta certa nunca é *se*, é *onde* e *com que efeito*.
"""
import asyncio
import os
import sys
import time

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.html_monitor import _limpar_e_extrair  # noqa: E402

# Página grande o suficiente para o parse ser mensurável — o defeito só aparece
# com volume, que é exatamente o caso real (páginas de 300-900KB no catálogo).
HTML_PESADO = (
    "<html><head><title>T</title></head><body>"
    + "<div class='x'>lorem ipsum dolor sit amet </div>" * 30000
    + "</body></html>"
)


async def _maior_atraso_do_loop(usar_executor: bool) -> float:
    """Devolve, em ms, o maior tempo em que o event loop ficou sem despachar."""
    parar = asyncio.Event()
    atrasos = []

    async def sonda():
        while not parar.is_set():
            t0 = time.perf_counter()
            await asyncio.sleep(0.01)
            atrasos.append((time.perf_counter() - t0 - 0.01) * 1000)

    tarefa = asyncio.create_task(sonda())
    await asyncio.sleep(0.05)

    loop = asyncio.get_running_loop()
    for _ in range(2):
        if usar_executor:
            await loop.run_in_executor(None, _limpar_e_extrair, HTML_PESADO)
        else:
            _limpar_e_extrair(HTML_PESADO)
        await asyncio.sleep(0.01)

    parar.set()
    await tarefa
    return max(atrasos) if atrasos else 0.0


class TestCalibracao:
    """Controle positivo primeiro: sem ele, um verde não distingue nada."""

    def test_o_defeito_realmente_bloqueia(self):
        # Se este teste parar de acusar, o instrumento deixou de medir o que
        # interessa (máquina rápida demais, HTML pequeno demais) e o teste
        # abaixo passa a aprovar por não enxergar nada.
        atraso = asyncio.run(_maior_atraso_do_loop(usar_executor=False))
        assert atraso > 100, (
            f"controle positivo falhou: o parse síncrono só bloqueou {atraso:.0f}ms. "
            "O instrumento não consegue distinguir bloqueio de não-bloqueio."
        )


class TestCorrecao:
    def test_executor_liberta_o_event_loop(self):
        ruim = asyncio.run(_maior_atraso_do_loop(usar_executor=False))
        bom = asyncio.run(_maior_atraso_do_loop(usar_executor=True))
        assert bom < ruim / 5, (
            f"o executor não libertou o loop: {bom:.0f}ms com executor "
            f"contra {ruim:.0f}ms sem. Esperado pelo menos 5x melhor."
        )


class TestEstrutura:
    """O parse tem de continuar fora do loop, mesmo que alguém edite o módulo."""

    @pytest.mark.parametrize("modulo, funcao", [
        ("core/html_monitor.py", "fetch_page_hash"),
        ("utils/opengraph.py", "fetch_og_image"),
    ])
    def test_corrotina_nao_chama_BeautifulSoup_diretamente(self, modulo, funcao):
        import ast

        arvore = ast.parse(open(os.path.join(_ROOT, modulo), encoding="utf-8").read())
        alvo = next(
            n for n in ast.walk(arvore)
            if isinstance(n, ast.AsyncFunctionDef) and n.name == funcao
        )
        diretas = [
            n for n in ast.walk(alvo)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "BeautifulSoup"
        ]
        assert not diretas, (
            f"{modulo}:{funcao} chama BeautifulSoup dentro da corrotina — "
            "isso prende o event loop e atrasa o heartbeat do Discord. "
            "Use loop.run_in_executor com a função síncrona extraída."
        )
