"""
Testes de regressão para sanitize_log_message.

Contexto: até 2026-08-01 o sanitizador truncava QUALQUER sequência de 20+
caracteres [a-zA-Z0-9_-] para 8 chars + "...". Isso não protegia segredo nenhum
que já não estivesse coberto pelas regras de rótulo, e destruía o dado de
diagnóstico nos logs de produção — domínios viravam 'unicorn-....jp',
'TLSV1_ALERT_INTERNAL_ERROR' virava 'TLSV1_AL...' e IDs de canal do YouTube
ficavam ilegíveis, impedindo o diagnóstico de fontes mortas.

Estes testes fixam as duas metades do contrato: segredo sai mascarado,
diagnóstico sai intacto.
"""
import importlib.util
import os

# Carrega security.py isoladamente: o pacote utils puxa dependências de rede que
# não são necessárias para exercitar a sanitização (lógica pura de regex).
_SEC_PATH = os.path.join(os.path.dirname(__file__), "..", "utils", "security.py")
_spec = importlib.util.spec_from_file_location("_security_under_test", _SEC_PATH)
_security = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_security)
sanitize_log_message = _security.sanitize_log_message


# Linhas reais colhidas do `docker compose logs` do VPS em 2026-08-01.
DIAGNOSTICO_INTACTO = [
    "Erro de conexao no HTML Monitor para 'https://www.unicorn-gundam-statue.jp/en/':"
    " [Errno -2] Name or service not known",
    "Erro de conexao para 'https://gundamnews.org/':"
    " [SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error (_ssl.c:1017)",
    "[YOUTUBE FEED] 15 entradas -"
    " https://www.youtube.com/feeds/videos.xml?channel_id=UC7wu64jGVKDIBHZoOsSNVAA",
    "HTTP 429 para https://www.reddit.com/r/Gunpla/search.rss"
    "?q=flair%3ANews&restrict_sr=on&sort=new (via proxy: True)",
    "Canal nao encontrado: channel_id 1526234637188464721, Guild 1523042008581804122.",
    "[FALHA TOTAL] Desistindo de https://kimithebuilderblog.wordpress.com/feed/"
    " apos 3 tentativas.",
    "UA: MaftyIntelBot/1.0 (+https://github.com/carmipa/gundam-news-discord)"
    " Python/3.10 aiohttp/3.9.5",
]

def _token_com_forma_de_discord() -> str:
    """Monta um valor com a FORMA de um bot token do Discord. Valor inventado.

    Tem de ser construído em runtime: um literal com esta forma faz o secret
    scanning do GitHub bloquear o push (`GH013: Push cannot contain secrets`),
    mesmo quando o valor nunca existiu. Aconteceu — daí a montagem por partes.

    Formato: <id em base64>.<timestamp>.<hmac>, que é o que o padrão ancorado
    em utils/security.py reconhece pela estrutura, sem precisar de rótulo.
    """
    id_b64 = "A" * 12 + "b" * 12        # 24 chars → casa {23,28}
    timestamp = "Gx" + "1" * 4          # 6 chars  → casa {6}
    hmac = "z" * 20 + "9" * 10          # 30 chars → casa {27,}
    return f"{id_b64}.{timestamp}.{hmac}"


TOKEN_FALSO = _token_com_forma_de_discord()

SEGREDOS = [
    f"Login com DISCORD_TOKEN={TOKEN_FALSO}",
    "headers X-Proxy-Secret: s3cr3t-do-worker-super-longo-aqui",
    f"Authorization: Bot {TOKEN_FALSO}",
    "POST https://discord.com/api/webhooks/1234567890/AbCdEfGhIjKlMnOpQrStUvWxYz012345",
    "GET https://worker.dev/?url=https://x.com&secret=abc123def456ghi789",
    "password = MinhaSenhaDoDashboard123",
    "api_key: sk-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
]


class TestDiagnosticoPreservado:
    """O sanitizador não pode destruir o que serve para diagnosticar produção."""

    def test_linhas_de_log_reais_saem_intactas(self):
        for linha in DIAGNOSTICO_INTACTO:
            assert sanitize_log_message(linha) == linha, linha

    def test_dominio_longo_nao_e_truncado(self):
        msg = "falha em https://www.unicorn-gundam-statue.jp/en/"
        assert "unicorn-gundam-statue.jp" in sanitize_log_message(msg)

    def test_nome_de_erro_ssl_nao_e_truncado(self):
        msg = "[SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error"
        assert "TLSV1_ALERT_INTERNAL_ERROR" in sanitize_log_message(msg)

    def test_id_de_canal_youtube_nao_e_truncado(self):
        msg = "channel_id=UC7wu64jGVKDIBHZoOsSNVAA"
        assert "UC7wu64jGVKDIBHZoOsSNVAA" in sanitize_log_message(msg)


class TestSegredosMascarados:
    """Nenhum segredo pode chegar ao console nem ao bot.log."""

    def test_segredos_conhecidos_sao_redigidos(self):
        for linha in SEGREDOS:
            out = sanitize_log_message(linha)
            assert "REDACTED" in out, linha

    def test_valor_do_token_nao_sobrevive(self):
        out = sanitize_log_message(f"DISCORD_TOKEN={TOKEN_FALSO}")
        assert TOKEN_FALSO not in out

    def test_token_solto_sem_rotulo_e_redigido_pela_forma(self):
        out = sanitize_log_message(f"conectando com {TOKEN_FALSO} agora")
        assert TOKEN_FALSO not in out
        assert "REDACTED" in out

    def test_padroes_customizados_sao_aplicados(self):
        out = sanitize_log_message("valor=ABC123", sensitive_patterns=[r"ABC\d+"])
        assert "ABC123" not in out


class TestRobustez:
    """Logar nunca pode derrubar a aplicação."""

    def test_idempotente(self):
        # O SecurityFilter roda no handler de arquivo E no de console sobre o
        # mesmo LogRecord: sanitizar duas vezes tem de dar o mesmo resultado.
        for linha in DIAGNOSTICO_INTACTO + SEGREDOS:
            uma = sanitize_log_message(linha)
            assert sanitize_log_message(uma) == uma, linha

    def test_entrada_vazia(self):
        assert sanitize_log_message("") == ""
        assert sanitize_log_message(None) == ""

    def test_regex_customizado_invalido_nao_quebra(self):
        out = sanitize_log_message("mensagem normal", sensitive_patterns=["[invalido"])
        assert out == "mensagem normal"
