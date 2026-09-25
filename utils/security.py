"""
Security utilities - URL validation, SSRF protection, input sanitization.
"""
import re
import ipaddress
from urllib.parse import urlparse
from typing import Optional, List, Tuple
import logging

log = logging.getLogger("MaftyIntel")

# IPs privados e locais que devem ser bloqueados (anti-SSRF)
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("::1/128"),  # IPv6 localhost
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
]

# Domínios locais que devem ser bloqueados
BLOCKED_DOMAINS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
]

# Schemas permitidos
ALLOWED_SCHEMES = ["http", "https"]


_PARTE_IPV4_LEGADA = re.compile(r"^(0x[0-9a-f]+|[0-9]+)$", re.IGNORECASE)


def _ipv4_legado(host: str) -> Optional[ipaddress.IPv4Address]:
    """
    Interpreta as formas de IPv4 que `inet_aton` e os resolvedores aceitam mas
    `ipaddress` não: `127.1`, `2130706433`, `0x7f.0.0.1`, `0177.0.0.1`.

    Cada parte pode ser decimal, octal (zero à esquerda) ou hexadecimal; a
    última preenche os bytes que faltam. Devolve None se não for IPv4 nessa forma.
    """
    partes = host.split(".")
    if not 1 <= len(partes) <= 4 or not all(_PARTE_IPV4_LEGADA.match(x) for x in partes):
        return None
    try:
        numeros = [
            int(x, 16) if x.lower().startswith("0x")
            else int(x, 8) if len(x) > 1 and x.startswith("0")
            else int(x)
            for x in partes
        ]
    except ValueError:
        return None
    *iniciais, ultima = numeros
    if any(n > 255 for n in iniciais) or ultima >= 256 ** (4 - len(iniciais)):
        return None
    valor = 0
    for n in iniciais:
        valor = (valor << 8) | n
    valor = (valor << (8 * (4 - len(iniciais)))) | ultima
    return ipaddress.IPv4Address(valor)


