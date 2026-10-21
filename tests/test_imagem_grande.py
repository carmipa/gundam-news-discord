"""
Imagem da notícia grande (set_image) quando ela aguenta; miniatura quando não.

Pedido de Paulo, 2026-10-21: os cards do bot de Gundam saíam com a imagem
pequena no canto, enquanto o bot de anime mostra a foto grande. Medido no mesmo
dia (4 notícias por fonte): hayamimi 1200x600, ANN 600x315, Reddit misto
(1200x630, 640x1137 e cortes 140x140) e Google News sempre o logo 300x300.

Casos de fronteira (A1):
  - imagem larga sai grande / imagem de 140 px (mesmo sinal: "tem imagem") fica
    miniatura, e exatamente 300 px já sai grande;
  - link do Google News não busca og:image / link comum busca, inclusive com
    imagem hospedada em googleusercontent (Blogger) — o mesmo domínio do logo;
  - corte do Reddit vira o original quando ele existe / continua o corte quando
    o original não responde.
Gabarito (A3) das dimensões: as especificações dos formatos (PNG IHDR, GIF
logical screen, JPEG SOF0, WebP VP8X), não a saída do parser.
"""
import asyncio
import struct

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
import aiohttp
from unittest.mock import MagicMock

import core.scanner.notifier as notifier
import utils.imagem as imagem
from utils.imagem import (
    LARGURA_MINIMA_GRANDE,
    apresentacao_da_imagem,
    dimensoes,
    eh_link_do_google_news,
    versao_cheia_do_reddit,
)


def png(w, h):
    ihdr = struct.pack(">II", w, h) + b"\x08\x02\x00\x00\x00"
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\x00" * 4


def gif(w, h):
    return b"GIF89a" + struct.pack("<HH", w, h) + b"\x00" * 6


def jpeg(w, h):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
    sof0 = b"\xff\xc0" + struct.pack(">HBHH", 17, 8, h, w) + b"\x03" + b"\x00" * 9
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


def jpeg_com_exif_grande(w, h, exif=20000):
    """JPEG cujo marcador de tamanho vem DEPOIS de ~20 KB de EXIF, como o da
    hobby.watch.impress medido em produção (SOF2 no byte 23282)."""
    app1 = b"\xff\xe1" + struct.pack(">H", exif + 2) + b"\x00" * exif
    sof2 = b"\xff\xc2" + struct.pack(">HBHH", 17, 8, h, w) + b"\x03" + b"\x00" * 9
    return b"\xff\xd8" + app1 + sof2 + b"\xff\xd9"


def webp_vp8x(w, h):
    corpo = b"VP8X" + struct.pack("<I", 10) + b"\x00\x00\x00\x00" + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little")
    return b"RIFF" + struct.pack("<I", 4 + len(corpo)) + b"WEBP" + corpo


class TestDimensoes:
    @pytest.mark.parametrize("fabrica", [png, gif, jpeg, webp_vp8x])
    def test_le_largura_e_altura_do_cabecalho(self, fabrica):
        assert dimensoes(fabrica(1200, 600)) == (1200, 600)

    def test_cabecalho_truncado_ou_desconhecido_nao_inventa_tamanho(self):
        assert dimensoes(png(1200, 600)[:12]) is None
        assert dimensoes(b"<html>nao e imagem</html>") is None
        assert dimensoes(b"") is None


class TestRedditCheio:
    def test_corte_de_140_vira_o_original(self):
        corte = "https://preview.redd.it/0snv2e4jxowh1.jpeg?width=140&height=140&crop=1:1,smart&auto=webp&s=abc"
        assert versao_cheia_do_reddit(corte) == "https://i.redd.it/0snv2e4jxowh1.jpeg"

    def test_outras_urls_nao_sao_mexidas(self):
        assert versao_cheia_do_reddit("https://external-preview.redd.it/abc.jpg?width=640") is None
        assert versao_cheia_do_reddit("https://i.redd.it/abc.jpeg") is None
        assert versao_cheia_do_reddit("https://share.redd.it/preview/post/1x8fazi") is None
        assert versao_cheia_do_reddit(None) is None


class TestGoogleNewsSemLogo:
    def test_reconhece_o_host_do_google_news(self):
        assert eh_link_do_google_news("https://news.google.com/rss/articles/CBMi...?oc=5") is True
        assert eh_link_do_google_news("https://en.gundam-official.com/news/123") is False
        assert eh_link_do_google_news("https://news.google.com.evil.example/x") is False

    @pytest.mark.asyncio
    async def test_google_news_nao_busca_og_e_link_comum_busca(self, monkeypatch):
        buscados = []

        async def og_falso(link, session):
            buscados.append(link)
            return "https://lh3.googleusercontent.com/blogger_img_proxy/foto.jpg"

        monkeypatch.setattr(notifier, "fetch_og_image", og_falso)
        sessao = object()
        google = {"link": "https://news.google.com/rss/articles/CBMiXXX?oc=5"}
        blog = {"link": "https://gunjap.blogspot.com/2026/10/hg-rick-dom.html"}

        assert await notifier.resolve_thumbnail(google, sessao) is None
        assert await notifier.resolve_thumbnail(blog, sessao) == (
            "https://lh3.googleusercontent.com/blogger_img_proxy/foto.jpg"
        )
        assert buscados == [blog["link"]]


