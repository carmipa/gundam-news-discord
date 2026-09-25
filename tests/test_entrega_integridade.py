"""
Integridade da entrega no ciclo de varredura (core/scanner/engine.run_scan_once).

Achados da auditoria de 2026-09-25, cada um com o caso doente e o legítimo que
carrega o mesmo sinal (A1):

  1. Corrida no config: o engine iterava o MESMO dict que /dashboard altera,
     com `await` no meio. Guild nova durante a varredura -> RuntimeError antes
     de gravar o que já tinha saído -> repostagem no ciclo seguinte.
  2. Falha numa guild perdia a notícia para ela se OUTRA guild recebeu: o link
     ia para o history e o ciclo seguinte o pulava antes do dedup por guild.
  3. Feed sem post na janela era apagado do dedup pela poda e voltava como
     "cold start", publicando itens de meses ignorando a janela de 7 dias.
  4. Com o feed servido por fallback, a falha de entrega descartava só o ETag da
     URL canônica; o do fallback devolvia 304 e a notícia se perdia.
  5. Monitor HTML gravava o hash novo antes de entregar: falha em todas as
     guilds = mudança nunca anunciada.
  6. Estado só era gravado no fim: container morto no meio = repostagem.

O harness roda o `run_scan_once` real, com rede, Discord e tradução falsos, e
lê o state.json e o history.json gravados em disco (A6: a verificação alcança a
persistência, não só a memória).
"""
import json
import time
from typing import Any, Dict, List, Optional

import feedparser
import pytest
from unittest.mock import MagicMock

import core.scanner.engine as engine

FEED = "https://feed.exemplo/rss"
FEED2 = "https://feed2.exemplo/rss"
FALLBACK = "https://espelho.exemplo/rss"


def entrada(link: str, dias_atras: Optional[float] = None) -> feedparser.FeedParserDict:
    e = feedparser.FeedParserDict()
    e["link"] = link
    e["title"] = f"Gundam {link}"
    e["summary"] = "Gundam"
    if dias_atras is not None:
        e["published_parsed"] = time.gmtime(time.time() - dias_atras * 86400)
    return e


class Canal:
    def __init__(self, nome: str):
        self.nome = nome
        self.enviados: List[str] = []
        self.falhar = False
        self.ao_enviar = None

    async def send(self, content=None, embed=None):
        if self.ao_enviar:
            self.ao_enviar(self)
        if self.falhar:
            raise RuntimeError(f"Discord 503 em {self.nome}")
        self.enviados.append(embed["link"])


