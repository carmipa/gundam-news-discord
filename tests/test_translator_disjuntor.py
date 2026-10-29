"""
Guarda do disjuntor do tradutor.

Medido em produção de 21/10 a 29/10/2026: 2310 traduções recusadas para 2385
envios, quase todas HTTP 429, e o bot insistia — dois pedidos por notícia e por
idioma, todos recusados, e a falha não entra no cache, então cada nova aparição
pedia de novo. O painel ainda dizia "o serviço devolveu página de erro", que não
era a causa.

CALIBRAÇÃO: cada regra tem o caso que tem de abrir o disjuntor e o gêmeo que tem
de deixá-lo fechado — inclusive o limite exato de falhas seguidas.
"""
import asyncio
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import utils.translator as tr  # noqa: E402
from core.stats import VEREDITO_ATENCAO, VEREDITO_OK, avaliar_varredura, stats  # noqa: E402
from deep_translator.exceptions import TooManyRequests  # noqa: E402


class Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


class Servico:
    """Tradutor falso que conta as chamadas e responde o que o teste mandar."""

    def __init__(self):
        self.chamadas = 0
        self.resposta = "Notícias Gundam"

    def fabrica(self, *a, **k):
        servico = self

        class _T:
            def translate(self, _texto):
                servico.chamadas += 1
                r = servico.resposta
                if isinstance(r, Exception):
                    raise r
                return r

        return _T()


@pytest.fixture
def ambiente(monkeypatch):
    tr._translation_cache.clear()
    for campo in ("traducoes_rejeitadas", "traducoes_falhas_servico", "traducoes_suspensas"):
        setattr(stats, campo, 0)
    relogio = Relogio()
    servico = Servico()
    monkeypatch.setattr(tr.time, "monotonic", relogio)
    monkeypatch.setattr(tr, "GoogleTranslator", servico.fabrica)
    monkeypatch.setattr(tr, "_TRANSLATE_JITTER_MIN", 0.0)
    monkeypatch.setattr(tr, "_TRANSLATE_JITTER_MAX", 0.0)
    yield relogio, servico
    tr._translation_cache.clear()


def traduzir(texto):
    return asyncio.run(tr.translate_to_target(texto, "pt_BR"))


class TestLimiteDoServico:
    def test_429_abre_na_hora_e_a_seguinte_nao_chama_o_servico(self, ambiente):
        _, servico = ambiente
        servico.resposta = TooManyRequests()
        assert traduzir("Gundam news A") == "Gundam news A"
        assert servico.chamadas == 1
        assert traduzir("Gundam news B") == "Gundam news B"
        assert servico.chamadas == 1, "com o disjuntor aberto o serviço não pode ser chamado"
        assert stats.traducoes_falhas_servico == 1
        assert stats.traducoes_suspensas == 1

    def test_gemeo_sucesso_nao_abre(self, ambiente):
        _, servico = ambiente
        assert traduzir("Gundam news A") == "Notícias Gundam"
        servico.resposta = "Outra"
        assert traduzir("Gundam news B") == "Outra"
        assert servico.chamadas == 2
        assert stats.traducoes_suspensas == 0

    def test_mesma_noticia_pedida_de_novo_nao_martela(self, ambiente):
        # A falha não entra no cache: sem disjuntor, cada nova aparição pedia de novo.
        _, servico = ambiente
        servico.resposta = TooManyRequests()
        for _ in range(5):
            assert traduzir("人気ガンプラ一挙本日再販") == "人気ガンプラ一挙本日再販"
        assert servico.chamadas == 1


