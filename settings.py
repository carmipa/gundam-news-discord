# settings.py
import os
from dotenv import load_dotenv

load_dotenv()

# Obrigatório
TOKEN = os.getenv("DISCORD_TOKEN")

# Operação (opcional via env)
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
try:
    LOOP_MINUTES = int(os.getenv("LOOP_MINUTES", "45"))
except ValueError:
    LOOP_MINUTES = 60

# Logging Level (INFO, DEBUG, WARNING, ERROR)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# HTTP client: timeout máximo de conexão e leitura (segundos) - evita bot "congelar" se API externa cair
try:
    HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "10"))
except ValueError:
    HTTP_TIMEOUT = 10
