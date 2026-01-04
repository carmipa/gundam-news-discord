# =========================================================
# Gundam Intel Bot - "Mafty Sovereign" v2.1
# main.py
#
# FIXES incluídos:
# - 10062 Unknown interaction -> sempre responde slash com (defer se necessário) + followup
# - 40060 Interaction already acknowledged -> só dá defer se response ainda não foi "done"
# - SSL seguro com certifi (sem CERT_NONE)
# - Sources.json validado e corrigido
#
# Features:
# - /dashboard abre painel persistente e configura canal
# - Loop automático a cada LOOP_MINUTES
# - Deduplicação por history.json
# - Config por guild em config.json
# - 🆕 Embeds ricos com cor Gundam e thumbnails automáticos
# - 🆕 Tradução automática PT-BR com deep-translator
# - 🆕 Cache HTTP com ETag/Last-Modified (economiza banda)
# - 🆕 Processamento paralelo de feeds (5x mais rápido)
# =========================================================

import os
import json
import re
import ssl
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple

import discord
import aiohttp
import feedparser
from discord.ext import tasks, commands
from deep_translator import GoogleTranslator
from urllib.parse import urlparse

# settings.py deve conter: TOKEN, COMMAND_PREFIX, LOOP_MINUTES
from settings import TOKEN, COMMAND_PREFIX, LOOP_MINUTES


# =========================================================
# 1) LOGS & MÉTRICAS
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
log = logging.getLogger("MaftyIntel")


