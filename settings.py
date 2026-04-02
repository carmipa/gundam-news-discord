# settings.py
import os
from dotenv import load_dotenv

load_dotenv()

# Obrigatório
TOKEN = os.getenv("DISCORD_TOKEN")

# Operação (opcional via env)
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
# Intervalo entre varreduras: 12h por padrão (720 min). Via env: LOOP_MINUTES (ex.: 30 para 30 min).
try:
    LOOP_MINUTES = int(os.getenv("LOOP_MINUTES", "720"))
except ValueError:
    LOOP_MINUTES = 720
def format_loop_interval(minutes: int) -> str:
    """Ex.: 720 -> '12h', 30 -> '30 min'."""
    if minutes >= 60:
        return f"{minutes // 60}h"
    return f"{minutes} min"

LOOP_INTERVAL_STR = format_loop_interval(LOOP_MINUTES)

# Logging Level (INFO, DEBUG, WARNING, ERROR)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# HTTP client: timeout máximo de conexão e leitura (segundos) - evita bot "congelar" se API externa cair
try:
    HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "10"))
except ValueError:
    HTTP_TIMEOUT = 10

# RSS: tentativas em falhas transitórias (timeout, desconexão, 502/503/504)
try:
    FEED_FETCH_MAX_ATTEMPTS = int(os.getenv("FEED_FETCH_MAX_ATTEMPTS", "3"))
except ValueError:
    FEED_FETCH_MAX_ATTEMPTS = 3
FEED_FETCH_MAX_ATTEMPTS = max(1, min(FEED_FETCH_MAX_ATTEMPTS, 8))
try:
    FEED_FETCH_RETRY_BACKOFF_SEC = float(os.getenv("FEED_FETCH_RETRY_BACKOFF_SEC", "2.0"))
except ValueError:
    FEED_FETCH_RETRY_BACKOFF_SEC = 2.0
