"""
Guarda estrutural do arranque (classe de defeito 3.3).

Exceção levantada dentro de um handler de evento do discord.py é apenas
REGISTADA por ele — e tudo o que viria depois no mesmo handler deixa de correr.
Como `start_scheduler` é o último passo do `on_ready`, qualquer acessório
desprotegido antes dele produz o pior modo de falha possível: bot online,
respondendo a comandos, que NUNCA varre. Sem erro visível para quem usa.

O cenário é alcançável e não teórico: `_startup_done` só é marcado no FIM do
handler, portanto uma falha num passo intermédio faz a reconexão seguinte
reexecutar o `on_ready` — e aí `site.start()` encontra a porta já aberta pela
tentativa anterior e levanta OSError(EADDRINUSE). O bot fica mudo até alguém
reiniciar o contêiner.

Esta guarda é ESTRUTURAL (lê o código-fonte) porque o defeito é de ordenação e
proteção, não de valor calculado — não há retorno para afirmar sobre.
"""
import ast
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MAIN = os.path.join(_ROOT, "main.py")


def _on_ready():
    """Devolve o nó AST do handler on_ready."""
    arvore = ast.parse(open(_MAIN, encoding="utf-8").read())
    for no in ast.walk(arvore):
        if isinstance(no, ast.AsyncFunctionDef) and no.name == "on_ready":
            return no
    raise AssertionError("on_ready não encontrado em main.py")


def _protegido_por_try(no_alvo, raiz) -> bool:
    """True se `no_alvo` estiver dentro do corpo de algum try com handler."""
    for no in ast.walk(raiz):
        if isinstance(no, ast.Try) and no.handlers:
            for filho in ast.walk(ast.Module(body=no.body, type_ignores=[])):
                if filho is no_alvo:
                    return True
    return False


class TestAcessoriosNaoDerrubamAVarredura:
    def test_start_web_server_esta_protegido(self):
        on_ready = _on_ready()
        chamadas = [
            n for n in ast.walk(on_ready)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "start_web_server"
        ]
        assert chamadas, "start_web_server não é chamado no on_ready"
        for c in chamadas:
            assert _protegido_por_try(c, on_ready), (
                "start_web_server sem try/except no on_ready: uma porta ocupada "
                "(EADDRINUSE) faz o scheduler nunca arrancar e o bot fica mudo"
            )

    def test_preparo_de_views_esta_protegido(self):
        on_ready = _on_ready()
        chamadas = [
            n for n in ast.walk(on_ready)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "_preparar_views_e_canais"
        ]
        assert chamadas, "_preparar_views_e_canais não é chamado no on_ready"
        for c in chamadas:
            assert _protegido_por_try(c, on_ready), (
                "o preparo de views grava config em disco e pode levantar; "
                "sem proteção, disco cheio impede a varredura de arrancar"
            )

    def test_start_scheduler_e_alcancavel(self):
        """O essencial não pode estar dentro de um try que o pule silenciosamente."""
        on_ready = _on_ready()
        chamadas = [
            n for n in ast.walk(on_ready)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "start_scheduler"
        ]
        assert chamadas, "start_scheduler não é chamado no on_ready"


class TestCalibracao:
    """A guarda foi vista REPROVANDO o defeito reintroduzido?"""

    def test_guarda_apanha_await_desprotegido(self):
        codigo = (
            "async def on_ready():\n"
            "    await start_web_server()\n"
            "    start_scheduler(bot)\n"
        )
        arvore = ast.parse(codigo)
        on_ready = next(
            n for n in ast.walk(arvore)
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "on_ready"
        )
        chamada = next(
            n for n in ast.walk(on_ready)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "start_web_server"
        )
        assert _protegido_por_try(chamada, on_ready) is False, (
            "a guarda TEM de acusar o padrão antigo; se aprovar, não protege nada"
        )

    def test_guarda_aprova_await_protegido(self):
        codigo = (
            "async def on_ready():\n"
            "    try:\n"
            "        await start_web_server()\n"
            "    except Exception:\n"
            "        pass\n"
            "    start_scheduler(bot)\n"
        )
        arvore = ast.parse(codigo)
        on_ready = next(
            n for n in ast.walk(arvore)
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "on_ready"
        )
        chamada = next(
            n for n in ast.walk(on_ready)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "start_web_server"
        )
        assert _protegido_por_try(chamada, on_ready) is True, (
            "controle negativo: a guarda não pode acusar código já correto"
        )
