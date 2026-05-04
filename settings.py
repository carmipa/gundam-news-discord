# settings.py
import os
from dotenv import load_dotenv

load_dotenv()

# Obrigatório
TOKEN = os.getenv("DISCORD_TOKEN")

# Operação (opcional via env)
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
# Intervalo entre varreduras: 12h por padrão (720 min). Via env: LOOP_MINUTES.
# Hardening: nunca permite 0/minúsculo para evitar loop agressivo (auto-DoS).
try:
    LOOP_MINUTES = int(os.getenv("LOOP_MINUTES", "720"))
except ValueError:
    LOOP_MINUTES = 720
LOOP_MINUTES = max(1, min(LOOP_MINUTES, 1440))
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


def _parse_feed_inter_retry_delays() -> list[float]:
    """Pausas (s) entre tentativas 1→2, 2→3, … em falhas transitórias de feed. Env: FEED_FETCH_INTER_RETRY_DELAYS=2,5"""
    raw = os.getenv("FEED_FETCH_INTER_RETRY_DELAYS", "2,5")
    out: list[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError:
            continue
    return out if out else [2.0, 5.0]


FEED_FETCH_INTER_RETRY_DELAYS = _parse_feed_inter_retry_delays()

# User-Agent para pedidos RSS/Atom (identificável; evita mascarar como crawler de terceiros)
FEED_USER_AGENT = os.getenv(
    "FEED_USER_AGENT",
    "MaftyIntelBot/1.0 (+https://github.com/carmipa/gundam-news-discord)",
).strip() or "MaftyIntelBot/1.0 (+https://github.com/carmipa/gundam-news-discord)"

# Teto (s) para http_timeout_sec por feed em sources.json → feed_fetch_overrides
try:
    FEED_HTTP_TIMEOUT_MAX_SEC = int(os.getenv("FEED_HTTP_TIMEOUT_MAX_SEC", "120"))
except ValueError:
    FEED_HTTP_TIMEOUT_MAX_SEC = 120
FEED_HTTP_TIMEOUT_MAX_SEC = max(HTTP_TIMEOUT, FEED_HTTP_TIMEOUT_MAX_SEC)

# Teto (s) para first_request_delay_sec em feed_fetch_overrides (Nyaa/Youtube podem precisar 60s+)
try:
    FEED_FIRST_DELAY_MAX_SEC = float(os.getenv("FEED_FIRST_DELAY_MAX_SEC", "120"))
except ValueError:
    FEED_FIRST_DELAY_MAX_SEC = 120.0
FEED_FIRST_DELAY_MAX_SEC = max(0.0, min(FEED_FIRST_DELAY_MAX_SEC, 300.0))

# Concorrência: limite de buscas simultâneas para evitar bloqueios por IP (anti-bot)
try:
    MAX_CONCURRENT_FEEDS = int(os.getenv("MAX_CONCURRENT_FEEDS", "3"))
except ValueError:
    MAX_CONCURRENT_FEEDS = 3
MAX_CONCURRENT_FEEDS = max(1, min(MAX_CONCURRENT_FEEDS, 10))

# Jitter: intervalo aleatório (s) entre o início de cada busca para evitar picos de tráfego
try:
    FEED_FETCH_JITTER_MIN = float(os.getenv("FEED_FETCH_JITTER_MIN", "0.5"))
except ValueError:
    FEED_FETCH_JITTER_MIN = 0.5
try:
    FEED_FETCH_JITTER_MAX = float(os.getenv("FEED_FETCH_JITTER_MAX", "2.5"))
except ValueError:
    FEED_FETCH_JITTER_MAX = 2.5

# Proxy do Cloudflare Worker para evitar bloqueios de IP (opcional)
# Exemplo: https://meu-worker.meu-subdominio.workers.dev/?url=
CLOUDFLARE_PROXY_URL = os.getenv("CLOUDFLARE_PROXY_URL", "").strip()
