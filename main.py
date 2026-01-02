import discord
import os
import json
import feedparser
import asyncio
import logging
from discord.ext import tasks, commands
from deep_translator import GoogleTranslator
from settings import TOKEN, ID_CANAL, COMMAND_PREFIX, LOOP_MINUTES

# --- LOGS E CONFIGS ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# Cache temporário (limpa ao reiniciar o bot para forçar reprocessamento)
sent_links = set()


# --- SISTEMA DE CONFIGURAÇÃO (SaaS) ---
def load_config():
    """Carrega as configurações de todos os servidores."""
    try:
        if os.path.exists('config.json') and os.path.getsize('config.json') > 0:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar config.json: {e}")
    return {}


def save_config(config):
    """Salva as preferências de filtros e canais por servidor."""
    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logging.error(f"Erro ao salvar config.json: {e}")


# --- PAINEL DE CONTROLE (BOTÕES DE FILTRO) ---
class FilterDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = str(guild_id)

    async def update_selection(self, interaction, category):
        config = load_config()
        server_settings = config.get(self.guild_id, {"channel_id": interaction.channel_id, "filters": []})

        if category == "ALL":
            server_settings["filters"] = ["gunpla", "movies", "games", "music", "fashion"]
        elif category in server_settings["filters"]:
            server_settings["filters"].remove(category)
        else:
            server_settings["filters"].append(category)

        config[self.guild_id] = server_settings
        save_config(config)

        ativos = ", ".join(server_settings["filters"]).upper() if server_settings["filters"] else "NENHUM"
        await interaction.response.send_message(f"📡 **Filtros Atualizados!**\nAtivos neste canal: `{ativos}`",
                                                ephemeral=True)

    @discord.ui.button(label="Tudo (All-In)", style=discord.ButtonStyle.success, emoji="🌟")
    async def all_btn(self, i, b):
        await self.update_selection(i, "ALL")

    @discord.ui.button(label="Gunpla", style=discord.ButtonStyle.primary, emoji="📦")
    async def gp_btn(self, i, b):
        await self.update_selection(i, "gunpla")

    @discord.ui.button(label="Filmes/Anime", style=discord.ButtonStyle.primary, emoji="🎬")
    async def mv_btn(self, i, b):
        await self.update_selection(i, "movies")

    @discord.ui.button(label="Games", style=discord.ButtonStyle.primary, emoji="🎮")
    async def gm_btn(self, i, b):
        await self.update_selection(i, "games")

    @discord.ui.button(label="Músicas", style=discord.ButtonStyle.primary, emoji="🎵")
    async def ms_btn(self, i, b):
        await self.update_selection(i, "music")


# --- MONITORAMENTO COM FILTROS E COMBO VISUAL ---
@tasks.loop(minutes=LOOP_MINUTES)
async def intelligence_gathering():
    try:
        config = load_config()
        try:
            with open('sources.json', 'r', encoding='utf-8') as f:
                sources = json.load(f)
        except:
            return

        for guild_id, settings in config.items():
            channel = bot.get_channel(settings.get("channel_id"))
            active_filters = settings.get("filters", [])
            if not channel or not active_filters: continue

            # Agora varre todas as listas do seu sources.json
            all_target_feeds = sources.get('rss_feeds', []) + sources.get('youtube_feeds', [])

            for url in all_target_feeds:
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries:
                        if entry.link in sent_links: continue

                        title_lower = entry.title.lower()
                        category = None

                        # Lógica de Categorização
                        if any(x in title_lower for x in ["gunpla", "hg ", "mg ", "rg ", "model kit", "p-bandai"]):
                            category = "gunpla"
                        elif any(x in title_lower for x in ["movie", "hathaway", "episode", "anime", "bdrip"]):
                            category = "movies"
                        elif any(x in title_lower for x in ["game", "ps5", "xbox", "steam", "nintendo", "bo2"]):
                            category = "games"
                        elif any(x in title_lower for x in ["ost", "music", "opening", "soundtrack"]):
                            category = "music"
                        elif any(x in title_lower for x in ["fashion", "clothing", "apparel", "uniqlo"]):
                            category = "fashion"

                        # Verificação de filtro ativo
                        if category in active_filters or ("gundam" in title_lower and "movies" in active_filters):
                            try:
                                title_pt = GoogleTranslator(source='auto', target='pt').translate(entry.title)
                            except:
                                title_pt = entry.title

                            # Envio do COMBO: Card Dourado + Link Puro para imagem grande
                            embed = discord.Embed(title="🚨 GUNDAM INTEL DETECTED", description=f"**{title_pt}**",
                                                  color=discord.Color.gold())
                            embed.set_footer(text=f"Fonte: {url.split('/')[2]}")

                            await channel.send(embed=embed)
                            await channel.send(entry.link)  # Dispara prévia visual automática

                            sent_links.add(entry.link)
                            await asyncio.sleep(2)
                except Exception as e:
                    logging.error(f"Erro no feed {url}: {e}")
    except Exception as e:
        logging.error(f"Erro no loop geral: {e}")


@bot.command()
@commands.has_permissions(administrator=True)
async def dashboard(ctx):
    """Abre o painel para selecionar as categorias desejadas."""
    view = FilterDashboard(ctx.guild.id)
    await ctx.send("🛰️ **MAFTY INTELLIGENCE DASHBOARD**\nAtive os filtros para este canal:", view=view)


@bot.event
async def on_ready():
    print(f"--- {bot.user} SaaS DASHBOARD OPERACIONAL ---")
    if not intelligence_gathering.is_running():
        intelligence_gathering.start()


bot.run(TOKEN)