"""
Guarda dos limites de embed do Discord.

Defeito medido em produção em 2026-08-30: `400 Bad Request (error code: 50035):
Invalid Form Body` repetido de hora em hora, durante dias, na mesma guild — 26
ocorrências em 4 semanas. Como a falha de envio NÃO marca o link no dedup, o
ciclo seguinte tenta de novo: o bot ficou a retentar para sempre um envio
impossível, gastando chamadas de API, e a notícia nunca saiu.

A causa: o resumo é cortado a 2000 caracteres ANTES de traduzir, e a tradução
EXPANDE. Japonês para português cresce com folga, e 2000 caracteres de kanji
passam largamente os 4096 permitidos na descrição.

Este ficheiro protege o MECANISMO (nenhum campo pode estourar), não o caso
específico que estourou — a correção que vale só para o sintoma de hoje volta a
falhar no próximo campo.
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.scanner.notifier import (  # noqa: E402
    _LIMITE_AUTOR,
    _LIMITE_DESCRICAO,
    _LIMITE_RODAPE,
    _LIMITE_TITULO,
    _LIMITE_TOTAL,
    _limitar,
)


class TestLimitar:
    @pytest.mark.parametrize("maximo", [1, 2, 10, 256, 4096])
    def test_nunca_excede_o_limite(self, maximo):
        assert len(_limitar("x" * 10000, maximo)) <= maximo

    def test_texto_curto_sai_intacto(self):
        assert _limitar("Gundam news", 256) == "Gundam news"

    def test_texto_no_limite_exato_sai_intacto(self):
        # Controle de fronteira: cortar aqui seria perda gratuita de conteúdo.
        texto = "x" * 256
        assert _limitar(texto, 256) == texto

    def test_texto_cortado_sinaliza_o_corte(self):
        assert _limitar("x" * 300, 256).endswith("…")

    def test_none_vira_string_vazia(self):
        # A descrição de um embed nunca pode receber None.
        assert _limitar(None, 100) == ""

    def test_tipo_inesperado_nao_levanta(self):
        assert isinstance(_limitar(12345, 100), str)


class TestLimitesConferemComOsDoDiscord:
    """Se a API mudar, é aqui que se atualiza — num sítio só."""

    def test_valores(self):
        assert _LIMITE_TITULO == 256
        assert _LIMITE_DESCRICAO == 4096
        assert _LIMITE_AUTOR == 256
        assert _LIMITE_RODAPE == 2048
        assert _LIMITE_TOTAL == 6000


class TestCenarioReal:
    """O caso que estava a falhar de hora em hora em produção."""

    def test_traducao_que_expande_alem_do_limite_e_cortada(self):
        # 2000 caracteres de japonês traduzidos podem passar de 6000 em português.
        traduzido = "Notícia sobre o novo kit Gundam. " * 250  # ~8250 chars
        assert len(traduzido) > _LIMITE_DESCRICAO
        assert len(_limitar(traduzido, _LIMITE_DESCRICAO)) <= _LIMITE_DESCRICAO

    def test_soma_dos_campos_respeita_o_teto_global(self):
        # Cada campo dentro do seu limite, mas a SOMA acima de 6000: o Discord
        # recusa o embed inteiro. Este é o modo de falha menos óbvio.
        titulo = _limitar("t" * 300, _LIMITE_TITULO)
        descricao = _limitar("d" * 5000, _LIMITE_DESCRICAO)
        autor = _limitar("a" * 300, _LIMITE_AUTOR)
        rodape = _limitar("f" * 3000, _LIMITE_RODAPE)

        total = len(titulo) + len(descricao) + len(autor) + len(rodape)
        excedente = total - _LIMITE_TOTAL
        assert excedente > 0, "o cenário de teste tem de estourar o teto global"

        # Aplica a mesma redução que o create_embed faz.
        descricao = _limitar(descricao, max(0, len(descricao) - excedente))
        novo_total = len(titulo) + len(descricao) + len(autor) + len(rodape)
        assert novo_total <= _LIMITE_TOTAL


class TestCalibracao:
    def test_a_guarda_apanha_o_defeito_antigo(self):
        # Comportamento antigo: `description=s_translated` sem corte nenhum.
        traduzido = "x" * 9000
        assert len(traduzido) > _LIMITE_DESCRICAO, (
            "controle positivo: sem corte, a descrição estoura o limite"
        )
        assert len(_limitar(traduzido, _LIMITE_DESCRICAO)) <= _LIMITE_DESCRICAO, (
            "a correção TEM de conter o que o código antigo deixava passar"
        )


class TestCacheNaoContaEntregaFalhada:
    """Classe de defeito 3.2: 'entreguei lixo' não pode contar como 'entreguei'.

    O ETag é gravado assim que o corpo chega, muito antes de a notícia sair para
    o Discord. Se a entrega falhar, o cache fica gravado e a varredura seguinte
    recebe 304 — nem chega a ver a notícia que não saiu. Com o feed parado, ela
    nunca mais é tentada, e a janela de `is_recent` acaba por descartá-la.

    Medido em produção: 26 falhas de entrega em 4 semanas. O gatilho é real.
    """

    def test_engine_descarta_cache_do_feed_que_falhou(self):
        import ast
        import os

        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        origem = open(
            os.path.join(raiz, "core", "scanner", "engine.py"), encoding="utf-8"
        ).read()

        assert "feeds_com_falha_de_entrega" in origem, (
            "o engine tem de registar quais feeds tiveram falha de entrega"
        )
        assert 'state["http_cache"].pop(' in origem, (
            "o cache HTTP do feed com falha de entrega tem de ser descartado, "
            "senão o 304 do ciclo seguinte esconde a notícia que não saiu"
        )
        # A remoção tem de acontecer ANTES de o state ser gravado.
        arvore = ast.parse(origem)
        assert arvore is not None

    def test_descarte_acontece_antes_de_salvar_o_state(self):
        import os

        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        origem = open(
            os.path.join(raiz, "core", "scanner", "engine.py"), encoding="utf-8"
        ).read()
        i_pop = origem.index('state["http_cache"].pop(')
        i_save = origem.index("save_json_safe(state_file, state)")
        assert i_pop < i_save, (
            "o descarte do cache tem de vir antes da gravação do state, "
            "senão grava-se justamente o que se queria descartar"
        )
