"""
Web Server module using aiohttp.
Integrates directly with the bot loop.
"""
import logging
from aiohttp import web
import aiohttp_jinja2
import jinja2
import os
from datetime import datetime
from functools import wraps

from core.stats import stats
from utils.storage import p
from settings import LOG_LEVEL

log = logging.getLogger("MaftyWeb")

# Configuração de segurança
WEB_AUTH_TOKEN = os.getenv("WEB_AUTH_TOKEN", None)
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")  # Por padrão, apenas localhost
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))

routes = web.RouteTableDef()

# Rate limiting simples (por IP)
_rate_limit_store = {}
RATE_LIMIT_WINDOW = 60  # segundos
RATE_LIMIT_MAX_REQUESTS = 30  # máximo de requisições por janela


def rate_limit_middleware(handler):
    """Middleware de rate limiting simples."""
    @wraps(handler)
    async def wrapper(request):
        client_ip = request.remote
        current_time = datetime.now().timestamp()
        
        # Limpa entradas antigas
        if client_ip in _rate_limit_store:
            _rate_limit_store[client_ip] = [
                ts for ts in _rate_limit_store[client_ip]
                if current_time - ts < RATE_LIMIT_WINDOW
            ]
        else:
            _rate_limit_store[client_ip] = []
        
        # Verifica limite
        if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            log.warning(f"⚠️ Rate limit excedido para IP: {client_ip}")
            return web.json_response(
                {"error": "Rate limit exceeded. Please try again later."},
                status=429
            )
        
        # Adiciona timestamp atual
        _rate_limit_store[client_ip].append(current_time)
        
        return await handler(request)
    return wrapper


def auth_required(handler):
    """Decorator para requerer autenticação via token."""
    @wraps(handler)
    async def wrapper(request):
        # Se não há token configurado, permite acesso (modo desenvolvimento)
        if not WEB_AUTH_TOKEN:
            log.warning("⚠️ Servidor web rodando SEM autenticação! Configure WEB_AUTH_TOKEN no .env")
            return await handler(request)
        
        # Verifica token no header Authorization
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response(
                {"error": "Authentication required"},
                status=401,
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = auth_header.replace("Bearer ", "").strip()
        if token != WEB_AUTH_TOKEN:
            log.warning(f"⚠️ Tentativa de acesso com token inválido de IP: {request.remote}")
            return web.json_response(
                {"error": "Invalid token"},
                status=403
            )
        
        return await handler(request)
    return wrapper


def security_headers_middleware(handler):
    """Adiciona headers de segurança HTTP."""
    @wraps(handler)
    async def wrapper(request):
        response = await handler(request)
        
        # Adiciona headers de segurança
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Content Security Policy básica
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:;"
        )
        
        return response
    return wrapper


@routes.get('/')
@rate_limit_middleware
@security_headers_middleware
async def index(request):
    """Renderiza a página inicial."""
    return aiohttp_jinja2.render_template('index.html', request, {})

@routes.get('/api/stats')
@rate_limit_middleware
@auth_required
@security_headers_middleware
async def api_stats(request):
    """API JSON para atualizar status via AJAX."""
    return web.json_response({
        "uptime": stats.format_uptime(),
        "scans": stats.scans_completed,
        "news_posted": stats.news_posted,
        "cache_hits": stats.cache_hits_total,
        "last_scan": stats.last_scan_time.isoformat() if stats.last_scan_time else "Never"
    })

async def start_web_server(host=None, port=None):
    """Inicia o servidor web aiohttp."""
    # Usa configurações do ambiente ou padrões seguros
    server_host = host or WEB_HOST
    server_port = port or WEB_PORT
    
    app = web.Application()
    
    # Configura templates
    template_dir = p("web/templates")
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(template_dir))
    
    app.add_routes(routes)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, server_host, server_port)
    
    # Log de segurança
    if WEB_AUTH_TOKEN:
        log.info(f"🌍 Web Dashboard iniciado em http://{server_host}:{server_port} (com autenticação)")
    else:
        log.warning(f"⚠️ Web Dashboard iniciado em http://{server_host}:{server_port} SEM autenticação!")
        log.warning("⚠️ Configure WEB_AUTH_TOKEN no .env para produção!")
    
    if server_host == "0.0.0.0":
        log.warning("⚠️ Servidor web escutando em 0.0.0.0 (acessível de qualquer IP)!")
        log.warning("⚠️ Considere usar 127.0.0.1 ou configurar firewall adequadamente!")
    
    await site.start()
