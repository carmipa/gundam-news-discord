import os
import json
import re
import ssl
import asyncio
import logging
from typing import Any, Dict, List, Set, Tuple

import discord
import aiohttp
import feedparser
from discord.ext import tasks, commands
from deep_translator import GoogleTranslator

# Importa configurações do seu projeto
from settings import TOKEN, COMMAND_PREFIX, LOOP_MINUTES


# =========================================================
# 1) CONFIGURAÇÃO DE LOGS
# =========================================================
# Logs em português e com formato consistente para facilitar troubleshooting na VPS
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
log = logging.getLogger("MaftyIntel")


# =========================================================
# 2) CONSTANTES DE FILTRO (PRECISÃO CIRÚRGICA)
# =========================================================
# Termos fundamentais para garantir que é Gundam
GUNDAM_CORE = [
    "gundam", "gunpla", "mobile suit", "universal century", "uc ",
    "rx-78", "zaku", "zeon", "char", "amuro", "hathaway", "mafty",
    "seed", "seed freedom", "witch from mercury", "g-witch",
    "p-bandai", "premium bandai", "ver.ka",
    "hg ", "mg ", "rg ", "pg ", "sd ", "fm ", "re/100"
]

# Blacklist para cortar ruído de feeds generalistas (ex.: sites de anime/game que misturam tudo)
BLACKLIST = [
    "one piece", "dragon ball", "naruto", "bleach",
    "pokemon", "digimon", "attack on titan",
    "jujutsu", "demon slayer"
]

# Mapa de categorias para o menu do dashboard
CAT_MAP = {
    "gunpla":  ["gunpla", "model kit", "kit", "ver.ka", "p-bandai", "premium bandai", "hg ", "mg ", "rg ", "pg ", "sd ", "fm ", "re/100"],
    "filmes":  ["anime", "episode", "movie", "film", "pv", "trailer", "teaser", "series", "season", "seed freedom", "witch from mercury", "hathaway"],
    "games":   ["game", "steam", "ps5", "xbox", "gbo2", "battle operation", "breaker", "gundam breaker"],
    "musica":  ["music", "ost", "soundtrack", "album", "opening", "ending"],
    "fashion": ["fashion", "clothing", "apparel", "t-shirt", "hoodie", "jacket", "merch"],
}

# Opções do dashboard (chave -> (label, emoji))
FILTER_OPTIONS = {
    "todos": ("TUDO", "🌟"),
    "gunpla": ("Gunpla", "🤖"),
    "filmes": ("Filmes", "🎬"),
    "games": ("Games", "🎮"),
    "musica": ("Música", "🎵"),
    "fashion": ("Fashion", "👕"),
}

# Todas as categorias (para o toggle “TUDO”)
ALL_CATEGORIES = ["gunpla", "filmes", "games", "musica", "fashion"]


# =========================================================
# 3) UTILITÁRIOS DE ARQUIVO JSON (SEGUROS)
# =========================================================
def load_json_safe(filepath: str, default: Any) -> Any:
    """
    Carrega JSON sem quebrar o bot se o arquivo estiver vazio/corrompido.
    Retorna "default" caso haja qualquer problema.
    """
    try:
        if not os.path.exists(filepath):
            log.warning(f"Arquivo '{filepath}' não existe. Usando valor padrão.")
            return default

        if os.path.getsize(filepath) == 0:
            log.warning(f"Arquivo '{filepath}' está vazio. Usando valor padrão.")
            return default

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        log.error(f"Falha ao carregar '{filepath}': {e}. Usando valor padrão.")
        return default