@pytest.fixture
async def servidor():
    imagens = {
        "/larga.png": png(1200, 600),
        "/limite.png": png(LARGURA_MINIMA_GRANDE, 300),
        "/abaixo.png": png(LARGURA_MINIMA_GRANDE - 1, 299),
        "/corte.jpg": jpeg(140, 140),
        "/original.jpg": jpeg(1600, 1200),
    }

    async def servir(request):
        if request.path == "/exif-picado.jpg":
            # Entrega em pedaços de 1 KB: o primeiro read() devolve só o que
            # chegou, como o servidor real fazia.
            resp = web.StreamResponse(status=206, headers={"Content-Type": "image/jpeg"})
            await resp.prepare(request)
            corpo = jpeg_com_exif_grande(1200, 1600)
            for i in range(0, len(corpo), 1024):
                await resp.write(corpo[i:i + 1024])
                await asyncio.sleep(0)
            await resp.write_eof()
            return resp
        corpo = imagens.get(request.path)
        if corpo is None:
            return web.Response(status=404)
        return web.Response(body=corpo, content_type="image/png")

    app = web.Application()
    app.router.add_get("/{nome}", servir)
    srv = TestServer(app)
    await srv.start_server()
    imagem._cache.clear()
    async with aiohttp.ClientSession() as sessao:
        yield srv, sessao
    await srv.close()
    imagem._cache.clear()


def url(srv, caminho):
    return str(srv.make_url(caminho))


class TestApresentacao:
    @pytest.mark.asyncio
    async def test_larga_sai_grande_e_140_fica_miniatura(self, servidor):
        srv, s = servidor
        assert await apresentacao_da_imagem(url(srv, "/larga.png"), s) == (url(srv, "/larga.png"), True)
        assert await apresentacao_da_imagem(url(srv, "/corte.jpg"), s) == (url(srv, "/corte.jpg"), False)

    @pytest.mark.asyncio
    async def test_cabecalho_que_chega_em_pedacos_e_lido_ate_o_fim(self, servidor):
        srv, s = servidor
        assert await apresentacao_da_imagem(url(srv, "/exif-picado.jpg"), s) == (url(srv, "/exif-picado.jpg"), True)

    @pytest.mark.asyncio
    async def test_fronteira_de_300_px(self, servidor):
        srv, s = servidor
        assert (await apresentacao_da_imagem(url(srv, "/limite.png"), s))[1] is True
        assert (await apresentacao_da_imagem(url(srv, "/abaixo.png"), s))[1] is False

    @pytest.mark.asyncio
    async def test_tamanho_desconhecido_fica_miniatura_como_antes(self, servidor):
        srv, s = servidor
        assert await apresentacao_da_imagem(url(srv, "/sumiu.png"), s) == (url(srv, "/sumiu.png"), False)
        assert await apresentacao_da_imagem("https://x.example/a.png", None) == ("https://x.example/a.png", False)
        assert "https://x.example/a.png" not in imagem._cache, "sem sessão não pode fixar o resultado"

    @pytest.mark.asyncio
    async def test_reddit_usa_o_original_quando_ele_responde(self, servidor, monkeypatch):
        srv, s = servidor
        monkeypatch.setattr(imagem, "versao_cheia_do_reddit", lambda u: url(srv, "/original.jpg"))
        assert await apresentacao_da_imagem(url(srv, "/corte.jpg"), s) == (url(srv, "/original.jpg"), True)

    @pytest.mark.asyncio
    async def test_reddit_mantem_o_corte_quando_o_original_nao_responde(self, servidor, monkeypatch):
        srv, s = servidor
        monkeypatch.setattr(imagem, "versao_cheia_do_reddit", lambda u: url(srv, "/nao-existe.jpg"))
        assert await apresentacao_da_imagem(url(srv, "/corte.jpg"), s) == (url(srv, "/corte.jpg"), False)

    @pytest.mark.asyncio
    async def test_uma_sonda_por_url(self, servidor, monkeypatch):
        srv, s = servidor
        chamadas = []
        sondar_real = imagem._sondar

        async def contar(u, sessao):
            chamadas.append(u)
            return await sondar_real(u, sessao)

        monkeypatch.setattr(imagem, "_sondar", contar)
        for _ in range(3):
            await apresentacao_da_imagem(url(srv, "/larga.png"), s)
        assert len(chamadas) == 1


class TestEmbedFinal:
    """A6: a decisão chega ao objeto que vai para o Discord, não só à função."""

    @pytest.fixture(autouse=True)
    def _sem_traducao(self, monkeypatch):
        async def identidade(texto, lang):
            return texto

        monkeypatch.setattr(notifier, "translate_to_target", identidade)
        monkeypatch.setattr(notifier, "imagem_publicavel", lambda u: u)

    def _bot(self):
        bot = MagicMock()
        bot.user = None
        return bot

    @pytest.mark.asyncio
    async def test_imagem_larga_vai_para_image(self, servidor):
        srv, s = servidor
        entry = {"title": "HG Rick Dom", "summary": "kit", "link": "https://hayamimi-gunpla.com/x"}
        embed = await notifier.create_embed(self._bot(), entry, "pt_BR", {}, session=s, thumbnail_url=url(srv, "/larga.png"))
        assert embed.image.url == url(srv, "/larga.png")
        assert embed.thumbnail.url is None

    @pytest.mark.asyncio
    async def test_imagem_pequena_continua_miniatura(self, servidor):
        srv, s = servidor
        entry = {"title": "Post", "summary": "x", "link": "https://www.reddit.com/r/Gunpla/comments/1/x/"}
        embed = await notifier.create_embed(self._bot(), entry, "pt_BR", {}, session=s, thumbnail_url=url(srv, "/corte.jpg"))
        assert embed.thumbnail.url == url(srv, "/corte.jpg")
        assert embed.image.url is None