class TestOutrasFalhas:
    def test_duas_falhas_seguidas_ainda_nao_abrem(self, ambiente):
        _, servico = ambiente
        servico.resposta = RuntimeError("timeout")
        traduzir("A")
        traduzir("B")
        servico.resposta = "Traduzido"
        assert traduzir("C") == "Traduzido"
        assert servico.chamadas == 3

    def test_terceira_falha_seguida_abre(self, ambiente):
        _, servico = ambiente
        servico.resposta = RuntimeError("timeout")
        for texto in ("A", "B", "C"):
            traduzir(texto)
        servico.resposta = "Traduzido"
        assert traduzir("D") == "D"
        assert servico.chamadas == 3

    def test_sucesso_no_meio_zera_a_contagem(self, ambiente):
        _, servico = ambiente
        servico.resposta = RuntimeError("timeout")
        traduzir("A")
        traduzir("B")
        servico.resposta = "ok"
        traduzir("C")
        servico.resposta = RuntimeError("timeout")
        traduzir("D")
        traduzir("E")
        servico.resposta = "ok2"
        assert traduzir("F") == "ok2", "duas falhas depois de um sucesso não podem abrir"

    def test_pagina_de_erro_conta_como_falha(self, ambiente):
        _, servico = ambiente
        servico.resposta = "Error 429 (Too Many Requests)!!1 That's an error."
        for texto in ("A", "B", "C"):
            assert traduzir(texto) == texto
        servico.resposta = "ok"
        assert traduzir("D") == "D"
        assert stats.traducoes_rejeitadas == 3
        assert stats.traducoes_suspensas == 1


class TestEntradaRecusadaLocalmente:
    """Recusa do próprio deep_translator, antes do pedido, não é falha do serviço."""

    def test_texto_grande_demais_nao_abre_o_disjuntor(self, ambiente, caplog):
        from deep_translator.exceptions import NotValidLength
        _, servico = ambiente
        gigante = "G" * 5057
        servico.resposta = NotValidLength(gigante, 0, 5000)
        for _ in range(5):
            assert traduzir(gigante) == gigante
        assert tr._disjuntor_aberto() is False
        assert stats.traducoes_falhas_servico == 0
        assert all(len(r.getMessage()) < 300 for r in caplog.records), "o texto inteiro não vai para o log"
        servico.resposta = "Traduzido"
        assert traduzir("Gundam news") == "Traduzido"

    def test_gemeo_falha_do_servico_continua_contando(self, ambiente):
        _, servico = ambiente
        servico.resposta = RuntimeError("x" * 5000)
        for texto in ("A", "B", "C"):
            traduzir(texto)
        assert tr._disjuntor_aberto() is True
        assert stats.traducoes_falhas_servico == 3


class TestEscalada:
    def test_reabre_com_o_dobro_e_respeita_o_teto(self, ambiente):
        relogio, servico = ambiente
        servico.resposta = TooManyRequests()
        pausas = []
        for i in range(8):
            traduzir(f"texto {i}")
            pausas.append(tr._disjuntor_ate - relogio.agora)
            relogio.agora = tr._disjuntor_ate + 1
        base, teto = tr._DISJUNTOR_BASE_S, tr._DISJUNTOR_MAX_S
        assert pausas[:4] == [base, 2 * base, 4 * base, 8 * base]
        assert max(pausas) == teto
        assert all(p <= teto for p in pausas)

    def test_volta_a_tentar_sozinho_quando_a_pausa_acaba(self, ambiente, caplog):
        relogio, servico = ambiente
        servico.resposta = TooManyRequests()
        traduzir("A")
        relogio.agora = tr._disjuntor_ate + 1
        servico.resposta = "Traduzido"
        with caplog.at_level("INFO", logger="MaftyIntel"):
            assert traduzir("B") == "Traduzido"
        assert servico.chamadas == 2
        assert any("voltou a funcionar" in r.getMessage() for r in caplog.records)

    def test_gemeo_sucesso_sem_pausa_antes_nao_anuncia_volta(self, ambiente, caplog):
        with caplog.at_level("INFO", logger="MaftyIntel"):
            traduzir("A")
        assert not any("voltou a funcionar" in r.getMessage() for r in caplog.records)

    def test_log_da_recusa_mantem_o_nome_TooManyRequests(self, ambiente, caplog):
        # Quem conta "TooManyRequests" no log para comparar com antes não pode achar
        # zero só porque a frase mudou.
        _, servico = ambiente
        servico.resposta = TooManyRequests()
        traduzir("A")
        assert any("TooManyRequests" in r.getMessage() for r in caplog.records)

    def test_sucesso_depois_da_pausa_recomeca_a_escalada(self, ambiente):
        relogio, servico = ambiente
        servico.resposta = TooManyRequests()
        traduzir("A")
        relogio.agora = tr._disjuntor_ate + 1
        traduzir("B")  # segunda abertura: pausa dobrada
        relogio.agora = tr._disjuntor_ate + 1
        servico.resposta = "ok"
        traduzir("C")
        servico.resposta = TooManyRequests()
        traduzir("D")
        assert tr._disjuntor_ate - relogio.agora == tr._DISJUNTOR_BASE_S

    def test_falha_com_disjuntor_ja_aberto_nao_dobra(self, ambiente):
        relogio, _ = ambiente
        tr._registrar_falha_do_servico(True, "429")
        ate = tr._disjuntor_ate
        tr._registrar_falha_do_servico(True, "429 de pedido que estava em voo")
        assert tr._disjuntor_ate == ate
        assert tr._aberturas_seguidas == 1