class Cenario:
    """Monta o mundo falso em volta do run_scan_once real."""

    def __init__(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        self.tmp = tmp_path
        self.config: Dict[str, Any] = {}
        self.canais: Dict[int, Canal] = {}
        self.feeds: Dict[str, List[Any]] = {}
        self.sources: List[Dict[str, Any]] = []
        self.etag_por_chave: Dict[str, str] = {}
        self.html_updates: List[Dict[str, Any]] = []
        self.html_novo_estado: Optional[Dict[str, str]] = None
        self.bot = MagicMock()
        self.bot.get_channel = lambda cid: self.canais.get(int(cid))

        async def fetch_feed(session, src, http_cache):
            url = src["url"]
            for chave, etag in self.etag_por_chave.items():
                if chave == url or chave in (src.get("metadata", {}).get("fallbacks") or []):
                    http_cache[chave] = {"etag": etag}
            return url, list(self.feeds.get(url, [])), "titulo"

        async def check_official_sites(estado):
            novo = dict(estado)
            novo.update(self.html_novo_estado or {})
            return list(self.html_updates), novo

        async def create_embed(bot, entry, lang, config, session=None, thumbnail_url=None):
            return {"link": entry["link"]}

        async def resolve_thumbnail(entry, session):
            return None

        monkeypatch.setattr(engine, "load_config_cached", lambda default=None: self.config)
        monkeypatch.setattr(engine, "load_sources", lambda: self.sources)
        monkeypatch.setattr(engine, "fetch_feed", fetch_feed)
        monkeypatch.setattr(engine, "check_official_sites", check_official_sites)
        monkeypatch.setattr(engine, "create_embed", create_embed)
        monkeypatch.setattr(engine, "resolve_thumbnail", resolve_thumbnail)
        monkeypatch.setattr(engine, "match_intel", lambda *a, **k: True)
        monkeypatch.setattr(engine, "save_translation_cache", lambda: None)
        monkeypatch.setattr(engine, "FEED_FETCH_JITTER_MIN", 0.0)
        monkeypatch.setattr(engine, "FEED_FETCH_JITTER_MAX", 0.0)

    def guild(self, gid: str, canal_id: int) -> Canal:
        self.config[gid] = {"channel_id": canal_id, "filters": ["todos"], "language": "en_US"}
        canal = Canal(gid)
        self.canais[canal_id] = canal
        return canal

    def fonte(self, url: str, entradas: List[Any], fallbacks: Optional[List[str]] = None) -> None:
        meta = {"url": url}
        if fallbacks:
            meta["fallbacks"] = fallbacks
        self.sources.append({"url": url, "metadata": meta})
        self.feeds[url] = entradas

    def gravar_state(self, state: Dict[str, Any]) -> None:
        (self.tmp / "state.json").write_text(json.dumps(state), encoding="utf-8")

    def state(self) -> Dict[str, Any]:
        return json.loads((self.tmp / "state.json").read_text(encoding="utf-8"))

    def history(self) -> List[str]:
        f = self.tmp / "history.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []

    async def varrer(self):
        await engine.run_scan_once(self.bot, trigger="teste")


@pytest.fixture
def cenario(monkeypatch, tmp_path):
    return Cenario(monkeypatch, tmp_path)


# 1 -------------------------------------------------------------------------
class TestConfigAlteradoDuranteAVarredura:
    @pytest.mark.asyncio
    async def test_guild_nova_no_meio_nao_aborta_e_o_enviado_fica_gravado(self, cenario):
        a = cenario.guild("111", 1)
        cenario.fonte(FEED, [entrada("https://n/1", 0), entrada("https://n/2", 0)])

        def configura_guild_nova(_canal):
            # O que /dashboard faz no dict em cache enquanto a varredura roda.
            cenario.config.setdefault("222", {"channel_id": 2, "filters": ["todos"]})

        a.ao_enviar = configura_guild_nova
        await cenario.varrer()

        assert a.enviados == ["https://n/1", "https://n/2"]
        dedup = cenario.state()["dedup"][FEED]
        assert dedup["https://n/1"] == ["111"]
        assert set(cenario.history()) == {"https://n/1", "https://n/2"}


# 2 -------------------------------------------------------------------------
class TestFalhaNumaGuildNaoPerdeANoticia:
    @pytest.mark.asyncio
    async def test_guild_que_falhou_recebe_no_ciclo_seguinte_e_a_outra_nao_repete(self, cenario):
        a = cenario.guild("111", 1)
        b = cenario.guild("222", 2)
        cenario.fonte(FEED, [entrada("https://n/1", 0)])

        b.falhar = True
        await cenario.varrer()
        assert a.enviados == ["https://n/1"] and b.enviados == []
        assert "https://n/1" not in cenario.history()
        assert cenario.state()["dedup"][FEED]["https://n/1"] == ["111"]

        b.falhar = False
        await cenario.varrer()
        assert a.enviados == ["https://n/1"], "a guild que já tinha recebido não pode receber de novo"
        assert b.enviados == ["https://n/1"]
        assert "https://n/1" in cenario.history()

    @pytest.mark.asyncio
    async def test_legitimo_todas_recebem_e_o_link_vai_ao_history_no_mesmo_ciclo(self, cenario):
        a = cenario.guild("111", 1)
        b = cenario.guild("222", 2)
        cenario.fonte(FEED, [entrada("https://n/1", 0)])
        await cenario.varrer()
        assert a.enviados == b.enviados == ["https://n/1"]
        assert cenario.history() == ["https://n/1"]
        await cenario.varrer()
        assert a.enviados == b.enviados == ["https://n/1"]

    @pytest.mark.asyncio
    async def test_mesmo_link_em_dois_feeds_sai_uma_vez_mesmo_pendente(self, cenario):
        a = cenario.guild("111", 1)
        b = cenario.guild("222", 2)
        cenario.fonte(FEED, [entrada("https://n/1", 0)])
        cenario.fonte(FEED2, [entrada("https://n/1", 0)])
        b.falhar = True
        await cenario.varrer()
        assert a.enviados == ["https://n/1"]


# 3 -------------------------------------------------------------------------
class TestColdStartSoParaFeedNuncaVisto:
    @pytest.mark.asyncio
    async def test_feed_ja_visto_sem_links_nao_publica_item_velho(self, cenario):
        a = cenario.guild("111", 1)
        cenario.fonte(FEED, [entrada("https://velho/1", dias_atras=90)])
        cenario.gravar_state({"dedup": {FEED: {}}})
        await cenario.varrer()
        assert a.enviados == []
        assert FEED in cenario.state()["dedup"], "a marca de 'feed visto' não pode ser podada"

    @pytest.mark.asyncio
    async def test_feed_nunca_visto_publica_no_primeiro_ciclo(self, cenario):
        a = cenario.guild("111", 1)
        cenario.fonte(FEED, [entrada("https://velho/1", dias_atras=90)])
        await cenario.varrer()
        assert a.enviados == ["https://velho/1"]

    @pytest.mark.asyncio
    async def test_filtro_barra_tudo_e_o_ciclo_seguinte_nao_vira_cold_start(self, cenario, monkeypatch):
        a = cenario.guild("111", 1)
        cenario.fonte(FEED, [entrada("https://velho/1", dias_atras=90)])
        cenario.gravar_state({"dedup": {FEED: {"https://outro/9": []}}})
        await cenario.varrer()
        assert cenario.state()["dedup"][FEED] == {}
        await cenario.varrer()
        assert a.enviados == []


# 4 -------------------------------------------------------------------------
class TestCacheDoFallbackDescartadoNaFalha:
    @pytest.mark.asyncio
    async def test_falha_de_entrega_descarta_a_url_canonica(self, cenario):
        a = cenario.guild("111", 1)
        cenario.fonte(FEED, [entrada("https://n/1", 0)])
        cenario.etag_por_chave = {FEED: "W/1"}
        a.falhar = True
        await cenario.varrer()
        assert FEED not in cenario.state()["http_cache"]

    @pytest.mark.asyncio
    async def test_legitimo_entrega_ok_mantem_o_etag_da_canonica(self, cenario):
        cenario.guild("111", 1)
        cenario.fonte(FEED, [entrada("https://n/1", 0)])
        cenario.etag_por_chave = {FEED: "W/1"}
        await cenario.varrer()
        assert cenario.state()["http_cache"][FEED] == {"etag": "W/1"}

    @pytest.mark.asyncio
    async def test_falha_de_entrega_descarta_canonica_e_fallback(self, cenario):
        a = cenario.guild("111", 1)
        cenario.fonte(FEED, [entrada("https://n/1", 0)], fallbacks=[FALLBACK])
        cenario.etag_por_chave = {FALLBACK: "W/espelho"}
        a.falhar = True
        await cenario.varrer()
        cache = cenario.state()["http_cache"]
        assert FALLBACK not in cache and FEED not in cache

    @pytest.mark.asyncio
    async def test_legitimo_entrega_ok_mantem_o_etag_do_fallback(self, cenario):
        cenario.guild("111", 1)
        cenario.fonte(FEED, [entrada("https://n/1", 0)], fallbacks=[FALLBACK])
        cenario.etag_por_chave = {FALLBACK: "W/espelho"}
        await cenario.varrer()
        assert cenario.state()["http_cache"][FALLBACK] == {"etag": "W/espelho"}


# 5 -------------------------------------------------------------------------
SITE = "https://oficial.exemplo/"


class TestMonitorHtmlNaoPerdeAMudanca:
    def _preparar(self, cenario):
        cenario.gravar_state({"html_monitor": {SITE: "hash-antigo"}})
        cenario.html_updates = [{"title": "🔄 Update: Oficial", "link": SITE, "summary": "mudou"}]
        cenario.html_novo_estado = {SITE: "hash-novo"}

    @pytest.mark.asyncio
    async def test_falha_em_todas_as_guilds_restaura_o_hash_anterior(self, cenario):
        a = cenario.guild("111", 1)
        self._preparar(cenario)
        a.falhar = True
        await cenario.varrer()
        st = cenario.state()
        assert st["html_monitor"][SITE] == "hash-antigo"
        assert SITE not in st.get("html_monitor_posted", {})

    @pytest.mark.asyncio
    async def test_legitimo_entregue_grava_hash_novo_e_arma_cooldown(self, cenario):
        a = cenario.guild("111", 1)
        self._preparar(cenario)
        await cenario.varrer()
        st = cenario.state()
        assert a.enviados == [SITE]
        assert st["html_monitor"][SITE] == "hash-novo"
        assert SITE in st["html_monitor_posted"]

    @pytest.mark.asyncio
    async def test_filtro_barrando_todas_nao_restaura_para_nao_repetir_para_sempre(self, cenario, monkeypatch):
        cenario.guild("111", 1)
        self._preparar(cenario)
        monkeypatch.setattr(engine, "match_intel", lambda *a, **k: False)
        await cenario.varrer()
        assert cenario.state()["html_monitor"][SITE] == "hash-novo"


# 6 -------------------------------------------------------------------------
class ProcessoMorto(BaseException):
    """Simula o container sendo derrubado: não é pego por `except Exception`."""


class TestInterrupcaoNoMeioNaoRepete:
    @pytest.mark.asyncio
    async def test_o_entregue_antes_da_queda_nao_sai_de_novo(self, cenario):
        a = cenario.guild("111", 1)
        cenario.fonte(FEED, [entrada("https://n/1", 0)])
        cenario.fonte(FEED2, [entrada("https://m/1", 0)])
        cenario.etag_por_chave = {FEED2: "W/novo"}
        cenario.gravar_state({"http_cache": {FEED2: {"etag": "W/antigo"}}})

        def morrer_no_segundo_feed(canal):
            if canal.enviados:
                raise ProcessoMorto()

        a.ao_enviar = morrer_no_segundo_feed
        with pytest.raises(ProcessoMorto):
            await cenario.varrer()

        st = cenario.state()
        assert st["dedup"][FEED]["https://n/1"] == ["111"]
        assert "https://n/1" in cenario.history()
        # O cache persistido continua o do ciclo anterior: o feed interrompido
        # será rebaixado de novo, e não receberá 304 sobre notícia não entregue.
        assert st["http_cache"] == {FEED2: {"etag": "W/antigo"}}

        a.ao_enviar = None
        await cenario.varrer()
        assert a.enviados == ["https://n/1", "https://m/1"]
