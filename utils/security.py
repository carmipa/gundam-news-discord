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


def is_private_ip(ip: str) -> bool:
    """
    Verifica se um IP é privado/local.
    
    Args:
        ip: Endereço IP (IPv4 ou IPv6)
    
    Returns:
        True se o IP for privado/local
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        for network in PRIVATE_IP_RANGES:
            if ip_obj in network:
                return True
        return False
    except ValueError:
        return False


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
    
    # Remove porta para validação
    netloc_without_port = parsed.netloc.split(":")[0]
    
    # Verifica domínios bloqueados
    if netloc_without_port.lower() in BLOCKED_DOMAINS:
        return False, f"Domínio '{netloc_without_port}' não permitido (domínio local)"
    
    # Verifica se é IP privado
    try:
        if is_private_ip(netloc_without_port):
            return False, f"IP privado/local '{netloc_without_port}' não permitido (anti-SSRF)"
    except ValueError:
        # Não é um IP válido, pode ser um domínio
        pass
    
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


def sanitize_log_message(message: str, sensitive_patterns: Optional[List[str]] = None) -> str:
    """
    Remove informações sensíveis de mensagens de log.
    
    Args:
        message: Mensagem de log original
        sensitive_patterns: Lista opcional de padrões regex para mascarar
    
    Returns:
        Mensagem sanitizada
    """
    if not message:
        return ""
    
    # Padrões padrão de informações sensíveis
    default_patterns = [
        (r'(?i)(token|password|secret|key|api[_-]?key)\s*[:=]\s*([^\s]+)', r'\1: [REDACTED]'),
        (r'(?i)(discord[_-]?token)\s*[:=]\s*([^\s]+)', r'\1: [REDACTED]'),
        (r'([a-zA-Z0-9_-]{20,})', lambda m: m.group(0)[:8] + "..." if len(m.group(0)) > 20 else m.group(0)),  # Tokens longos
    ]
    
    sanitized = message
    
    # Aplica padrões padrão
    for pattern, replacement in default_patterns:
        if callable(replacement):
            sanitized = re.sub(pattern, replacement, sanitized)
        else:
            sanitized = re.sub(pattern, replacement, sanitized)
    
    # Aplica padrões customizados se fornecidos
    if sensitive_patterns:
        for pattern in sensitive_patterns:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
    
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
