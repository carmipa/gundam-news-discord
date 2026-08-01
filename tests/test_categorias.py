"""
Testes das categorias de filtro e da migração de nomes legados.

Contexto: em 2026-08-01 mediu-se na produção que 4 guilds filtravam por nomes que
o CAT_MAP não conhecia ("gunpla", "filmes", "musica"). `CAT_MAP.get(nome, [])`
devolvia lista vazia e o match_intel rejeitava tudo em silêncio — 2 guilds com
canal ativo estavam a receber zero notícias. Estes testes fixam o contrato:
todo nome que uma guild possa ter guardado tem de resolver para keywords reais.
"""
import pytest

from core.filters import (
    CAT_MAP,
    FILTER_OPTIONS,
    LEGACY_FILTER_ALIASES,
    _contains_any,
    match_intel,
    normalize_filters,
)


def cfg(filtros):
    return {"1": {"channel_id": 99, "filters": filtros}}


class TestIntegridadeDoMapa:
    """O dashboard e o motor de match têm de falar do mesmo conjunto."""

    def test_toda_opcao_do_dashboard_tem_keywords(self):
        for chave in FILTER_OPTIONS:
            if chave == "todos":
                continue
            assert CAT_MAP.get(chave), f"'{chave}' aparece no painel mas não tem keywords"

    def test_todo_alias_legado_aponta_para_categoria_real(self):
        for antigo, novo in LEGACY_FILTER_ALIASES.items():
            assert novo in CAT_MAP, f"alias '{antigo}' aponta para '{novo}', que não existe"

    def test_alias_nao_colide_com_categoria_atual(self):
        # Um nome não pode ser simultaneamente alias e categoria de pleno direito.
        assert not (set(LEGACY_FILTER_ALIASES) & set(CAT_MAP))

    def test_nenhuma_categoria_tem_keyword_vazia(self):
        for chave, kws in CAT_MAP.items():
            assert all(k and k.strip() for k in kws), f"keyword vazia em '{chave}'"

    def test_painel_cabe_nos_limites_do_discord(self):
        """FilterDashboard põe os filtros nas linhas 0 e 1; idiomas na 2, controles na 3.

        O Discord aceita no máximo 5 botões por linha e 25 componentes por view.
        Sem esta guarda, acrescentar categorias passa nos testes e só rebenta em
        produção, ao registar a view — altura em que o painel deixa de aparecer.
        """
        filtros = len(FILTER_OPTIONS)
        linha_0 = min(filtros, 5)
        linha_1 = max(0, filtros - 5)
        assert linha_0 <= 5 and linha_1 <= 5, (
            f"{filtros} filtros não cabem em 2 linhas de 5 — o dashboard precisa "
            "de distribuir por mais linhas antes de aceitar novas categorias."
        )
        idiomas, controles = 5, 2
        assert filtros + idiomas + controles <= 25


class TestNomesLegados:
    """As guilds que nunca tocaram no painel desde a renomeação têm de voltar a receber."""

    @pytest.mark.parametrize("antigo, esperado", [
        ("gunpla", "model_kits"),
        ("filmes", "anime_movies"),
    ])
    def test_traducao(self, antigo, esperado):
        assert normalize_filters([antigo]) == [esperado]

    def test_musica_deixou_de_ser_orfa(self):
        # Era o caso mais grave: 4 guilds filtravam por "musica" e recebiam zero.
        assert CAT_MAP.get("musica")
        assert match_intel("1", "Gundam GQuuuuuuX opening theme revealed",
                           "New single by the band", cfg(["musica"])) is True

    def test_guild_legada_de_gunpla_volta_a_receber(self):
        assert match_intel("1", "New MG Gundam Ver.Ka announced", "Model kit",
                           cfg(["gunpla"])) is True

    def test_normalize_remove_duplicado_da_traducao(self):
        assert normalize_filters(["gunpla", "model_kits"]) == ["model_kits"]

    def test_normalize_preserva_ordem_e_desconhecidos(self):
        assert normalize_filters(["games", "gunpla", "inventado"]) == \
            ["games", "model_kits", "inventado"]

    def test_normalize_tolera_lixo(self):
        assert normalize_filters(None) == []
        assert normalize_filters("gunpla") == []
        assert normalize_filters([None, 3, "", "  ", "games"]) == ["games"]


