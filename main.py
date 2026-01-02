import discord
import os
import json
import feedparser
import asyncio
import logging
import aiohttp
from discord.ext import tasks, commands
from deep_translator import GoogleTranslator
from settings import TOKEN, COMMAND_PREFIX, LOOP_MINUTES

# --- 1. CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
log = logging.getLogger("MaftyBot")

# --- 2. CONFIGURAÇÃO DO BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


# --- 3. PERSISTÊNCIA DE DADOS (CONFIG E HISTÓRICO) ---
def load_json_safe(filename, default_value):
    """Carrega arquivos JSON com tratamento de erro."""
    try:
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Erro ao ler {filename}: {e}")
    return default_value


def save_json_safe(filename, data):
    """Salva dados em JSON para persistência na VPS."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log.error(f"Erro ao salvar {filename}: {e}")


# Carrega links já enviados para evitar repetição após reiniciar o bot
sent_links = set(load_json_safe('history.json', []))


# --- 4. INTERFACE DO DASHBOARD ---
class FilterDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = str(guild_id)

    async def update_selection(self, interaction, category):
        config = load_json_safe('config.json', {})
        server_data = config.get(self.guild_id, {"channel_id": interaction.channel_id, "filters": []})

        if category == "ALL":
            server_data["filters"] = ["gunpla", "movies", "games", "music", "fashion", "general"]
        elif category in server_data["filters"]:
            server_data["filters"].remove(category)
        else:
            server_data["filters"].append(category)

        config[self.guild_id] = server_data
        save_json_safe('config.json', config)

        ativos = ", ".join(server_data["filters"]).upper() if server_data["filters"] else "NENHUM"
        await interaction.response.send_message(f"📡 **Filtros Atualizados!**\nMonitorando: `{ativos}`", ephemeral=True)

    @discord.ui.button(label="Tudo", style=discord.ButtonStyle.success, emoji="🌟")
    async def all_btn(self, i, b):
        await self.update_selection(i, "ALL")

    @discord.ui.button(label="Gunpla", style=discord.ButtonStyle.primary, emoji="📦")
    async def gp_btn(self, i, b):
        await self.update_selection(i, "gunpla")

    @discord.ui.button(label="Filmes", style=discord.ButtonStyle.primary, emoji="🎬")
    async def mv_btn(self, i, b):
        await self.update_selection(i, "movies")

    @discord.ui.button(label="Games", style=discord.ButtonStyle.primary, emoji="🎮")
    async def gm_btn(self, i, b):
        await self.update_selection(i, "games")

    @discord.ui.button(label="Fashion", style=discord.ButtonStyle.primary, emoji="👕")
    async def fs_btn(self, i, b):
        await self.update_selection(i, "fashion")


# --- 5. LOOP DE INTELIGÊNCIA COM FILTRO GUNDAM ---
@tasks.loop(minutes=LOOP_MINUTES)
async def intelligence_gathering():
    log.info("Iniciando varredura de inteligência...")
    config = load_json_safe('config.json', {})
    sources = load_json_safe('sources.json', {"rss_feeds": [], "youtube_feeds": []})

    async with aiohttp.ClientSession() as session:
        for guild_id, settings in config.items():
            try:
                channel = bot.get_channel(settings.get("channel_id"))
                active_filters = settings.get("filters", [])
                if not channel or not active_filters: continue

                all_urls = sources.get('rss_feeds', []) + sources.get('youtube_feeds', [])

                for url in all_urls:
                    try:
                        async with session.get(url, timeout=15) as response:
                            if response.status != 200: continue
                            feed = feedparser.parse(await response.text())

                            for entry in feed.entries:
                                # 🛑 EVITA REPETIÇÃO: Checa se o link já foi enviado
                                if entry.link in sent_links: continue

                                title_lower = entry.title.lower()

                                # 🛡️ BARREIRA GUNDAM: Filtra apenas conteúdo relevante
                                gundam_keywords = ["gundam", "gunpla", "hg ", "mg ", "rg ", "pg ", "hathaway",
                                                   "witch from mercury", "bandai hobby", "model kit"]
                                if not any(kw in title_lower for kw in gundam_keywords):
                                    continue

                                # Categorização
                                category = "general"
                                if any(x in title_lower for x in ["gunpla", "model kit", "p-bandai"]):
                                    category = "gunpla"
                                elif any(x in title_lower for x in ["movie", "anime", "hathaway"]):
                                    category = "movies"
                                elif any(x in title_lower for x in ["game", "ps5", "xbox", "gbo2"]):
                                    category = "games"
                                elif any(x in title_lower for x in ["fashion", "clothing", "uniqlo"]):
                                    category = "fashion"
                                elif any(x in title_lower for x in ["ost", "music", "opening"]):
                                    category = "music"

                                if category in active_filters:
                                    try:
                                        title_pt = GoogleTranslator(source='auto', target='pt').translate(entry.title)
                                    except:
                                        title_pt = entry.title

                                    embed = discord.Embed(
                                        title="🚨 GUNDAM INTEL DETECTED",
                                        description=f"**[{category.upper()}]**\n{title_pt}",
                                        color=discord.Color.gold()
                                    )
                                    embed.set_footer(text=f"Fonte: {url.split('/')[2]}")

                                    await channel.send(embed=embed)
                                    await channel.send(entry.link)  # Gera preview de imagem

                                    # Adiciona ao histórico e salva no arquivo history.json
                                    sent_links.add(entry.link)
                                    save_json_safe('history.json', list(sent_links))

                                    log.info(f"Enviado: {entry.title[:50]}")
                                    await asyncio.sleep(2)

                    except Exception as e:
                        log.error(f"Erro no feed {url}: {e}")
            except Exception as e:
                log.error(f"Erro no servidor {guild_id}: {e}")


# --- 6. COMANDOS ---
@bot.command()
@commands.has_permissions(administrator=True)
async def dashboard(ctx):
    """Define o canal e abre os filtros."""
    config = load_json_safe('config.json', {})
    config[str(ctx.guild.id)] = config.get(str(ctx.guild.id), {"filters": []})
    config[str(ctx.guild.id)]["channel_id"] = ctx.channel.id
    save_json_safe('config.json', config)

    view = FilterDashboard(ctx.guild.id)
    await ctx.send(f"🛰️ **MAFTY DASHBOARD ATIVADO**\nCanal: {ctx.channel.mention}", view=view)


@bot.event
async def on_ready():
    log.info(f"--- {bot.user} ONLINE NA VPS ---")
    if not intelligence_gathering.is_running():
        intelligence_gathering.start()


try:
    bot.run(TOKEN)
except Exception as e:
    log.critical(f"Falha fatal: {e}")