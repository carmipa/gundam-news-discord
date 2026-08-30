"""
Guarda da fronteira com o serviço de tradução (classe de defeito 3.1).

O `deep_translator` NÃO levanta quando o Google responde com página de erro:
devolve o corpo da página como se fosse a tradução. Nenhum `try/except` apanha
isso — o adaptador mente DENTRO do contrato, não falha fora dele.

Medido num bot irmão em 2026-08-30: a página de erro chegou ao canal do Discord
como título E resumo. O elo caro é o terceiro: o envio "teve sucesso", o link
entrou no dedup, e a notícia verdadeira nunca mais sairia.

CALIBRAÇÃO (§6 do procedimento de manutenção): cada regra aqui tem controle
positivo (tem de acusar) e negativo (tem de ficar calada). Uma guarda que nunca
foi vista reprovando não prova nada quando aprova — por isso
`test_guarda_reprova_o_defeito_reintroduzido` reintroduz o comportamento antigo
e exige que o teste o apanhe.
"""
import asyncio
import importlib.util
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from utils.translator import (  # noqa: E402
    _parece_pagina_de_erro,
    _translation_cache,
    translate_to_target,
)
from core.stats import stats  # noqa: E402


# Corpo representativo de uma página de erro do Google Translate. Não é o texto
# exato do incidente do bot irmão (que não foi preservado), mas carrega as
# assinaturas documentadas — é isso que a validação reconhece.
PAGINA_DE_ERRO = (
    "Error 429 (Too Many Requests)!!1 That's an error. "
    "We're sorry, but your computer or network may be sending automated queries. "
    "That's all we know."
)

PAGINA_404 = (
    "Error 404 (Not Found)!!1 That's an error. "
    "The requested URL was not found on this server. That's all we know."
)


class TestControlePositivo:
    """A guarda TEM de acusar estes — senão vira decoração."""

    @pytest.mark.parametrize("corpo", [PAGINA_DE_ERRO, PAGINA_404])
    def test_pagina_de_erro_e_rejeitada(self, corpo):
        assert _parece_pagina_de_erro(corpo, "Novo kit Gundam anunciado") is True

    def test_resposta_vazia_e_rejeitada(self):
        assert _parece_pagina_de_erro("", "Gundam news") is True
        assert _parece_pagina_de_erro("   ", "Gundam news") is True

    def test_none_e_rejeitado(self):
        # O bug antigo devolvia None ao chamador, que o punha no embed.
        assert _parece_pagina_de_erro(None, "Gundam news") is True

    def test_tipo_inesperado_e_rejeitado(self):
        assert _parece_pagina_de_erro(["lista"], "Gundam news") is True


class TestControleNegativo:
    """A guarda TEM de ficar calada nestes — alarme falso ensina a ignorar o aviso."""

    def test_traducao_normal_passa(self):
        assert _parece_pagina_de_erro(
            "Novo kit Gundam anunciado", "New Gundam kit announced"
        ) is False

    def test_noticia_que_FALA_de_erro_passa(self):
        # O caso que separa validação de conteúdo de censura por palavra-chave:
        # a notícia é legitimamente sobre um erro 404 do site oficial.
        original = "Gundam site returns Error 404 (Not Found) after update"
        traduzido = "Site da Gundam retorna Error 404 (Not Found) após atualização"
        assert _parece_pagina_de_erro(traduzido, original) is False

    def test_noticia_sobre_erro_com_marcador_no_original_passa(self):
        original = "That's an error: the Gunpla page is down"
        traduzido = "That's an error: a página de Gunpla caiu"
        assert _parece_pagina_de_erro(traduzido, original) is False

    def test_texto_japones_normal_passa(self):
        assert _parece_pagina_de_erro("ガンダムの最新ニュース", "Gundam news") is False


class TestCaminhoCompleto:
    """O comportamento visível: o que sai da função e o que entra no cache."""

    def setup_method(self):
        _translation_cache.clear()
        stats.traducoes_rejeitadas = 0

    def _traduzir(self, retorno_do_adaptador, monkeypatch, texto="Gundam news"):
        import utils.translator as tr

        class FakeTranslator:
            def __init__(self, *a, **k):
                pass

            def translate(self, _texto):
                if isinstance(retorno_do_adaptador, Exception):
                    raise retorno_do_adaptador
                return retorno_do_adaptador

        monkeypatch.setattr(tr, "GoogleTranslator", FakeTranslator)
        monkeypatch.setattr(tr, "_TRANSLATE_JITTER_MIN", 0.0)
        monkeypatch.setattr(tr, "_TRANSLATE_JITTER_MAX", 0.0)
        return asyncio.run(translate_to_target(texto, "pt_BR"))

    def test_pagina_de_erro_publica_o_ORIGINAL(self, monkeypatch):
        saida = self._traduzir(PAGINA_DE_ERRO, monkeypatch)
        assert saida == "Gundam news", "o original tem de ser publicado, não a página de erro"

    def test_pagina_de_erro_NAO_entra_no_cache(self, monkeypatch):
        # É isto que torna o defeito permanente: o cache é persistido em disco e
        # sobrevive ao restart. Uma vez cacheado, o lixo é servido sem rede.
        self._traduzir(PAGINA_DE_ERRO, monkeypatch)
        assert all(PAGINA_DE_ERRO not in v for v in _translation_cache.values())
        assert len(_translation_cache) == 0

    def test_traducao_boa_entra_no_cache(self, monkeypatch):
        # Controle positivo do cache: se nada entrasse, o teste acima passaria
        # por o cache estar sempre vazio, e não por a validação funcionar.
        saida = self._traduzir("Notícias Gundam", monkeypatch)
        assert saida == "Notícias Gundam"
        assert len(_translation_cache) == 1

    def test_none_do_adaptador_devolve_o_original(self, monkeypatch):
        # O bug antigo: `if trad:` era falso, não cacheava — e `return trad`
        # devolvia None ao embed, apesar da assinatura declarar `-> str`.
        saida = self._traduzir(None, monkeypatch)
        assert saida == "Gundam news"
        assert isinstance(saida, str)

    def test_excecao_do_adaptador_devolve_o_original(self, monkeypatch):
        saida = self._traduzir(RuntimeError("timeout"), monkeypatch)
        assert saida == "Gundam news"

    def test_rejeicao_e_contabilizada_para_a_telemetria(self, monkeypatch):
        self._traduzir(PAGINA_DE_ERRO, monkeypatch)
        assert stats.traducoes_rejeitadas == 1

    def test_texto_vazio_nao_chama_o_servico(self, monkeypatch):
        assert asyncio.run(translate_to_target("", "pt_BR")) == ""


class TestCalibracao:
    """A guarda foi vista REPROVANDO o defeito? Senão não prova nada quando aprova."""

    def test_guarda_reprova_o_defeito_reintroduzido(self):
        # Reintroduz o comportamento antigo (`if trad:` — só rejeita vazio) e
        # exige que o critério de hoje o apanhe. Se este teste passar a falhar,
        # a validação foi enfraquecida.
        def validacao_antiga(saida, _original):
            return not bool(saida)

        assert validacao_antiga(PAGINA_DE_ERRO, "Gundam news") is False, (
            "a validação antiga aprovava a página de erro — é este o defeito"
        )
        assert _parece_pagina_de_erro(PAGINA_DE_ERRO, "Gundam news") is True, (
            "a validação atual TEM de reprovar o que a antiga aprovava"
        )