# Classe para rastrear métricas do bot
class BotStats:
    """Estatísticas do bot em memória."""
    def __init__(self):
        self.start_time = datetime.now()
        self.scans_completed = 0
        self.news_posted = 0
        self.feeds_failed = 0
        self.last_scan_time = None
        self.cache_hits_total = 0
    
    @property
    def uptime(self) -> timedelta:
        """Retorna tempo de atividade do bot."""
        return datetime.now() - self.start_time
    
    def format_uptime(self) -> str:
        """Formata uptime de forma legível."""
        total_seconds = int(self.uptime.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

# Instância global de estatísticas
stats = BotStats()



# =========================================================
# 2) FILTROS / CATEGORIAS
# =========================================================
GUNDAM_CORE = [
    "gundam", "gunpla", "mobile suit", "universal century", "uc ",
    "rx-78", "zaku", "zeon", "char", "amuro", "hathaway", "mafty",
    "seed", "seed freedom", "witch from mercury", "g-witch",
    "p-bandai", "premium bandai", "ver.ka",
    "hg ", "mg ", "rg ", "pg ", "sd ", "fm ", "re/100"
]

BLACKLIST = [
    "one piece", "dragon ball", "naruto", "bleach",
    "pokemon", "digimon", "attack on titan",
    "jujutsu", "demon slayer"
]

CAT_MAP = {
    "gunpla":  ["gunpla", "model kit", "kit", "ver.ka", "p-bandai", "premium bandai", "hg ", "mg ", "rg ", "pg ", "sd ", "fm ", "re/100"],
    "filmes":  ["anime", "episode", "movie", "film", "pv", "trailer", "teaser", "series", "season", "seed freedom", "witch from mercury", "hathaway"],
    "games":   ["game", "steam", "ps5", "xbox", "gbo2", "battle operation", "breaker", "gundam breaker"],
    "musica":  ["music", "ost", "soundtrack", "album", "opening", "ending"],
    "fashion": ["fashion", "clothing", "apparel", "t-shirt", "hoodie", "jacket", "merch"],
}

FILTER_OPTIONS = {
    "todos": ("TUDO", "🌟"),
    "gunpla": ("Gunpla", "🤖"),
    "filmes": ("Filmes", "🎬"),
    "games": ("Games", "🎮"),
    "musica": ("Música", "🎵"),
    "fashion": ("Fashion", "👕"),
}

ALL_CATEGORIES = ["gunpla", "filmes", "games", "musica", "fashion"]


# =========================================================
# 3) PATH ABSOLUTO (evita salvar JSON em lugar errado no systemd)
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def p(filename: str) -> str:
    """Retorna caminho absoluto de um arquivo dentro da pasta do projeto."""
    return os.path.join(BASE_DIR, filename)


# =========================================================
# 4) JSON SAFE
# =========================================================
def load_json_safe(filepath: str, default: Any) -> Any:
    """Carrega JSON sem derrubar o bot se faltar / vazio / corrompido."""
    try:
        if not os.path.exists(filepath):
            log.warning(f"Arquivo '{filepath}' não existe. Usando padrão.")
            return default
        if os.path.getsize(filepath) == 0:
            log.warning(f"Arquivo '{filepath}' está vazio. Usando padrão.")
            return default
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Falha ao carregar '{filepath}': {e}. Usando padrão.")
        return default


def save_json_safe(filepath: str, data: Any) -> None:
    """Salva JSON com indentação; em erro, loga e segue."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Falha ao salvar '{filepath}': {e}")


# =========================================================
# 5) LIMPEZA DE TEXTO (remove HTML e normaliza espaços)
# =========================================================
_HTML_RE = re.compile(r"<.*?>|&([a-z0-9]+|#[0-9]{1,6});", flags=re.IGNORECASE)
_WS_RE = re.compile(r"\s+")

def clean_html(raw_html: str) -> str:
    """Remove tags HTML e entidades; normaliza espaços."""
    if not raw_html:
        return ""
    txt = re.sub(_HTML_RE, " ", raw_html)
    txt = re.sub(_WS_RE, " ", txt).strip()
    return txt


async def translate_to_pt(text: str) -> str:
    """
    Traduz texto para PT-BR de forma assíncrona usando Google Translator.
    Fallback: retorna texto original se tradução falhar.
    """
    if not text or len(text.strip()) == 0:
        return text
    
    # Limita tamanho (API tem limite de 5000 caracteres)
    text_to_translate = text[:4500] if len(text) > 4500 else text
    
    try:
        # Executa tradução em thread pool para não bloquear event loop
        loop = asyncio.get_event_loop()
        translated = await loop.run_in_executor(
            None,
            lambda: GoogleTranslator(source='auto', target='pt').translate(text_to_translate)
        )
        return translated if translated else text
    except Exception as e:
        log.warning(f"Falha na tradução (fallback para original): {e}")
        return text


# =========================================================
# 6) NORMALIZAÇÃO DO sources.json
# =========================================================
def normalize_sources_to_urls(sources_raw: Any) -> List[str]:
    """
    Aceita:
      - dict: {"rss_feeds":[...], "youtube_feeds":[...], "official_sites":[...]}
      - list: ["http...", {"url":"http..."}, {"link":"http..."}]
    Retorna lista única de URLs http(s), mantendo ordem.
    """
    urls: List[str] = []

    def _add(u: Any):
        if isinstance(u, str):
            u = u.strip()
            if u.startswith(("http://", "https://")):
                urls.append(u)

    if isinstance(sources_raw, dict):
        for key in ("rss_feeds", "youtube_feeds", "official_sites", "feeds", "sources", "urls"):
            val = sources_raw.get(key, [])
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        _add(item)
                    elif isinstance(item, dict):
                        _add(item.get("url") or item.get("link"))

    elif isinstance(sources_raw, list):
        for item in sources_raw:
            if isinstance(item, str):
                _add(item)
            elif isinstance(item, dict):
                _add(item.get("url") or item.get("link"))

    # remove duplicados mantendo ordem
    seen = set()
    out: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# =========================================================
# 7) BOT / INTENTS
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True  # necessário se você usar prefixo (!dashboard)

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Lock global para impedir varreduras simultâneas (loop vs dashboard)
scan_lock = asyncio.Lock()


# =========================================================
# 8) FUNÇÕES DE FILTRO
# =========================================================
def _contains_any(hay: str, needles: List[str]) -> bool:
    """True se qualquer termo em needles existir em hay (hay já deve estar lower)."""
    return any(n in hay for n in needles)


def match_intel(guild_id: str, title: str, summary: str, config: Dict[str, Any]) -> bool:
    """
    Decide se notícia deve ir para a guild:
      - exige filtros
      - corta blacklist
      - exige termos Gundam core
      - "todos" libera tudo
      - senão, precisa bater em categoria selecionada
    """
    g = config.get(str(guild_id), {})
    filters = g.get("filters", [])

    if not isinstance(filters, list) or not filters:
        return False

    content = f"{clean_html(title)} {clean_html(summary)}".lower()

    if _contains_any(content, BLACKLIST):
        return False

    if not _contains_any(content, GUNDAM_CORE):
        return False

    if "todos" in filters:
        return True

    for f in filters:
        kws = CAT_MAP.get(f, [])
        if kws and _contains_any(content, kws):
            return True

    return False


# =========================================================
# 9) HISTÓRICO (dedupe global por link)
# =========================================================
def load_history() -> Tuple[List[str], Set[str]]:
    """Carrega history.json e devolve (lista, set) para dedupe rápido."""
    h = load_json_safe(p("history.json"), [])
    if not isinstance(h, list):
        log.warning("history.json inválido. Reiniciando histórico.")
        h = []
    h = [x for x in h if isinstance(x, str)]
    return h, set(h)


def save_history(history_list: List[str], limit: int = 2000) -> None:
    """Mantém histórico limitado para não crescer infinito."""
    save_json_safe(p("history.json"), history_list[-limit:])


# =========================================================
# 10) CACHE HTTP (ETag / Last-Modified)
# =========================================================
def load_http_state() -> Dict[str, Dict[str, str]]:
    """
    Carrega state.json com ETags e Last-Modified por URL.
    Formato: {"https://feed.com": {"etag": "abc123", "last_modified": "..."}}
    """
    return load_json_safe(p("state.json"), {})


def save_http_state(state: Dict[str, Dict[str, str]]) -> None:
    """Salva cache de ETags e Last-Modified."""
    save_json_safe(p("state.json"), state)


def get_cache_headers(url: str, state: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """Retorna headers de cache para uma URL se disponíveis."""
    headers = {}
    url_state = state.get(url, {})
    
    if "etag" in url_state and url_state["etag"]:
        headers["If-None-Match"] = url_state["etag"]
    
    if "last_modified" in url_state and url_state["last_modified"]:
        headers["If-Modified-Since"] = url_state["last_modified"]
    
    return headers


def update_cache_state(url: str, response_headers: Any, state: Dict[str, Dict[str, str]]) -> None:
    """Atualiza state com ETags e Last-Modified da resposta."""
    if url not in state:
        state[url] = {}
    
    # Salva ETag se presente
    if "ETag" in response_headers:
        state[url]["etag"] = response_headers["ETag"]
    elif "etag" in response_headers:
        state[url]["etag"] = response_headers["etag"]
    
    # Salva Last-Modified se presente
    if "Last-Modified" in response_headers:
        state[url]["last_modified"] = response_headers["Last-Modified"]
    elif "last-modified" in response_headers:
        state[url]["last_modified"] = response_headers["last-modified"]


# =========================================================
# 10) DASHBOARD (VIEW persistente)
# =========================================================
class FilterDashboard(discord.ui.View):
    """
    View persistente: timeout=None.
    Botões com custom_id estável -> funcionam após restart via add_view.
    """

    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = str(guild_id)
        self._rebuild()

    def _cfg(self) -> Dict[str, Any]:
        """Carrega config.json e garante estrutura mínima por guild."""
        cfg = load_json_safe(p("config.json"), {})
        if not isinstance(cfg, dict):
            log.error("config.json inválido. Recriando.")
            cfg = {}

        cfg.setdefault(self.guild_id, {"filters": [], "channel_id": None})

        if not isinstance(cfg[self.guild_id].get("filters"), list):
            cfg[self.guild_id]["filters"] = []

        return cfg

    def _save(self, cfg: Dict[str, Any]) -> None:
        save_json_safe(p("config.json"), cfg)

    def _filters(self) -> List[str]:
        cfg = self._cfg()
        return list(cfg[self.guild_id].get("filters", []))

    def _set_filters(self, new_filters: List[str]) -> None:
        cfg = self._cfg()
        cfg[self.guild_id]["filters"] = list(dict.fromkeys(new_filters))
        self._save(cfg)

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        """Somente admin altera filtros."""
        try:
            return bool(interaction.user.guild_permissions.administrator)
        except Exception:
            return False

    def _rebuild(self) -> None:
        """Reconstrói botões conforme filtros ativos."""
        self.clear_items()
        active = set(self._filters())

        for key, (label, emoji) in FILTER_OPTIONS.items():
            is_active = key in active
            style = discord.ButtonStyle.success if is_active else discord.ButtonStyle.secondary

            btn = discord.ui.Button(
                label=label,
                emoji=emoji,
                style=style,
                custom_id=f"mafty:filter:{self.guild_id}:{key}"
            )
            btn.callback = self._toggle_callback
            self.add_item(btn)

        show_btn = discord.ui.Button(
            label="Ver filtros",
            emoji="📌",
            style=discord.ButtonStyle.primary,
            custom_id=f"mafty:show:{self.guild_id}"
        )
        show_btn.callback = self._show_callback
        self.add_item(show_btn)

        reset_btn = discord.ui.Button(
            label="Reset",
            emoji="🔄",
            style=discord.ButtonStyle.danger,
            custom_id=f"mafty:reset:{self.guild_id}"
        )
        reset_btn.callback = self._reset_callback
        self.add_item(reset_btn)

    async def _toggle_callback(self, interaction: discord.Interaction):
        """Alterna um filtro."""
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem alterar filtros.", ephemeral=True)
            return

        cid = str(interaction.data.get("custom_id", ""))
        key = cid.split(":")[-1] if cid else ""

        current = set(self._filters())

        if key == "todos":
            current = set() if "todos" in current else {"todos", *ALL_CATEGORIES}
        else:
            current.discard("todos")
            if key in current:
                current.remove(key)
            else:
                current.add(key)

        self._set_filters(list(current))
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _show_callback(self, interaction: discord.Interaction):
        """Mostra filtros ativos (ephemeral)."""
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem ver os filtros.", ephemeral=True)
            return

        active = self._filters()
        if not active:
            await interaction.response.send_message("📌 Nenhum filtro ativo no momento.", ephemeral=True)
            return

        await interaction.response.send_message(f"📌 Filtros ativos: {', '.join(active)}", ephemeral=True)

    async def _reset_callback(self, interaction: discord.Interaction):
        """Reseta filtros."""
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem resetar os filtros.", ephemeral=True)
            return

        self._set_filters([])
        self._rebuild()
        await interaction.response.edit_message(view=self)


# =========================================================
# 11) VARREDURA ÚNICA (reutilizável)
# =========================================================
def _log_next_run() -> None:
    """Log explícito do próximo horário de varredura."""
    nxt = datetime.now() + timedelta(minutes=LOOP_MINUTES)
    log.info(f"⏳ Aguardando próxima varredura às {nxt:%Y-%m-%d %H:%M:%S} (em {LOOP_MINUTES} min)...")


async def run_scan_once(trigger: str = "manual") -> None:
    """
    Executa UMA varredura completa.
    - trigger: "loop" | "dashboard" | "manual" (apenas para log)
    - lock impede varreduras simultâneas
    """
    if scan_lock.locked():
        log.info(f"⏭️ Varredura ignorada (já existe uma em execução). Trigger: {trigger}")
        return

    async with scan_lock:
        log.info(f"🔎 Iniciando varredura de inteligência... (trigger={trigger})")

        config = load_json_safe(p("config.json"), {})
        if not isinstance(config, dict) or not config:
            log.info("Nenhuma guild configurada em config.json. Nada para processar.")
            _log_next_run()
            return

        sources_raw = load_json_safe(p("sources.json"), {})
        urls = normalize_sources_to_urls(sources_raw)
        if not urls:
            log.warning("Nenhuma URL válida em sources.json.")
            _log_next_run()
            return

        history_list, history_set = load_history()
        
        # Carregar estado de cache HTTP
        http_state = load_http_state()

        # SSL seguro usando certifi (pacote já instalado)
        # Usa certificados confiáveis do sistema + certifi
        import certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        # Fallback: se um feed específico falhar com SSL, será logado e pulado

        base_headers = {"User-Agent": "Mozilla/5.0 MaftyIntel/2.0"}
        timeout = aiohttp.ClientTimeout(total=25)
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)

        sent_count = 0
        cache_hits = 0  # Contador de feeds não modificados
        
        # Semáforo para limitar concorrência (5 feeds simultâneos)
        MAX_CONCURRENT_FEEDS = 5
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)

        async def fetch_and_process_feed(session, url):
            """Busca e processa um feed de forma assíncrona."""
            nonlocal cache_hits
            
            async with semaphore:  # Limita concorrência
                try:
                    # Adiciona headers de cache (ETag/Last-Modified)
                    request_headers = get_cache_headers(url, http_state)
                    
                    async with session.get(url, headers=request_headers) as resp:
                        # Se 304 Not Modified, pula este feed
                        if resp.status == 304:
                            cache_hits += 1
                            log.debug(f"📦 Cache hit: {url} (304 Not Modified)")
                            return None  # Nada a processar
                        
                        # Atualiza cache com novos headers
                        update_cache_state(url, resp.headers, http_state)
                        
                        text = await resp.text(errors="ignore")
                    
                    # Parse do feed
                    feed = feedparser.parse(text)
                    entries = getattr(feed, "entries", []) or []
                    return (url, entries)
                    
                except Exception as e:
                    log.error(f"Falha ao baixar feed '{url}': {e}")
                    return None

        async with aiohttp.ClientSession(connector=connector, headers=base_headers, timeout=timeout) as session:
            # Busca todos os feeds em paralelo
            tasks = [fetch_and_process_feed(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
            
            # Processa resultados
            for result in results:
                if result is None:
                    continue
                    
                url, entries = result
                
                for entry in entries:
                    link = entry.get("link") or ""
                    if not link or link in history_set:
                        continue

                    title = entry.get("title") or ""
                    summary = entry.get("summary") or entry.get("description") or ""

                    posted_anywhere = False

                    # Para cada guild configurada
                    for gid, gdata in config.items():
                        if not isinstance(gdata, dict):
                            continue

                        channel_id = gdata.get("channel_id")
                        if not isinstance(channel_id, int):
                            continue

                        if not match_intel(str(gid), title, summary, config):
                            continue

                        channel = bot.get_channel(channel_id)
                        if channel is None:
                            log.warning(f"Canal {channel_id} não encontrado na guild {gid}.")
                            continue

                        t_clean = clean_html(title).strip()
                        s_clean = clean_html(summary).strip()[:2000]  # Limite do Discord para description

                        # Traduzir para PT-BR
                        t_translated = await translate_to_pt(t_clean)
                        s_translated = await translate_to_pt(s_clean)

                        try:
                            # Criar embed rico em vez de mensagem simples
                            embed = discord.Embed(
                                title=t_translated[:256],  # Limite do Discord para title
                                description=s_translated,
                                url=link,
                                color=discord.Color.from_rgb(255, 0, 32),  # Vermelho Gundam (#FF0020)
                                timestamp=datetime.now()
                            )
                            
                            # Header com ícone do bot
                            embed.set_author(
                                name="🛰️ INTEL MAFTY",
                                icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
                            )
                            
                            # Footer com fonte
                            source_domain = urlparse(link).netloc
                            embed.set_footer(text=f"Fonte: {source_domain}")
                            
                            # Thumbnail se disponível no feed
                            if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
                                try:
                                    thumb_url = entry.media_thumbnail[0].get("url")
                                    if thumb_url:
                                        embed.set_thumbnail(url=thumb_url)
                                except (AttributeError, IndexError, KeyError):
                                    pass
                            
                            # Enviar embed
                            await channel.send(embed=embed)
                            posted_anywhere = True
                            sent_count += 1
                            await asyncio.sleep(1)  # anti rate-limit

                        except Exception as e:
                            log.error(f"Falha ao enviar no canal {channel_id}: {e}")

                    # Só marca no histórico se foi postado em algum lugar
                    if posted_anywhere:
                        history_set.add(link)
                        history_list.append(link)

        save_history(history_list, limit=2000)
        save_http_state(http_state)  # Salva cache de ETag/Last-Modified
        
        # Atualiza métricas
        stats.scans_completed += 1
        stats.news_posted += sent_count
        stats.cache_hits_total += cache_hits
        stats.last_scan_time = datetime.now()
        
        log.info(f"✅ Varredura concluída. (enviadas={sent_count}, cache_hits={cache_hits}/{len(urls)}, trigger={trigger})")
        _log_next_run()


# =========================================================
# 12) LOOP AUTOMÁTICO
# =========================================================
@tasks.loop(minutes=LOOP_MINUTES)
async def intelligence_gathering():
    await run_scan_once(trigger="loop")


@intelligence_gathering.before_loop
async def _before_loop():
    await bot.wait_until_ready()


# =========================================================
# 13) /dashboard (abre painel + força varredura)
# =========================================================
@bot.hybrid_command(name="dashboard", description="Abre o painel Mafty.")
@commands.has_permissions(administrator=True)
async def dashboard(ctx: commands.Context):
    """
    Abre o painel Mafty e configura o canal atual.
    Em seguida, dispara uma varredura imediata.

    FIX 40060:
    - só chama defer se response ainda não foi done
    FIX 10062:
    - sempre responde via followup (defer se possível)
    """
    gid = str(ctx.guild.id)

    cfg = load_json_safe(p("config.json"), {})
    if not isinstance(cfg, dict):
        log.error("config.json inválido. Recriando estrutura.")
        cfg = {}

    old_filters: List[str] = []
    if isinstance(cfg.get(gid), dict) and isinstance(cfg[gid].get("filters"), list):
        old_filters = cfg[gid]["filters"]

    # define canal atual como destino
    cfg[gid] = {"filters": old_filters, "channel_id": ctx.channel.id}
    save_json_safe(p("config.json"), cfg)

    view = FilterDashboard(ctx.guild.id)
    active = old_filters if old_filters else ["(nenhum)"]

    msg = (
        "🛰️ **PAINEL MAFTY ATIVADO**\n"
        f"📍 Canal configurado: {ctx.channel.mention}\n"
        f"📌 Filtros atuais: {', '.join(active)}\n\n"
        "Selecione as categorias para monitorar:"
    )

    # -----------------------------
    # SLASH (/dashboard)
    # -----------------------------
    if ctx.interaction is not None:
        try:
            # Só dá defer se ainda não foi ack
            if not ctx.interaction.response.is_done():
                await ctx.interaction.response.defer(ephemeral=True)

            # Sempre envia via followup (seguro com ou sem defer)
            await ctx.interaction.followup.send(msg, view=view, ephemeral=True)

        except discord.HTTPException as e:
            log.error(f"Falha ao responder /dashboard: {e}")
            try:
                await ctx.interaction.followup.send("❌ Falha ao abrir o painel. Tente novamente.", ephemeral=True)
            except Exception:
                pass
            return

        # força varredura
        await run_scan_once(trigger="dashboard")
        return

    # -----------------------------
    # PREFIXO (!dashboard)
    # -----------------------------
    await ctx.send(msg, view=view)
    await run_scan_once(trigger="dashboard")


@dashboard.error
async def dashboard_error(ctx: commands.Context, error: Exception):
    """Trata falta de permissão e evita stack trace inútil."""
    if isinstance(error, commands.MissingPermissions):
        msg = "❌ Você precisa ter **Administrador** para usar este comando."

        if ctx.interaction is not None:
            try:
                if not ctx.interaction.response.is_done():
                    await ctx.interaction.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.interaction.followup.send(msg, ephemeral=True)
            except discord.NotFound:
                pass
        else:
            await ctx.send(msg)
        return

    log.exception("Erro no comando /dashboard", exc_info=error)


# =========================================================
# 14) /status (mostra estatísticas do bot)
# =========================================================
@bot.hybrid_command(name="status", description="Mostra estatísticas do bot Mafty.")
async def status(ctx: commands.Context):
    """Exibe estatísticas e status atual do bot."""
    # Calcula próxima varredura
    next_scan = datetime.now() + timedelta(minutes=LOOP_MINUTES)
    next_scan_ts = int(next_scan.timestamp())
    
    embed = discord.Embed(
        title="🛰️ Status do Mafty Intel Bot",
        color=discord.Color.from_rgb(255, 0, 32),
        timestamp=datetime.now()
    )
    
    embed.add_field(
        name="⏰ Uptime",
        value=stats.format_uptime(),
        inline=True
    )
    
    embed.add_field(
        name="📡 Varreduras",
        value=f"{stats.scans_completed}",
        inline=True
    )
    
    embed.add_field(
        name="📰 Notícias Enviadas",
        value=f"{stats.news_posted}",
        inline=True
    )
    
    embed.add_field(
        name="📦 Cache Hits Total",
        value=f"{stats.cache_hits_total}",
        inline=True
    )
    
    if stats.last_scan_time:
        last_scan_str = f"<t:{int(stats.last_scan_time.timestamp())}:R>"
    else:
        last_scan_str = "Nenhuma ainda"
    
    embed.add_field(
        name="🕐 Última Varredura",
        value=last_scan_str,
        inline=True
    )
    
    embed.add_field(
        name="⏳ Próxima Varredura",
        value=f"<t:{next_scan_ts}:R>",
        inline=True
    )
    
    embed.set_footer(text=f"Bot v2.1 | Intervalo: {LOOP_MINUTES} min")
    
    await ctx.send(embed=embed)


# =========================================================
# 15) /forcecheck (força varredura imediata)
# =========================================================
@bot.hybrid_command(name="forcecheck", description="Força varredura imediata de feeds.")
@commands.has_permissions(administrator=True)
async def forcecheck(ctx: commands.Context):
    """Força uma varredura imediata sem abrir o dashboard."""
    # Slash command
    if ctx.interaction is not None:
        try:
            if not ctx.interaction.response.is_done():
                await ctx.interaction.response.defer(ephemeral=True)
            
            await run_scan_once(trigger="forcecheck")
            await ctx.interaction.followup.send("✅ Varredura forçada concluída!", ephemeral=True)
        except Exception as e:
            log.error(f"Erro em /forcecheck: {e}")
            try:
                await ctx.interaction.followup.send("❌ Falha ao executar varredura.", ephemeral=True)
            except:
                pass
        return
    
    # Prefixo
    msg = await ctx.send("🔎 Iniciando varredura forçada...")
    await run_scan_once(trigger="forcecheck")
    await msg.edit(content="✅ Varredura forçada concluída!")


@forcecheck.error
async def forcecheck_error(ctx: commands.Context, error: Exception):
    """Trata erros do comando /forcecheck."""
    if isinstance(error, commands.MissingPermissions):
        msg = "❌ Você precisa ter **Administrador** para usar este comando."
        
        if ctx.interaction is not None:
            try:
                if not ctx.interaction.response.is_done():
                    await ctx.interaction.response.send_message(msg, ephemeral=True)
                else:
                    await ctx.interaction.followup.send(msg, ephemeral=True)
            except discord.NotFound:
                pass
        else:
            await ctx.send(msg)
        return
    
    log.exception("Erro no comando /forcecheck", exc_info=error)



# =========================================================
# 14) on_ready (views persistentes + sync + start loop)
# =========================================================
@bot.event
async def on_ready():
    log.info(f"✅ Bot conectado como: {bot.user}")

    # Re-registra views persistentes
    cfg = load_json_safe(p("config.json"), {})
    if isinstance(cfg, dict):
        for gid in cfg.keys():
            try:
                bot.add_view(FilterDashboard(int(gid)))
                log.info(f"View persistente registrada para a guild {gid}.")
            except Exception as e:
                log.error(f"Falha ao registrar view persistente para guild {gid}: {e}")

    # Sync por guild (rápido)
    try:
        for g in bot.guilds:
            await bot.tree.sync(guild=discord.Object(id=g.id))
            log.info(f"Comandos sincronizados na guild: {g.name} ({g.id})")
    except Exception as e:
        log.error(f"Falha ao sincronizar comandos: {e}")

    # Inicia loop se ainda não estiver rodando
    if not intelligence_gathering.is_running():
        intelligence_gathering.start()
        log.info("Loop de inteligência iniciado com sucesso.")
        _log_next_run()


# =========================================================
# 15) START
# =========================================================
if __name__ == "__main__":
    bot.run(TOKEN)
