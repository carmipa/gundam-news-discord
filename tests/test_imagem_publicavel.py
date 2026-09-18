"""
Guarda de URL de imagem antes de set_image/set_thumbnail (vetor de URL do 50035).

Portado do anime-news em 2026-09-18. O notifier ja tratava as causas de TAMANHO
do erro 50035 (_limitar/_LIMITE_*), mas nao validava a URL da imagem: uma
og:image ou media_thumbnail malformada podia fazer o Discord recusar o embed
inteiro e perder a noticia no loop de retentativa.

Cada guarda com caso doente + caso legitimo de MESMO SINAL (regra 25/A1).
"""
from utils.opengraph import imagem_publicavel


class TestImagemPublicavel:
    def test_doente_url_relativa_recusada(self):
        assert imagem_publicavel("/wp-content/capa.jpg") is None

    def test_doente_host_interno_recusado(self):
        # SSRF: metadata de cloud. validate_url (contrato de tupla) tem de barrar.
        assert imagem_publicavel("http://169.254.169.254/latest/meta-data/") is None

    def test_legitimo_com_mesmo_sinal_passa(self):
        # Mesmo sinal do 1o doente (caminho /wp-content/, .jpg); so difere no que
        # importa: ser absoluta e de host publico.
        url = "https://cdn.gundam.example/wp-content/capa.jpg"
        assert imagem_publicavel(url) == url

    def test_doente_esquema_nao_http_recusado(self):
        assert imagem_publicavel("ftp://exemplo.com/x.jpg") is None

    def test_legitimo_youtube_thumb_passa(self):
        url = "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        assert imagem_publicavel(url) == url

    def test_none_e_vazio_nao_levantam(self):
        assert imagem_publicavel(None) is None
        assert imagem_publicavel("") is None
        assert imagem_publicavel("   ") is None
