import asyncio
import aiohttp
import sys
import os

sys.path.append(os.getcwd())
from utils.opengraph import fetch_og_image

async def test_og():
    print("Testando Captura Inteligente de Imagens (OpenGraph)...")
    
    # Exemplo: Link do Gundam.info que costuma ser difícil de pegar imagem via RSS simples
    test_url = "https://en.gundam.info/news/video-music/the-gundam-live-action-film-will-be-an-original-story-not-based-on-an-anime/"
    
    async with aiohttp.ClientSession() as session:
        image_url = await fetch_og_image(test_url, session)
        
        if image_url:
            print(f"SUCESSO! Imagem encontrada:\n{image_url}")
        else:
            print("FALHA: Nenhuma imagem encontrada no link.")

if __name__ == "__main__":
    asyncio.run(test_og())
