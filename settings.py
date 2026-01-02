# settings.py
import os
from dotenv import load_dotenv

# Carrega o .env
load_dotenv()

# Credenciais com tratamento básico de ausência
TOKEN = os.getenv('DISCORD_TOKEN')
raw_id = os.getenv('DISCORD_CHANNEL_ID')

# Converte o ID para int apenas se ele existir, para evitar erro de inicialização
try:
    ID_CANAL = int(raw_id) if raw_id else 0
except ValueError:
    print("ERRO: O DISCORD_CHANNEL_ID no seu .env não é um número válido!")
    ID_CANAL = 0

# Configurações de Operação
COMMAND_PREFIX = "!"
LOOP_MINUTES = 30