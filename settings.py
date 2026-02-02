# settings.py
import os
from dotenv import load_dotenv

load_dotenv()

# Obrigatório
TOKEN = os.getenv("DISCORD_TOKEN")

# Operação (opcional via env)
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
try:
    LOOP_MINUTES = int(os.getenv("LOOP_MINUTES", "30"))
except ValueError:
    LOOP_MINUTES = 60

# Logging Level (INFO, DEBUG, WARNING, ERROR)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
