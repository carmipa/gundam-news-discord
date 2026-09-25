"""
`validate_url` barra endereço interno em qualquer grafia (anti-SSRF).

Achado da auditoria de 2026-09-25, medido: todas estas URLs eram aceitas como
válidas — o host era extraído com `netloc.split(":")[0]` e só IPs na grafia
canônica eram reconhecidos. O vetor é o link de uma entrada de feed (fonte
comprometida), usado no fetch de OpenGraph e imagem.

A1 — para cada sinal que antes enganava a checagem (credenciais na URL, IPv6
entre colchetes, IPv4 numérico abreviado ou decimal, faixa CGNAT) há um caso
legítimo com o MESMO sinal apontando para endereço público, que tem de passar.

Limite declarado, não coberto aqui: nome de domínio público que RESOLVE para IP
interno (`localtest.me`, DNS rebinding). Fechar exige checar o IP resolvido no
momento da conexão, não o texto da URL.
"""
import pytest

from utils.security import validate_url, is_private_ip

DOENTES = [
    "http://x@127.0.0.1:8080/api/stats",
    "http://[::1]:8080/",
    "http://127.1/",
    "http://2130706433/",
    "http://0x7f.0.0.1/",
    "http://0177.0.0.1/",
    "http://0/",
    "http://[::ffff:127.0.0.1]/",
    "http://100.64.0.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://[fd00:ec2::254]/",
    "http://metadata.google.internal/",
    "http://printer.local/",
    "http://LOCALHOST./",
]

LEGITIMOS_COM_O_MESMO_SINAL = [
    "http://user@example.com/",
    "http://[2606:4700:4700::1111]/",
    "http://8.8.8.8/",
    "http://134744072/",
    "http://100.63.255.255/",
    "https://www.gundam.info:443/news/",
    "https://www.youtube.com/feeds/videos.xml?channel_id=UC7wu64jFsV02bpu4Nm-6Chw",
]


@pytest.mark.parametrize("url", DOENTES)
def test_endereco_interno_e_recusado(url):
    ok, motivo = validate_url(url)
    assert ok is False, f"{url} passou"
    assert motivo


@pytest.mark.parametrize("url", LEGITIMOS_COM_O_MESMO_SINAL)
def test_endereco_publico_com_o_mesmo_sinal_passa(url):
    assert validate_url(url) == (True, None)


def test_grafia_legada_e_interpretada_como_o_ip_que_representa():
    assert is_private_ip("127.1") is True
    assert is_private_ip("2130706433") is True
    assert is_private_ip("134744072") is False  # 8.8.8.8


def test_nome_de_dominio_nao_e_confundido_com_ip():
    assert is_private_ip("123.example") is False
    assert validate_url("http://123.example/")[0] is True
