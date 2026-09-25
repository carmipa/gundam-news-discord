"""
O canal configurado de uma guild só sai do config por sinal definitivo.

Achado da auditoria de 2026-09-25: no arranque, `get_channel() is None` fazia o
bot gravar `channel_id = None`. Esse None também acontece com guild
momentaneamente indisponível (queda parcial do Discord); a guild perdia a
configuração para sempre, em silêncio, e ninguém sabia por que parou de receber.

Caso-controle de fronteira (A1): o mesmo sinal ("canal não encontrado") no
arranque MANTÉM a configuração; o canal realmente apagado (evento
on_guild_channel_delete) a remove; apagar OUTRO canal da guild não mexe nela.
"""
import json
from unittest.mock import MagicMock

import pytest

import utils.storage as storage


@pytest.fixture
def main_mod(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    storage.invalidate_json_cache(storage.p("config.json"))
    import bot.canais
    return bot.canais


def gravar_config(cfg):
    storage.save_json_safe(storage.p("config.json"), cfg)
    storage.invalidate_json_cache(storage.p("config.json"))


def ler_config():
    with open(storage.p("config.json"), encoding="utf-8") as f:
        return json.load(f)


def test_canal_invisivel_no_arranque_mantem_a_configuracao(main_mod):
    gravar_config({"111": {"channel_id": 555, "filters": ["todos"]}})
    bot = MagicMock()
    bot.get_channel.return_value = None
    main_mod._preparar_views_e_canais(bot)
    assert ler_config()["111"]["channel_id"] == 555


def test_canal_apagado_de_fato_e_desvinculado_e_filtros_ficam(main_mod):
    gravar_config({"111": {"channel_id": 555, "filters": ["todos"], "language": "pt_BR"}})
    assert main_mod.desvincular_canal_apagado(111, 555) is True
    cfg = ler_config()["111"]
    assert cfg["channel_id"] is None
    assert cfg["filters"] == ["todos"] and cfg["language"] == "pt_BR"


def test_apagar_outro_canal_da_guild_nao_mexe(main_mod):
    gravar_config({"111": {"channel_id": 555}})
    assert main_mod.desvincular_canal_apagado(111, 999) is False
    assert ler_config()["111"]["channel_id"] == 555


def test_canal_de_outra_guild_nao_mexe(main_mod):
    gravar_config({"111": {"channel_id": 555}, "222": {"channel_id": 777}})
    assert main_mod.desvincular_canal_apagado(222, 555) is False
    assert ler_config()["111"]["channel_id"] == 555


def test_main_liga_o_evento_de_canal_apagado():
    """O evento é o único caminho que remove o canal; sem ele, canal apagado fica para sempre."""
    import ast
    import os

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    arvore = ast.parse(open(os.path.join(raiz, "main.py"), encoding="utf-8").read())
    handlers = [
        n for n in ast.walk(arvore)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "on_guild_channel_delete"
    ]
    assert handlers, "main.py não registra on_guild_channel_delete"
    chamadas = [
        c for c in ast.walk(handlers[0])
        if isinstance(c, ast.Call) and getattr(c.func, "id", "") == "desvincular_canal_apagado"
    ]
    assert chamadas
