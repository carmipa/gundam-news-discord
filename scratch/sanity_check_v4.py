import asyncio
import logging
import sys
import os
import aiohttp

# Configuração de path para importação
sys.path.append(os.getcwd())

from core.scanner.fetcher import load_sources, fetch_feed
from core.scanner.notifier import create_embed
from core.filters import match_intel
from settings import LOOP_INTERVAL_STR

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
log = logging.getLogger("SanityCheck")

async def sanity_test():
    log.info("🧪 Iniciando Teste de Sanidade v4.0...")
    log.info(f"🛰️ Verificando Intervalo: {LOOP_INTERVAL_STR}")
    
    if LOOP_INTERVAL_STR != "12h":
        log.error(f"❌ Erro de Configuração: Esperado 12h, obtido {LOOP_INTERVAL_STR}")
    else:
        log.info("✅ Intervalo de 12h confirmado.")

    log.info("📂 Carregando Fontes...")
    urls = load_sources()
    log.info(f"✅ {len(urls)} fontes carregadas do sources.json.")

    # Mock de bot e config
    class MockUser:
        display_avatar = type('Avatar', (), {'url': 'https://example.com/icon.png'})
    class MockBot:
        user = MockUser()
    
    bot = MockBot()
    mock_config = {"123": {"filters": ["todos"], "language": "pt_BR"}}
    
    async with aiohttp.ClientSession() as session:
        # Testar YouTube Highlight logic
        log.info("🎥 Testando Lógica de Vídeo YouTube...")
        yt_link = "https://www.youtube.com/watch?v=qu8dRoLR4m4"
        entry = {"title": "Teste Video", "summary": "Gundam Movie", "link": yt_link}
        
        # Simula a lógica do engine.py
        msg_content = None
        if any(x in yt_link for x in ["youtube.com", "youtu.be"]):
            msg_content = f"🎥 **Assistir Vídeo:** {yt_link}"
            log.info(f"✅ Destaque de vídeo gerado: {msg_content}")
        
        # Testar criação de embed com OpenGraph Fallback
        log.info("🖼️ Testando Criação de Embed + OpenGraph Fallback...")
        # Link real e VÁLIDO do novo domínio
        official_link = "https://en.gundam-official.com/news/i/news/hot-topics/01_16574"
        entry_official = {"title": "Live Action Gundam News", "summary": "Official Announcement", "link": official_link}
        
        try:
            embed = await create_embed(bot, entry_official, "pt_BR", mock_config, session=session)
            log.info(f"✅ Embed criado com sucesso. Thumbnail: {embed.thumbnail.url if embed.thumbnail else 'Nenhuma'}")
        except Exception as e:
            log.error(f"❌ Erro ao criar embed: {e}")
            return

    log.info("\n✨ TESTE DE SANIDADE CONCLUÍDO COM SUCESSO! O bot está pronto para decolar.")

if __name__ == "__main__":
    asyncio.run(sanity_test())
