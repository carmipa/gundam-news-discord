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

# Logs detalhados da varredura (SEMAFORO, JITTER, PROXY, CACHE…) em INFO sem DEBUG global
SCAN_VERBOSE = os.getenv("SCAN_VERBOSE", "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

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

# User-Agent identificável (bot honesto). Fontes que aceitam/exigem UA de biblioteca
# HTTP — a Natalie devolve 405 para UA de navegador — usam este via "user_agent" no
# sources.json. O sufixo Python/aiohttp é o que faz o WAF da Natalie liberar.
_FEED_UA_DEFAULT = (
    "MaftyIntelBot/1.0 (+https://github.com/carmipa/gundam-news-discord) "
    "Python/3.10 aiohttp/3.9.5"
)
FEED_USER_AGENT = os.getenv("FEED_USER_AGENT", _FEED_UA_DEFAULT).strip() or _FEED_UA_DEFAULT

# UA de navegador: padrão para feeds, porque a maioria dos portais de hobby JP
# bloqueia crawlers. Sobreponível por fonte com "user_agent" no sources.json.
_FEED_BROWSER_UA_DEFAULT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
FEED_BROWSER_USER_AGENT = (
    os.getenv("FEED_BROWSER_USER_AGENT", _FEED_BROWSER_UA_DEFAULT).strip()
    or _FEED_BROWSER_UA_DEFAULT
)

# Teto (s) para "http_timeout_sec" declarado dentro de cada fonte em sources.json
try:
    FEED_HTTP_TIMEOUT_MAX_SEC = int(os.getenv("FEED_HTTP_TIMEOUT_MAX_SEC", "120"))
except ValueError:
    FEED_HTTP_TIMEOUT_MAX_SEC = 120
FEED_HTTP_TIMEOUT_MAX_SEC = max(HTTP_TIMEOUT, FEED_HTTP_TIMEOUT_MAX_SEC)

# Teto (s) para "first_request_delay_sec" por fonte (Nyaa/YouTube podem precisar 60s+)
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

# Número máximo de entradas processadas por feed em cada varredura.
# YouTube costuma expor 15 entradas no Atom; manter 15 reduz perda de vídeos.
try:
    MAX_ENTRIES_PER_FEED = int(os.getenv("MAX_ENTRIES_PER_FEED", "10"))
except ValueError:
    MAX_ENTRIES_PER_FEED = 10
MAX_ENTRIES_PER_FEED = max(1, min(MAX_ENTRIES_PER_FEED, 50))

try:
    MAX_YOUTUBE_ENTRIES_PER_FEED = int(os.getenv("MAX_YOUTUBE_ENTRIES_PER_FEED", "15"))
except ValueError:
    MAX_YOUTUBE_ENTRIES_PER_FEED = 0
# 0 = sem limite (processa todas as entradas retornadas pelo feed naquele ciclo).
MAX_YOUTUBE_ENTRIES_PER_FEED = max(0, min(MAX_YOUTUBE_ENTRIES_PER_FEED, 200))

# Teto de links no history.json E no dedup do state.json (auto-poda a cada varredura).
# O dedup é alinhado à janela dos últimos HISTORY_LIMIT links enviados, impedindo que
# state.json cresça indefinidamente. Env: HISTORY_LIMIT.
try:
    HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "2000"))
except ValueError:
    HISTORY_LIMIT = 2000
HISTORY_LIMIT = max(100, min(HISTORY_LIMIT, 100000))

# Intervalo mínimo (s) entre requisições ao Reddit.
#
# Medido no VPS em 2026-08-01: o Reddit devolve `x-ratelimit-remaining: 0.0` com
# `x-ratelimit-reset: 6` a clientes anónimos — orçamento por IP, não bloqueio de bot.
# Com os 8 feeds a saírem quase em paralelo (semáforo 3), 7 voltavam 429 todo ciclo.
#
# O limite NÃO é um intervalo fixo — é um balde partilhado e ruidoso para IPs de
# datacenter. Taxas de sucesso medidas, 8 feeds sequenciais: 8s → 2/5, 20s → 3/8,
# 35s → 5/8. Espaçar mais não resolve; 12s com retentativa guiada pelo
# `x-ratelimit-reset` deu o mesmo 5/8 que 35s e gasta menos tempo de parede.
#
# A cobertura completa não vem de um ciclo, vem do conjunto deles: os feeds que
# falham são refeitos na varredura seguinte e o dedup impede repostagem, com a
# janela de `is_recent` (7 dias) a cobrir a recolha atrasada. Para 100% por ciclo a
# via é a API OAuth do Reddit (60 req/min autenticadas), não mais espera.
# Env: REDDIT_MIN_INTERVAL_SEC.
try:
    REDDIT_MIN_INTERVAL_SEC = float(os.getenv("REDDIT_MIN_INTERVAL_SEC", "12"))
except ValueError:
    REDDIT_MIN_INTERVAL_SEC = 12.0
REDDIT_MIN_INTERVAL_SEC = max(0.0, min(REDDIT_MIN_INTERVAL_SEC, 120.0))

# HTML Monitor: intervalo mínimo (h) entre dois avisos do MESMO site.
# Sem isto, portais que mudam a cada ciclo (gundam-base.net, gundam-gcg.com) geram
# um post "🔄 Update" por hora sem notícia nova — o hash muda, mas o conteúdo
# relevante não. 0 desliga o cooldown (comportamento antigo). Env: HTML_MONITOR_COOLDOWN_HOURS.
try:
    HTML_MONITOR_COOLDOWN_HOURS = float(os.getenv("HTML_MONITOR_COOLDOWN_HOURS", "24"))
except ValueError:
    HTML_MONITOR_COOLDOWN_HOURS = 24.0
HTML_MONITOR_COOLDOWN_HOURS = max(0.0, min(HTML_MONITOR_COOLDOWN_HOURS, 720.0))
HTML_MONITOR_COOLDOWN_SEC = HTML_MONITOR_COOLDOWN_HOURS * 3600.0

# Proxy do Cloudflare Worker para evitar bloqueios de IP (opcional)
# Exemplo: https://meu-worker.meu-subdominio.workers.dev/?url=
CLOUDFLARE_PROXY_URL = os.getenv("CLOUDFLARE_PROXY_URL", "").strip()

# Segredo compartilhado com o Worker (opcional). Se definido aqui E no Worker
# (env PROXY_SECRET), o bot envia o header X-Proxy-Secret e o Worker recusa quem
# não o apresentar — evita que o proxy seja usado por terceiros (open proxy).
CLOUDFLARE_PROXY_SECRET = os.getenv("CLOUDFLARE_PROXY_SECRET", "").strip()