class TestCacheEConcorrencia:
    def test_traducao_em_cache_continua_servida_com_disjuntor_aberto(self, ambiente):
        _, servico = ambiente
        tr._translation_cache["pt_BR:Gundam news"] = "Notícias Gundam"
        tr._registrar_falha_do_servico(True, "429")
        assert traduzir("Gundam news") == "Notícias Gundam"
        assert servico.chamadas == 0
        assert stats.traducoes_suspensas == 0

    def test_quem_esperava_na_fila_nao_chama_depois_que_abriu(self, ambiente, monkeypatch):
        _, servico = ambiente
        servico.resposta = TooManyRequests()
        monkeypatch.setattr(tr, "_translate_semaphore", asyncio.Semaphore(1))

        async def rodar():
            return await asyncio.gather(
                tr.translate_to_target("A", "pt_BR"),
                tr.translate_to_target("B", "pt_BR"),
                tr.translate_to_target("C", "pt_BR"),
            )

        assert asyncio.run(rodar()) == ["A", "B", "C"]
        assert servico.chamadas == 1


class TestTelemetriaDaCausa:
    def _avaliar(self, **kw):
        base = dict(fontes_totais=60, feeds_falhos=0, feeds_vazios=0, enviadas=5,
                    cache_hits=10, traducoes_rejeitadas=0, ciclos_sem_envio=0)
        base.update(kw)
        return avaliar_varredura(**base)

    def test_recusa_do_servico_nao_e_chamada_de_pagina_de_erro(self):
        r = self._avaliar(traducoes_falhas_servico=10)
        assert r["veredito"] == VEREDITO_ATENCAO
        assert any("recusadas pelo serviço" in m for m in r["motivos"])
        assert not any("página de erro" in m for m in r["motivos"])

    def test_pausa_tem_motivo_proprio(self):
        r = self._avaliar(traducoes_suspensas=7)
        assert r["veredito"] == VEREDITO_ATENCAO
        assert any("não tentadas" in m for m in r["motivos"])

    def test_pagina_de_erro_continua_com_o_motivo_dela(self):
        r = self._avaliar(traducoes_rejeitadas=2)
        assert any("página de erro" in m for m in r["motivos"])

    def test_gemeo_saudavel_fica_calado(self):
        r = self._avaliar(traducoes_falhas_servico=0, traducoes_suspensas=0)
        assert r["veredito"] == VEREDITO_OK

    @pytest.mark.parametrize("campo", ["traducoes_falhas_servico", "traducoes_suspensas"])
    def test_contador_novo_invalido_e_ANOMALIA(self, campo):
        r = self._avaliar(**{campo: "lixo"})
        assert r["veredito"] == "ANOMALIA"
