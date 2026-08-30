"""
Guarda da leitura de data das entradas de feed.

Defeito descoberto em 2026-08-30 pelo CONTROLE POSITIVO da sonda de fontes — não
por leitura de código. A sonda reprovou o Anime News Network, um feed grande e
saudável, com "nenhuma entrada tem data legível". O feed estava bem; o parser é
que estava partido.

A causa: `parse_entry_dt` tentava `dtparser.isoparse` no campo de TEXTO primeiro.
`isoparse` aceita apenas ISO 8601 e levanta em RFC 822 — que é o formato PADRÃO
do RSS. A exceção era capturada e a função devolvia None **sem nunca chegar ao
`published_parsed`**, que o feedparser já tinha normalizado corretamente.

O dano: `is_recent(None)` devolve True, portanto a janela de 7 dias estava
DESLIGADA para todos os feeds RSS clássicos — funcionando apenas nos Atom e do
YouTube, que publicam ISO 8601. Uma notícia antiga que reaparecesse no feed
(republicação, reordenação, troca de servidor) seria publicada como nova.

É a lição do procedimento aplicada: instrumento sem controle positivo prova que
rodou, não que acertou. Aqui o controle positivo pagou-se antes de a sonda ter
sequer corrido o catálogo.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.scanner.processor import is_recent, parse_entry_dt  # noqa: E402


class Entrada:
    """Imita o FeedParserDict no que interessa: acesso por atributo."""

    def __init__(self, **campos):
        self.__dict__.update(campos)


def _struct_time(dt: datetime):
    return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, 0, 0, 0)


class TestFormatosDeData:
    """Os formatos que aparecem de facto nos feeds do catálogo."""

    def test_rfc822_o_padrao_do_rss(self):
        # ESTE é o caso que estava partido. Sem published_parsed, o texto RFC 822
        # tem de ser lido pelo parser tolerante.
        e = Entrada(published="Wed, 30 Aug 2026 12:00:00 -0400")
        dt = parse_entry_dt(e)
        assert dt is not None, "RFC 822 é o formato padrão do RSS e tem de ser lido"
        assert dt.year == 2026 and dt.month == 8 and dt.day == 30

    def test_iso8601_atom_e_youtube(self):
        e = Entrada(published="2026-08-30T12:00:00+00:00")
        dt = parse_entry_dt(e)
        assert dt is not None
        assert dt.year == 2026 and dt.day == 30

    def test_published_parsed_tem_prioridade(self):
        # É o campo que o feedparser já normalizou — o mais confiável da entrada.
        alvo = datetime(2020, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        e = Entrada(
            published="Wed, 30 Aug 2026 12:00:00 -0400",
            published_parsed=_struct_time(alvo),
        )
        dt = parse_entry_dt(e)
        assert dt is not None
        assert dt.year == 2020, "published_parsed tem de vencer o campo de texto"

    def test_updated_serve_quando_nao_ha_published(self):
        e = Entrada(updated="Wed, 30 Aug 2026 12:00:00 -0400")
        assert parse_entry_dt(e) is not None

    def test_updated_parsed_serve_quando_nao_ha_published_parsed(self):
        alvo = datetime(2026, 8, 30, tzinfo=timezone.utc)
        e = Entrada(updated_parsed=_struct_time(alvo))
        assert parse_entry_dt(e) is not None


class TestSempreComFuso:
    """Comparar aware com naive levanta TypeError dentro de is_recent."""

    @pytest.mark.parametrize("campos", [
        {"published": "Wed, 30 Aug 2026 12:00:00 -0400"},
        {"published": "2026-08-30T12:00:00"},          # ISO sem fuso
        {"published_parsed": (2026, 8, 30, 12, 0, 0, 0, 0, 0)},
    ])
    def test_resultado_tem_tzinfo(self, campos):
        dt = parse_entry_dt(Entrada(**campos))
        assert dt is not None and dt.tzinfo is not None

    def test_is_recent_nao_levanta_com_o_resultado(self):
        for campos in (
            {"published": "Wed, 30 Aug 2026 12:00:00 -0400"},
            {"published": "2026-08-30T12:00:00"},
        ):
            is_recent(parse_entry_dt(Entrada(**campos)))


class TestJanelaDeRecencia:
    """O efeito que o defeito anulava: notícia velha não pode passar por nova."""

    def test_noticia_antiga_em_rfc822_e_recusada(self):
        antiga = datetime.now(timezone.utc) - timedelta(days=400)
        e = Entrada(published=antiga.strftime("%a, %d %b %Y %H:%M:%S +0000"))
        dt = parse_entry_dt(e)
        assert dt is not None, "sem data, is_recent devolve True e a velha passa"
        assert is_recent(dt) is False

    def test_noticia_de_hoje_em_rfc822_e_aceite(self):
        agora = datetime.now(timezone.utc)
        e = Entrada(published=agora.strftime("%a, %d %b %Y %H:%M:%S +0000"))
        assert is_recent(parse_entry_dt(e)) is True


class TestRobustez:
    def test_entrada_sem_data_devolve_none(self):
        assert parse_entry_dt(Entrada()) is None

    def test_data_ilegivel_devolve_none_sem_levantar(self):
        assert parse_entry_dt(Entrada(published="ontem à tarde, talvez")) is None

    def test_published_parsed_malformado_cai_no_texto(self):
        e = Entrada(
            published_parsed=("lixo",),
            published="Wed, 30 Aug 2026 12:00:00 -0400",
        )
        assert parse_entry_dt(e) is not None, (
            "struct_time inválido não pode impedir a leitura do campo de texto"
        )

    def test_sem_data_a_noticia_passa(self):
        # Decisão deliberada: melhor publicar do que descartar por campo de data
        # mal formado. Fica registado aqui para não ser "corrigido" por engano.
        assert is_recent(None) is True


class TestCalibracao:
    def test_a_guarda_apanha_o_defeito_antigo(self):
        from dateutil import parser as dtparser

        texto = "Wed, 30 Aug 2026 12:00:00 -0400"

        with pytest.raises(Exception):
            dtparser.isoparse(texto)  # controle positivo: era isto que levantava

        assert dtparser.parse(texto) is not None, (
            "o parser tolerante TEM de ler o que o isoparse recusava"
        )
        assert parse_entry_dt(Entrada(published=texto)) is not None, (
            "a correção TEM de ler o formato que o código antigo perdia"
        )
