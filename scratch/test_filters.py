import asyncio
import logging
import aiohttp
import sys
import os

# Adiciona o diretório atual ao path para importar os módulos do projeto
sys.path.append(os.getcwd())

from core.scanner.fetcher import load_sources, fetch_feed
from core.filters import match_intel
from utils.storage import load_json_safe, p

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger("FilterTest")

async def test_filters():
    log.info("🚀 Iniciando Simulação de Varredura com Novos Filtros...")
    
    urls = load_sources()
    log.info(f"Carregadas {len(urls)} fontes.")
    
    # Simula uma config de guilda para teste (filtro 'todos' habilitado)
    mock_config = {
        "123456789": {
            "filters": ["todos"],
            "channel_id": 999
        }
    }
    
    async with aiohttp.ClientSession() as session:
        http_cache = {}
        tasks = [fetch_feed(session, url, http_cache) for url in urls[:20]] # Testamos as primeiras 20 (inclui as de elite)
        results = await asyncio.gather(*tasks)
        
        passed_count = 0
        blocked_count = 0
        
        print("\n" + "="*50)
        print("RESULTADOS DA FILTRAGEM")
        print("="*50)
        
        for result in results:
            if not result: continue
            url, entries = result
            for entry in entries[:5]:
                title = entry.get("title", "No Title")
                summary = entry.get("summary", "")
                
                if match_intel("123456789", title, summary, mock_config, source_url=url):
                    safe_title = title.encode('ascii', 'ignore').decode('ascii')
                    print(f"OK: {safe_title[:80]}...")
                    passed_count += 1
                else:
                    # Só logamos o que foi bloqueado se for algo que costumava passar
                    if any(x in title.lower() for x in ["one piece", "dragoner", "apex", "bandai", "sunrise", "daitarn"]):
                        safe_title = title.encode('ascii', 'ignore').decode('ascii')
                        print(f"BLOCKED: {safe_title[:80]}...")
                        blocked_count += 1
        
        print("="*50)
        print(f"Resumo: {passed_count} aprovadas, {blocked_count} bloqueadas (suspeitas).")

if __name__ == "__main__":
    asyncio.run(test_filters())
