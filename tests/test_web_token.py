"""
Dashboard web com WEB_AUTH_TOKEN: a API exige o token e a página o envia.

Achado da auditoria de 2026-09-25: com WEB_AUTH_TOKEN definido, a página fazia
`fetch('/api/stats')` sem o header Authorization e recebia 401 para sempre — o
dashboard só funcionava sem autenticação. E o token era comparado com `!=`.

O servidor real (aiohttp) é exercitado por requisição HTTP. A execução do
JavaScript no navegador NÃO é feita aqui: o teste da página confere que o script
monta o header a partir do token guardado.
"""
import os

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import web.server as server


async def _cliente(monkeypatch, token):
    monkeypatch.setattr(server, "WEB_AUTH_TOKEN", token)
    app = web.Application()
    app.add_routes(server.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    return client


@pytest.mark.asyncio
async def test_sem_header_recebe_401(monkeypatch):
    client = await _cliente(monkeypatch, "s3gr3do")
    try:
        assert (await client.get("/api/stats")).status == 401
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_token_errado_recebe_403(monkeypatch):
    client = await _cliente(monkeypatch, "s3gr3do")
    try:
        r = await client.get("/api/stats", headers={"Authorization": "Bearer s3gr3dX"})
        assert r.status == 403
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_token_certo_recebe_os_numeros(monkeypatch):
    client = await _cliente(monkeypatch, "s3gr3do")
    try:
        r = await client.get("/api/stats", headers={"Authorization": "Bearer s3gr3do"})
        assert r.status == 200
        assert "scans" in await r.json()
    finally:
        await client.close()


def test_comparacao_do_token_e_em_tempo_constante():
    fonte = open(server.__file__, encoding="utf-8").read()
    assert "hmac.compare_digest(" in fonte
    assert "token != WEB_AUTH_TOKEN" not in fonte


def test_pagina_envia_o_token_guardado_no_header():
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html = open(os.path.join(raiz, "web", "templates", "index.html"), encoding="utf-8").read()
    assert "headers['Authorization'] = 'Bearer ' + t" in html
    assert "fetch('/api/stats', { headers })" in html
    assert "location.hash" in html, "o token entra pelo fragmento, que não vai ao servidor"