def save_json_safe(filepath: str, data: Any) -> None:
    """
    Salva JSON com indentação e sem quebrar o bot em caso de erro.
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Falha ao salvar '{filepath}': {e}")


# =========================================================
# 4) LIMPEZA DE TEXTO / TRADUÇÃO
# =========================================================
_HTML_RE = re.compile(r"<.*?>|&([a-z0-9]+|#[0-9]{1,6});", flags=re.IGNORECASE)
_WS_RE = re.compile(r"\s+")

def clean_html(raw_html: str) -> str:
    """
    Remove tags HTML e entidades para evitar resumos poluídos.
    """
    if not raw_html:
        return ""
    txt = re.sub(_HTML_RE, " ", raw_html)
    txt = re.sub(_WS_RE, " ", txt).strip()
    return txt


def translate_to_pt(text: str) -> str:
    """
    Traduz para PT-BR com limite de tamanho (evita erros por payload grande).
    Em falha, retorna o texto limpo (sem HTML).
    """
    try:
        if not text:
            return ""
        cleaned = clean_html(text)
        # Limite para evitar falha de request muito grande
        return GoogleTranslator(source="auto", target="pt").translate(cleaned[:1000])
    except Exception as e:
        log.warning(f"Falha ao traduzir texto (usando texto limpo). Motivo: {e}")
        return clean_html(text)


# =========================================================
# 5) NORMALIZAÇÃO DO sources.json (ROBUSTA)
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

    # Remove duplicados mantendo a ordem
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# =========================================================
# 6) CONFIGURAÇÃO DO BOT (INTENTS)
# =========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True  # Necessário para comandos por prefixo (!dashboard, se usado)

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


# =========================================================
# 7) FUNÇÕES DE FILTRO (ANTI-LIXO + CATEGORIAS)
# =========================================================
def _contains_any(hay: str, needles: List[str]) -> bool:
    """
    Retorna True se qualquer termo em needles existir no texto hay.
    """
    return any(n in hay for n in needles)


def match_intel(guild_id: str, title: str, summary: str, config: Dict[str, Any]) -> bool:
    """
    Decide se uma notícia deve ser enviada para uma guild:
      1) Precisa existir filtro configurado
      2) Corta blacklist
      3) Exige núcleo Gundam
      4) Se "todos" ativo -> aceita
      5) Caso contrário, precisa bater em alguma categoria escolhida
    """
    g = config.get(str(guild_id), {})
    filters = g.get("filters", [])

    if not isinstance(filters, list) or not filters:
        return False

    # Limpa HTML antes de avaliar (reduz falsos positivos)
    content = f"{clean_html(title)} {clean_html(summary)}".lower()

    # Corta ruído
    if _contains_any(content, BLACKLIST):
        return False

    # Exige termos fundamentais de Gundam
    if not _contains_any(content, GUNDAM_CORE):
        return False

    # Se "todos" ativo, passa direto
    if "todos" in filters:
        return True

    # Caso contrário, precisa bater em uma categoria selecionada
    for f in filters:
        kws = CAT_MAP.get(f, [])
        if kws and _contains_any(content, kws):
            return True

    return False


# =========================================================
# 8) HISTÓRICO (PRESERVA RECÊNCIA)
# =========================================================
def load_history() -> Tuple[List[str], Set[str]]:
    """
    Mantém o arquivo como lista (preserva ordem),
    mas usa set em memória para busca rápida.
    """
    h = load_json_safe("history.json", [])
    if not isinstance(h, list):
        log.warning("history.json inválido. Reiniciando histórico.")
        h = []
    h = [x for x in h if isinstance(x, str)]
    return h, set(h)


def save_history(history_list: List[str], limit: int = 2000) -> None:
    """
    Salva apenas os últimos 'limit' itens para evitar crescimento infinito.
    """
    save_json_safe("history.json", history_list[-limit:])


# =========================================================
# 9) DASHBOARD PERSISTENTE (VIEW)
# =========================================================
class FilterDashboard(discord.ui.View):
    """
    Dashboard persistente:
      - timeout=None: essencial para botões continuarem válidos
      - custom_id estável: permite re-registrar a View após restart
    """

    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = str(guild_id)
        self._rebuild()

    def _cfg(self) -> Dict[str, Any]:
        """
        Carrega config.json e garante estrutura mínima para a guild.
        """
        cfg = load_json_safe("config.json", {})
        if not isinstance(cfg, dict):
            log.error("config.json inválido. Recriando estrutura.")
            cfg = {}

        cfg.setdefault(self.guild_id, {"filters": [], "channel_id": None})

        if not isinstance(cfg[self.guild_id].get("filters"), list):
            cfg[self.guild_id]["filters"] = []

        return cfg

    def _save(self, cfg: Dict[str, Any]) -> None:
        save_json_safe("config.json", cfg)

    def _filters(self) -> List[str]:
        cfg = self._cfg()
        return list(cfg[self.guild_id].get("filters", []))

    def _set_filters(self, new_filters: List[str]) -> None:
        cfg = self._cfg()
        # Remove duplicados mantendo ordem
        cfg[self.guild_id]["filters"] = list(dict.fromkeys(new_filters))
        self._save(cfg)

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        """
        Apenas administradores podem alterar filtros.
        """
        try:
            return bool(interaction.user.guild_permissions.administrator)
        except Exception:
            return False

    def _rebuild(self) -> None:
        """
        Reconstrói botões com cores:
          - Verde (success) se estiver ativo
          - Cinza (secondary) se estiver desligado
        """
        self.clear_items()
        active = set(self._filters())

        # Botões de categorias
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

        # Botão "Ver filtros"
        show_btn = discord.ui.Button(
            label="Ver filtros",
            emoji="📌",
            style=discord.ButtonStyle.primary,
            custom_id=f"mafty:show:{self.guild_id}"
        )
        show_btn.callback = self._show_callback
        self.add_item(show_btn)

        # Botão "Reset"
        reset_btn = discord.ui.Button(
            label="Reset",
            emoji="🔄",
            style=discord.ButtonStyle.danger,
            custom_id=f"mafty:reset:{self.guild_id}"
        )
        reset_btn.callback = self._reset_callback
        self.add_item(reset_btn)

    async def _toggle_callback(self, interaction: discord.Interaction):
        """
        Alterna um filtro e atualiza visualmente o menu.
        """
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem alterar filtros.", ephemeral=True)
            return

        cid = str(interaction.data.get("custom_id", ""))
        key = cid.split(":")[-1] if cid else ""

        current = set(self._filters())

        if key == "todos":
            # Toggle geral
            current = set() if "todos" in current else {"todos", *ALL_CATEGORIES}
        else:
            # Mudança manual remove "todos"
            current.discard("todos")
            if key in current:
                current.remove(key)
            else:
                current.add(key)

        self._set_filters(list(current))
        self._rebuild()
        await interaction.response.edit_message(view=self)

    async def _show_callback(self, interaction: discord.Interaction):
        """
        Mostra filtros ativos em mensagem ephemeral.
        """
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem ver os filtros.", ephemeral=True)
            return

        active = self._filters()
        if not active:
            await interaction.response.send_message("📌 Nenhum filtro ativo no momento.", ephemeral=True)
            return

        await interaction.response.send_message(f"📌 Filtros ativos: {', '.join(active)}", ephemeral=True)

    async def _reset_callback(self, interaction: discord.Interaction):
        """
        Reseta todos os filtros.
        """
        if not self._is_admin(interaction):
            await interaction.response.send_message("❌ Apenas administradores podem resetar os filtros.", ephemeral=True)
            return

        self._set_filters([])
        self._rebuild()
        await interaction.response.edit_message(view=self)


# =========================================================
# 10) LOOP DE INTELIGÊNCIA (SCANNER)
# =========================================================
@tasks.loop(minutes=LOOP_MINUTES)
async def intelligence_gathering():
    """
    Varre feeds e posta notícias relevantes no canal configurado de cada guild.
    """
    log.info("🔎 Iniciando varredura de inteligência...")

    config = load_json_safe("config.json", {})
    if not isinstance(config, dict) or not config:
        log.info("Nenhuma guild configurada em config.json. Nada para processar.")
        return

    sources_raw = load_json_safe("sources.json", {})
    urls = normalize_sources_to_urls(sources_raw)

    if not urls:
        log.warning("Nenhuma URL válida encontrada em sources.json. Verifique seu arquivo.")
        return

    history_list, history_set = load_history()

    # SSL tolerante (alguns feeds antigos falham handshake)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # User-Agent ajuda em sites que bloqueiam requests genéricas
    headers = {"User-Agent": "Mozilla/5.0 MaftyIntel/1.0"}

    # Timeout total do request (evita travar o loop)
    timeout = aiohttp.ClientTimeout(total=25)
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    async with aiohttp.ClientSession(connector=connector, headers=headers, timeout=timeout) as session:
        for url in urls:
            try:
                async with session.get(url) as resp:
                    text = await resp.text(errors="ignore")
            except Exception as e:
                log.error(f"Falha ao baixar feed '{url}': {e}")
                continue

            feed = feedparser.parse(text)
            entries = getattr(feed, "entries", []) or []

            for entry in entries:
                link = entry.get("link") or ""
                if not link:
                    continue

                # Deduplicação
                if link in history_set:
                    continue

                title = entry.get("title") or ""
                summary = entry.get("summary") or entry.get("description") or ""

                # Avalia para cada guild configurada
                for gid, gdata in config.items():
                    if not isinstance(gdata, dict):
                        log.warning(f"Config inválida para guild '{gid}'. Ignorando.")
                        continue

                    channel_id = gdata.get("channel_id")
                    if not isinstance(channel_id, int):
                        # Sem canal configurado, não posta
                        continue

                    # Aplica filtros
                    if not match_intel(str(gid), title, summary, config):
                        continue

                    channel = bot.get_channel(channel_id)
                    if channel is None:
                        log.warning(f"Canal {channel_id} não encontrado na guild {gid}. Verifique permissões/ID.")
                        continue

                    # Monta mensagem traduzida
                    t_pt = translate_to_pt(title)
                    s_pt = translate_to_pt(summary)[:350]

                    try:
                        await channel.send(
                            f"🛰️ **INTEL MAFTY**\n"
                            f"**{t_pt}**\n"
                            f"{s_pt}\n"
                            f"🔗 {link}"
                        )
                        # Marca como enviado
                        history_set.add(link)
                        history_list.append(link)

                        # Pequena pausa para evitar rate limit
                        await asyncio.sleep(1)

                    except Exception as e:
                        log.error(f"Falha ao enviar mensagem no canal {channel_id}: {e}")

    # Salva histórico com limite para não crescer infinito
    save_history(history_list, limit=2000)
    log.info("✅ Varredura concluída com sucesso.")


@intelligence_gathering.before_loop
async def _before_loop():
    """
    Garante que o bot está pronto antes de iniciar o loop.
    """
    await bot.wait_until_ready()


# =========================================================
# 11) COMANDO DASHBOARD (HYBRID CORRETO)
# =========================================================
@bot.hybrid_command(name="dashboard", description="Abre o painel Mafty.")
@commands.has_permissions(administrator=True)
async def dashboard(ctx: commands.Context):
    """
    - Se for slash: responde ephemeral
    - Se for prefixo: responde normal
    Também registra o canal atual como canal do bot nesta guild.
    """
    gid = str(ctx.guild.id)

    cfg = load_json_safe("config.json", {})
    if not isinstance(cfg, dict):
        log.error("config.json inválido. Recriando estrutura.")
        cfg = {}

    # Mantém filtros antigos, se existirem
    old_filters = []
    if isinstance(cfg.get(gid), dict) and isinstance(cfg[gid].get("filters"), list):
        old_filters = cfg[gid]["filters"]

    # Define o canal atual como destino das notícias
    cfg[gid] = {"filters": old_filters, "channel_id": ctx.channel.id}
    save_json_safe("config.json", cfg)

    view = FilterDashboard(ctx.guild.id)
    active = old_filters if old_filters else ["(nenhum)"]

    msg = (
        "🛰️ **PAINEL MAFTY ATIVADO**\n"
        f"📍 Canal configurado: {ctx.channel.mention}\n"
        f"📌 Filtros atuais: {', '.join(active)}\n\n"
        "Selecione as categorias para monitorar:"
    )

    # Se for slash command (Interaction), usamos defer + followup com ephemeral
    if ctx.interaction is not None:
        await ctx.interaction.response.defer(ephemeral=True)
        await ctx.interaction.followup.send(msg, view=view, ephemeral=True)
        return

    # Se for comando por prefixo, não existe ephemeral
    await ctx.send(msg, view=view)


# =========================================================
# 12) EVENTO on_ready (PERSISTÊNCIA + SYNC POR GUILD)
# =========================================================
@bot.event
async def on_ready():
    """
    - Re-registra Views persistentes após restart
    - Sincroniza comandos por guild (rápido e evita CommandNotFound)
    - Inicia o loop de inteligência
    """
    log.info(f"✅ Bot conectado como: {bot.user}")

    # 1) Re-registra Views persistentes para guilds do config.json
    cfg = load_json_safe("config.json", {})
    if isinstance(cfg, dict):
        for gid in cfg.keys():
            try:
                bot.add_view(FilterDashboard(int(gid)))
                log.info(f"View persistente registrada para a guild {gid}.")
            except Exception as e:
                log.error(f"Falha ao registrar view persistente para guild {gid}: {e}")

    # 2) Sincronização por guild (propaga rápido e reduz erros)
    try:
        for g in bot.guilds:
            guild_obj = discord.Object(id=g.id)
            bot.tree.clear_commands(guild=guild_obj)
            await bot.tree.sync(guild=guild_obj)
            log.info(f"Comandos sincronizados na guild: {g.name} ({g.id})")
    except Exception as e:
        log.error(f"Falha ao sincronizar comandos: {e}")

    # 3) Inicia loop de inteligência se ainda não estiver rodando
    if not intelligence_gathering.is_running():
        intelligence_gathering.start()
        log.info("Loop de inteligência iniciado com sucesso.")


# =========================================================
# 13) START
# =========================================================
if __name__ == "__main__":
    bot.run(TOKEN)
