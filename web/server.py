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

from core.stats import stats
from utils.storage import p

log = logging.getLogger("MaftyWeb")

routes = web.RouteTableDef()

@routes.get('/')
async def index(request):
    """Renderiza a página inicial."""
    return aiohttp_jinja2.render_template('index.html', request, {})

@routes.get('/api/stats')
async def api_stats(request):
    """API JSON para atualizar status via AJAX."""
    return web.json_response({
        "uptime": stats.format_uptime(),
        "scans": stats.scans_completed,
        "news_posted": stats.news_posted,
        "cache_hits": stats.cache_hits_total,
        "last_scan": stats.last_scan_time.isoformat() if stats.last_scan_time else "Never"
    })

async def start_web_server(host='0.0.0.0', port=8080):
    """Inicia o servidor web aiohttp."""
    app = web.Application()
    
    # Configura templates
    template_dir = p("web/templates")
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(template_dir))
    
    app.add_routes(routes)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    
    log.info(f"🌍 Web Dashboard iniciado em http://{host}:{port}")
    await site.start()
