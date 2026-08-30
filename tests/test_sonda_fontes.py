"""
Guardas da sonda de fontes.

O instrumento também precisa de prova: um detector sem contraprova demonstra que
rodou, não que acertou. Estes testes fixam as decisões de calibração da sonda —
todas tomadas contra o catálogo REAL, não escolhidas a gosto.

Sem rede: exercitam o critério, não o fetch. A prova de que a sonda fala com a
rede é a própria calibração dela, que corre controles ao vivo antes de emitir
qualquer veredito.
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from scripts.probe_sources import (  # noqa: E402
    LIMIAR_DIVERGENCIA,
    Resultado,
    _similaridade,
    _tem_cjk,
    chave_de_comparacao,
)


def feed(nome, titulo, **kw):
    base = dict(
        url="https://exemplo.com/feed", nome_configurado=nome, titulo=titulo,
        tipo="feed", entradas=10, pos_filtro=5, idade_dias=1,
        saudavel=True, motivo="",
    )
    base.update(kw)
    return Resultado(**base)


class TestNaoAlarmaOQueEIgual:
    """Cada caso aqui foi um ALARME FALSO real na primeira versão do critério."""

    @pytest.mark.parametrize("nome, titulo", [
        # Ordem trocada — o critério de substring falhava nisto.
        ("Tokyo Toshokan – Gundam", "gundam - Tokyo Toshokan"),
        # Título descritivo do Reddit.
        ("r/Gunpla – News flair", "Gunpla: search results - flair:News"),
        ("r/Gundam (new)", "newest submissions : Gundam"),
        # Sufixo técnico do Nyaa.
        ("Nyaa – Gundam geral", 'Nyaa - "gundam" - Torrent File RSS'),
        ("Nyaa – Gundam 1080p", 'Nyaa - "gundam 1080p" - Torrent File RSS'),
        # Pontuação e espaço ideográfico.
        ("Gundam Base", "Gundam  Base"),
        ("NEWS (英語版)", "NEWS(英語版)"),
    ])
    def test_variacao_do_mesmo_nome_nao_alarma(self, nome, titulo):
        assert feed(nome, titulo).diverge() is False, (
            "alarme falso gasta a atenção de quem lê e ensina a ignorar o aviso verdadeiro"
        )

    def test_idiomas_diferentes_nao_alarmam(self):
        # Metade deste catálogo é japonesa e o sources.json guarda o nome em
        # inglês. Comparar através de alfabetos não diz nada.
        assert feed("Gundam Base", "ガンダムベース").diverge() is False

    def test_titulo_vazio_nao_alarma(self):
        assert feed("Gundam Base", "").diverge() is False


class TestAlarmaOQueImporta:
    """Controle positivo: se não acusar isto, o critério não protege nada."""

    def test_fonte_trocada_alarma(self):
        # O defeito real: a URL responde 200 com itens recentes, de OUTRO sítio.
        assert feed("Gundam Base", "Anime Corner Daily").diverge() is True

    def test_nome_de_posicao_alarma(self):
        # Foi assim que se descobriu que 12 canais do YouTube tinham nome de
        # posição em vez do nome real.
        assert feed("Canal YT – UCPjm", "SUNRISE Music").diverge() is True

    def test_canal_generico_alarma(self):
        assert feed("Canal YT – UCWOA", "Netflix").diverge() is True


class TestChaveDeComparacao:
    def test_ignora_pontuacao_e_caixa(self):
        assert chave_de_comparacao("Gundam-Base!") == chave_de_comparacao("gundam base")

    def test_ignora_espaco_ideografico(self):
        assert chave_de_comparacao("サンライズ　SUNRISE") == chave_de_comparacao("サンライズ SUNRISE")

    def test_tipo_invalido_devolve_vazio(self):
        assert chave_de_comparacao(None) == ""
        assert chave_de_comparacao(123) == ""


class TestSimilaridade:
    def test_identicos_valem_um(self):
        assert _similaridade("gundambase", "gundambase") == 1.0

    def test_sem_nada_em_comum_vale_zero(self):
        assert _similaridade("gundam", "xyzwq") == 0.0

    def test_ordem_trocada_continua_alta(self):
        s = _similaridade("tokyotoshokangundam", "gundamtokyotoshokan")
        assert s >= LIMIAR_DIVERGENCIA, f"ordem trocada deu {s:.2f}"

    def test_limiar_foi_calibrado_e_nao_arbitrado(self):
        # Calibrado contra os 63 pares reais do catálogo em 2026-08-30. Mexer
        # aqui sem repetir a medição reintroduz o ruído que este valor eliminou.
        assert LIMIAR_DIVERGENCIA == 0.15


class TestCJK:
    @pytest.mark.parametrize("texto, esperado", [
        ("ガンダムベース", True),
        ("機動戦士", True),
        ("ＧＵＮＤＡＭ", True),
        ("Gundam Base", False),
        ("", False),
    ])
    def test_deteccao(self, texto, esperado):
        assert _tem_cjk(texto) is esperado


class TestCriterioDoisModos:
    """Feed e site institucional têm naturezas diferentes — e critérios diferentes."""

    def test_site_nao_e_medido_por_entradas(self):
        # Medir os ~120 official_sites com critério de feed produziria 120 falhas
        # falsas. Foi o engano cometido num bot irmão, com 29 sites.
        site = Resultado(
            url="https://gundam-official.com/", nome_configurado="GUNDAM Official",
            titulo="GUNDAM.INFO", tipo="site", entradas=0, pos_filtro=0,
            idade_dias=None, saudavel=True, motivo="",
        )
        assert site.saudavel is True
        assert "entradas" not in site.linha(), (
            "a linha de um site não pode exibir contagem de entradas: ele não tem"
        )

    def test_feed_exibe_volume_pos_filtro(self):
        # Sem isto, admitir fonte nova é palpite: um feed com 100 itens dos quais
        # nenhum é sobre Gundam custa banda e não rende nada.
        linha = feed("X", "X", entradas=100, pos_filtro=3).linha()
        assert "pos_filtro=3" in linha