def _ip_do_host(host: str):
    """IP representado por `host` em qualquer grafia aceita pela rede, ou None."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return _ipv4_legado(host)


def is_private_ip(ip: str) -> bool:
    """
    Verifica se um endereço aponta para rede NÃO pública.

    PROPÓSITO DE NEGÓCIO:
        Barreira anti-SSRF: um link vindo de feed de terceiro não pode fazer o
        bot requisitar o próprio host, a rede do Docker ou o metadata de nuvem.

    INVARIANTES DO DOMÍNIO:
        - "Privado" = qualquer endereço que não seja global: loopback, RFC1918,
          link-local (169.254/16, metadata), CGNAT (100.64/10), 0.0.0.0,
          reservado, multicast, ULA IPv6 (fc00::/7).
        - IPv6 que embute IPv4 (`::ffff:127.0.0.1`) é julgado pelo IPv4.
        - Aceita as grafias numéricas legadas (`127.1`, `2130706433`, hex, octal).

    COMPORTAMENTO EM CASO DE FALHA:
        Texto que não é IP em nenhuma grafia devolve False (é nome de domínio,
        julgado em `validate_url`). Nunca levanta.
    """
    ip_obj = _ip_do_host(ip)
    if ip_obj is None:
        return False
    mapeado = getattr(ip_obj, "ipv4_mapped", None)
    if mapeado is not None:
        ip_obj = mapeado
    if any(ip_obj in rede for rede in PRIVATE_IP_RANGES if rede.version == ip_obj.version):
        return True
    return not ip_obj.is_global


def validate_url(url: str, allowed_domains: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    """
    Valida uma URL contra ataques SSRF e outros problemas de segurança.
    
    Args:
        url: URL a validar
        allowed_domains: Lista opcional de domínios permitidos (whitelist)
    
    Returns:
        (is_valid, error_message)
        is_valid: True se a URL é segura
        error_message: Mensagem de erro se inválida, None se válida
    """
    if not url or not isinstance(url, str):
        return False, "URL inválida: deve ser uma string não vazia"
    
    url = url.strip()
    
    # Verifica esquema permitido
    if not url.startswith(("http://", "https://")):
        return False, f"URL deve começar com http:// ou https://"
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Erro ao fazer parse da URL: {e}"
    
    # Valida esquema
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, f"Esquema '{parsed.scheme}' não permitido. Use http:// ou https://"
    
    # Valida netloc (domínio/IP)
    if not parsed.netloc:
        return False, "URL deve conter um domínio ou IP válido"
    
    # Host real, como o cliente HTTP vai usar: sem credenciais (`user@`), sem
    # porta e sem colchetes de IPv6. `netloc.split(":")[0]` devolvia "x@127.0.0.1"
    # para `http://x@127.0.0.1:8080/` e "[" para `http://[::1]/` — os dois
    # passavam pela checagem de IP privado.
    try:
        netloc_without_port = (parsed.hostname or "").rstrip(".").lower()
    except ValueError as e:
        return False, f"Host inválido na URL: {e}"
    if not netloc_without_port:
        return False, "URL deve conter um domínio ou IP válido"

    # Verifica domínios bloqueados
    if (
        netloc_without_port in BLOCKED_DOMAINS
        or netloc_without_port.endswith((".localhost", ".local", ".internal"))
    ):
        return False, f"Domínio '{netloc_without_port}' não permitido (domínio local)"

    # Verifica se é IP não público, em qualquer grafia numérica
    if is_private_ip(netloc_without_port):
        return False, f"IP privado/local '{netloc_without_port}' não permitido (anti-SSRF)"
    
    # Se há whitelist de domínios, valida contra ela
    if allowed_domains:
        domain_match = False
        for allowed in allowed_domains:
            if netloc_without_port.lower() == allowed.lower() or netloc_without_port.lower().endswith("." + allowed.lower()):
                domain_match = True
                break
        
        if not domain_match:
            return False, f"Domínio '{netloc_without_port}' não está na whitelist permitida"
    
    # Validação adicional: verifica caracteres suspeitos
    suspicious_chars = ["\x00", "\r", "\n", "\t"]
    for char in suspicious_chars:
        if char in url:
            return False, f"URL contém caracteres suspeitos"
    
    return True, None


# Padrões ancorados de segredo. Todos exigem um rótulo (`token=`, `Bearer …`) ou a
# forma estrutural do próprio segredo — nunca "qualquer string longa", que destruiria
# URLs, IDs de canal do YouTube e nomes de erro de SSL nos logs de diagnóstico.
_SECRET_PATTERNS: List[Tuple[str, str]] = [
    # chave=valor / chave: valor (token, password, secret, api_key, proxy_secret…)
    (r'(?i)\b((?:discord[_-]?)?(?:token|password|passwd|secret|api[_-]?key|auth)'
     r'|x[_-]proxy[_-]secret)\b\s*[:=]\s*\S+', r'\1=[REDACTED]'),
    # Authorization: Bearer/Bot <valor>
    (r'(?i)\b(bearer|bot|basic)\s+[A-Za-z0-9._~+/=-]{8,}', r'\1 [REDACTED]'),
    # Token de bot do Discord: <id_base64>.<timestamp>.<hmac>
    (r'\b[A-Za-z0-9_-]{23,28}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}\b', '[REDACTED_DISCORD_TOKEN]'),
    # Webhook do Discord (o token vai no fim da URL)
    (r'(?i)(https://(?:\w+\.)?discord(?:app)?\.com/api/webhooks/\d+/)\S+', r'\1[REDACTED]'),
    # Segredo do proxy passado como query string
    (r'(?i)([?&](?:secret|token|key|apikey|access[_-]?token)=)[^&\s]+', r'\1[REDACTED]'),
]


def sanitize_log_message(message: str, sensitive_patterns: Optional[List[str]] = None) -> str:
    """
    Mascara segredos em mensagens de log antes de irem para o console e o bot.log.

    PROPÓSITO DE NEGÓCIO:
        Os logs do bot são lidos via `docker compose logs` e ficam em disco no VPS.
        Uma linha de log que vaze o DISCORD_TOKEN entrega o controle do bot em 21
        servidores; um X-Proxy-Secret vazado transforma o Worker do Cloudflare em
        open proxy de terceiros. Esta função é o último ponto antes da escrita.

    INVARIANTES DO DOMÍNIO:
        - Só mascara o que é comprovadamente segredo: valor de um rótulo conhecido
          (`token=`, `Bearer …`, `?secret=`) ou a forma estrutural de um token do
          Discord/webhook. NUNCA mascara por heurística de comprimento.
        - Dado de diagnóstico é preservado intacto: URLs completas, domínios,
          IDs de canal do YouTube, nomes de erro de SSL, hashes de commit. Truncar
          isso quebra a capacidade de diagnosticar falhas de fonte em produção.
        - É idempotente: aplicar duas vezes (o filtro roda no handler de arquivo e
          no de console sobre o mesmo LogRecord) produz o mesmo resultado.

    COMPORTAMENTO EM CASO DE FALHA:
        Nunca levanta exceção — logar não pode derrubar a aplicação. Entrada vazia
        ou None retorna "". Se um padrão customizado em `sensitive_patterns` for um
        regex inválido, esse padrão é ignorado e os demais continuam sendo aplicados.

    Args:
        message: Mensagem de log original.
        sensitive_patterns: Regexes extras a mascarar por completo (opcional).

    Returns:
        Mensagem com os segredos substituídos por [REDACTED].
    """
    if not message:
        return ""

    sanitized = message
    for pattern, replacement in _SECRET_PATTERNS:
        try:
            sanitized = re.sub(pattern, replacement, sanitized)
        except re.error:
            continue

    if sensitive_patterns:
        for pattern in sensitive_patterns:
            try:
                sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
            except re.error:
                continue

    return sanitized


def validate_guild_id(guild_id: str) -> bool:
    """
    Valida se um guild_id é válido (numérico).
    
    Args:
        guild_id: ID da guild a validar
    
    Returns:
        True se válido
    """
    if not guild_id:
        return False
    
    try:
        int(guild_id)
        return True
    except (ValueError, TypeError):
        return False


def validate_channel_id(channel_id) -> bool:
    """
    Valida se um channel_id é válido (numérico).
    
    Args:
        channel_id: ID do canal a validar
    
    Returns:
        True se válido
    """
    if channel_id is None:
        return False
    
    try:
        int(channel_id)
        return True
    except (ValueError, TypeError):
        return False


def sanitize_filter_name(filter_name: str) -> Optional[str]:
    """
    Sanitiza e valida um nome de filtro.
    
    Args:
        filter_name: Nome do filtro a validar
    
    Returns:
        Nome sanitizado ou None se inválido
    """
    if not filter_name or not isinstance(filter_name, str):
        return None
    
    # Remove espaços e converte para lowercase
    sanitized = filter_name.strip().lower()
    
    # Valida contra caracteres não permitidos
    if not re.match(r'^[a-z0-9_-]+$', sanitized):
        return None
    
    return sanitized
