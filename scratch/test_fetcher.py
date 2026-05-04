import asyncio
import aiohttp
import logging
import sys
import os

# Adiciona o diretório raiz ao path para importar os módulos do bot
sys.path.append(os.getcwd())

from core.scanner.fetcher import load_sources, fetch_feed
from core.html_monitor import check_official_sites
from settings import MAX_CONCURRENT_FEEDS, CLOUDFLARE_PROXY_URL

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("TestScanner")

async def test_all():
    log.info(f"Configuração: Proxy={CLOUDFLARE_PROXY_URL}, MaxConc={MAX_CONCURRENT_FEEDS}")
    
    # 1. Teste de Feeds RSS
    sources = load_sources()
    log.info(f"Total de fontes RSS carregadas: {len(sources)}")
    
    # Busca o Hayamimi especificamente
    hayamimi = next((s for s in sources if "hayamimi" in s["url"]), None)
    if hayamimi:
        log.info(f"Testando Hayamimi: {hayamimi['url']}")
        async with aiohttp.ClientSession() as session:
            result = await fetch_feed(session, hayamimi, {})
            if result:
                log.info(f"✅ Sucesso Hayamimi: {len(result[1])} entradas encontradas.")
            else:
                log.error("❌ Falha ao buscar Hayamimi.")
    
    # 2. Teste de Monitor HTML (Apenas 2 sites para teste rápido)
    log.info("Testando Monitor de HTML (Official Sites)...")
    html_state = {}
    updates, new_state = await check_official_sites(html_state)
    log.info(f"✅ Monitor HTML finalizado. {len(updates)} atualizações detectadas (primeira rodada).")

if __name__ == "__main__":
    asyncio.run(test_all())