class TestCategoriasNovas:
    """Música, roupas e hardware temáticos — pedido do Paulo em 2026-08-01."""

    def test_musica(self):
        assert match_intel("1", "Gundam Hathaway soundtrack out now",
                           "Full OST released", cfg(["musica"])) is True

    def test_roupas(self):
        assert match_intel("1", "Strict-G launches Gundam hoodie collab",
                           "New apparel line", cfg(["roupas"])) is True

    def test_hardware_raro_mas_existe(self):
        assert match_intel("1", "ASUS ROG Strix Gundam Edition motherboard",
                           "Limited run", cfg(["hardware"])) is True
        assert match_intel("1", "Zotac Gundam Edition graphics card revealed",
                           "GPU collab", cfg(["hardware"])) is True

    def test_hardware_nao_apanha_qualquer_noticia_gundam(self):
        # Categoria estreita: notícia de anime não pode cair em hardware.
        assert match_intel("1", "Gundam SEED Freedom hits theaters",
                           "Movie premiere", cfg(["hardware"])) is False

    def test_merchandise_continua_guarda_chuva(self):
        # Quem assina merchandise não perde roupas nem hardware.
        for titulo in ("Gundam hoodie by Strict-G", "Gundam Edition SSD launched"):
            assert match_intel("1", titulo, "", cfg(["merchandise"])) is True

    def test_categoria_estreita_nao_vira_todos(self):
        assert match_intel("1", "New HG Zaku II model kit", "Gunpla release",
                           cfg(["musica"])) is False


class TestKeywordsJaponesas:
    """CJK não tem espaço entre palavras: \\b nunca casa no meio da frase."""

    def test_keyword_cjk_casa_por_substring(self):
        assert _contains_any("アニメ主題歌決定のお知らせ", ["主題歌"]) is True
        assert _contains_any("ガンプラ新作が発表された", ["ガンプラ"]) is True

    def test_keyword_cjk_ausente_nao_casa(self):
        assert _contains_any("ガンプラ新作", ["主題歌"]) is False

    def test_noticia_japonesa_de_musica_e_classificada(self):
        assert match_intel("1", "『機動戦士ガンダム』主題歌が決定", "サントラ情報",
                           cfg(["musica"])) is True

    def test_pv_de_filme_japones_cai_em_anime_movies(self):
        """Caso real do YouTube que passava no portão e não caía em categoria nenhuma.

        O comunicado usa 劇場/上映/公開, não 映画 nem アニメ — sem essas keywords a
        notícia era aprovada como relevante e depois descartada por não bater com
        nenhuma categoria, ficando invisível para quem filtra por Anime & Filmes.
        """
        titulo = "[ヘッドホン推奨]『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』戦場体感PV"
        resumo = "大ヒット公開中！先週より上映がスタートした。劇場でお楽しみください。"
        assert match_intel("1", titulo, resumo, cfg(["anime_movies"]),
                           source_url="https://www.youtube.com/watch?v=x") is True
        # E pelo nome legado que as guilds antigas ainda têm guardado.
        assert match_intel("1", titulo, resumo, cfg(["filmes"]),
                           source_url="https://www.youtube.com/watch?v=x") is True


class TestFronteiraNumerica:
    """Gundam 00 não pode ser confundido com horários nem números maiores."""

    @pytest.mark.parametrize("texto, esperado", [
        ("it is 12:00 now", False),
        ("03:00 pm", False),
        ("year 300", False),
        ("2000", False),
        ("version 1.00 released", False),
        ("gundam 00 is great", True),
        ("double 00", True),
    ])
    def test_keyword_numerica(self, texto, esperado):
        assert _contains_any(texto, ["00"]) is esperado

    def test_keyword_textual_mantem_fronteira_classica(self):
        # A fronteira estrita vale só para números: apertar as de texto quebraria
        # casos legítimos como "Novidade:Gundam".
        assert _contains_any("drawing a picture", ["wing"]) is False
        assert _contains_any("gundam wing zero", ["wing"]) is True
        assert _contains_any("Novidade:Gundam RX-78", ["gundam"]) is True
