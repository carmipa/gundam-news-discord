"""
Guarda da telemetria de ausência (classe de defeito 3.6).

Um painel que só mede SUCESSO é indistinguível de um painel que não mede nada:
`feeds_falhos=0` significa tanto "nenhuma fonte falhou" quanto "o contador nunca
foi alimentado". Num bot irmão, 7 dos 12 defeitos de uma auditoria teriam
aparecido num painel que medisse ausência.

CALIBRAÇÃO (§6): cada regra de veredito tem par — o cenário que alarma E o gêmeo
saudável que TEM de ficar calado. Alarme falso gasta a atenção de quem lê e
ensina a ignorar o aviso verdadeiro.
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.stats import (  # noqa: E402
    VEREDITO_ANOMALIA,
    VEREDITO_ATENCAO,
    VEREDITO_OK,
    avaliar_varredura,
)


def avaliar(**kw):
    base = dict(
        fontes_totais=60,
        feeds_falhos=0,
        feeds_vazios=0,
        enviadas=5,
        cache_hits=10,
        traducoes_rejeitadas=0,
        ciclos_sem_envio=0,
    )
    base.update(kw)
    return avaliar_varredura(**base)


class TestCatalogoVazio:
    """O buraco clássico: o detector reportar catálogo vazio como saudável."""

    def test_catalogo_vazio_e_ANOMALIA(self):
        r = avaliar(fontes_totais=0, enviadas=0)
        assert r["veredito"] == VEREDITO_ANOMALIA
        assert any("catálogo vazio" in m for m in r["motivos"])

    def test_gemeo_saudavel_com_catalogo_cheio_fica_calado(self):
        assert avaliar()["veredito"] == VEREDITO_OK


class TestFontesQueNaoEntregam:
    """Falha e 200-vazio contam juntos: as duas são 'fonte que não entregou'."""

    def test_metade_das_fontes_mudas_e_ANOMALIA(self):
        r = avaliar(feeds_falhos=20, feeds_vazios=10)  # 30/60
        assert r["veredito"] == VEREDITO_ANOMALIA

    def test_um_quarto_mudas_e_ATENCAO(self):
        r = avaliar(feeds_falhos=10, feeds_vazios=5)  # 15/60
        assert r["veredito"] == VEREDITO_ATENCAO

    def test_ruido_normal_fica_calado(self):
        # 2 falhas em 60 é o estado medido em produção (Reddit sem OAuth).
        # Se isto alarmasse, o alarme seria ignorado em uma semana.
        assert avaliar(feeds_falhos=2)["veredito"] == VEREDITO_OK

    def test_feed_vazio_conta_mesmo_sem_falha(self):
        # 200 com zero entradas é o disfarce mais comum de fonte morta.
        r = avaliar(feeds_falhos=0, feeds_vazios=20)
        assert r["veredito"] == VEREDITO_ATENCAO
        assert any("vazias" in m for m in r["motivos"])


class TestAusenciaDeEntrega:
    """Zero publicadas: rotina uma vez, sintoma quando persiste."""

    def test_um_ciclo_sem_envio_e_OK_e_o_zero_e_DITO(self):
        r = avaliar(enviadas=0, ciclos_sem_envio=1)
        assert r["veredito"] == VEREDITO_OK
        assert any("0 publicadas" in m for m in r["motivos"]), (
            "o zero legítimo tem de ser dito com todas as letras, não ficar em silêncio"
        )

    def test_seis_ciclos_sem_envio_e_ATENCAO(self):
        assert avaliar(enviadas=0, ciclos_sem_envio=6)["veredito"] == VEREDITO_ATENCAO

    def test_um_dia_inteiro_sem_envio_e_ANOMALIA(self):
        r = avaliar(enviadas=0, ciclos_sem_envio=24)
        assert r["veredito"] == VEREDITO_ANOMALIA

    def test_envio_normal_zera_a_contagem_e_fica_calado(self):
        assert avaliar(enviadas=12, ciclos_sem_envio=0)["veredito"] == VEREDITO_OK


class TestTraducaoRejeitada:
    def test_rejeicao_vira_ATENCAO(self):
        r = avaliar(traducoes_rejeitadas=3)
        assert r["veredito"] == VEREDITO_ATENCAO
        assert any("página de erro" in m for m in r["motivos"])

    def test_sem_rejeicao_fica_calado(self):
        assert avaliar(traducoes_rejeitadas=0)["veredito"] == VEREDITO_OK


class TestRobustez:
    """O instrumento também precisa de prova: nunca aprovar por omissão."""

    @pytest.mark.parametrize("campo", [
        "fontes_totais", "feeds_falhos", "feeds_vazios", "enviadas",
        "cache_hits", "traducoes_rejeitadas", "ciclos_sem_envio",
    ])
    def test_contador_invalido_e_ANOMALIA_nunca_OK(self, campo):
        r = avaliar(**{campo: "lixo"})
        assert r["veredito"] == VEREDITO_ANOMALIA
        assert any("inválidos" in m for m in r["motivos"])

    def test_negativo_e_ANOMALIA(self):
        assert avaliar(feeds_falhos=-1)["veredito"] == VEREDITO_ANOMALIA

    def test_todo_veredito_tem_motivo(self):
        # Veredito sem motivo é rótulo, não diagnóstico.
        for kw in ({}, {"feeds_falhos": 40}, {"enviadas": 0, "ciclos_sem_envio": 30},
                   {"fontes_totais": 0}, {"traducoes_rejeitadas": 1}):
            r = avaliar(**kw)
            assert r["motivos"], f"veredito sem motivo para {kw}"

    def test_veredito_carrega_metricas_e_hora(self):
        r = avaliar()
        assert r["metricas"]["fontes_totais"] == 60
        assert r["quando"]

    def test_pior_veredito_vence(self):
        # Uma condição de ATENÇÃO não pode rebaixar uma de ANOMALIA.
        r = avaliar(fontes_totais=60, feeds_falhos=40, traducoes_rejeitadas=1)
        assert r["veredito"] == VEREDITO_ANOMALIA
