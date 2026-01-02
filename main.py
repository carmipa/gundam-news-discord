import discord
import os
import json
import feedparser
import asyncio
import logging
import aiohttp
import ssl
from discord.ext import tasks, commands
from discord import app_commands
from deep_translator import GoogleTranslator
from settings import TOKEN, COMMAND_PREFIX, LOOP_MINUTES

# --- 1. CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
log = logging.getLogger("MaftyBot")

# --- 2. CONFIGURAÇÃO DO BOT E CAMINHOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

intents = discord.Intents.default()
intents.message_content = True # Obrigatório para prefixos e comandos híbridos
intents.members = True        # Ative no Portal do Desenvolvedor (Bot -> Privileged Gateway Intents)

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# --- 3. PERSISTÊNCIA DE DADOS (JSON) ---
def get_path(filename):
    return os.path.join(BASE_DIR, filename)

def load_json_safe(filename, default_value):
    path = get_path(filename)
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Erro ao ler {filename}: {e}")
    return default_value

def save_json_safe(filename, data):
    path = get_path(filename)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log.error(f"Erro ao salvar {filename}: {e}")

sent_links = set(load_json_safe('history.json', []))

# --- 4. INTERFACE DO DASHBOARD (MÚLTIPLOS FILTROS) ---
class FilterDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None) # Mantém os botões ativos após reiniciar
        self.guild_id = str(guild_id)

    async def update_selection(self, interaction, category):
        """Lógica de 'Checkbox': Adiciona se não houver, remove se já estiver na lista."""
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

    # Botões organizados por linhas (rows)
    @discord.ui.button(label="Tudo", style=discord.ButtonStyle.success, emoji="🌟", row=0)
    async def all_btn(self, i, b): await self.update_selection(i, "ALL")

    @discord.ui.button(label="Gunpla", style=discord.ButtonStyle.primary, emoji="📦", row=1)
    async def gp_btn(self, i, b): await self.update_selection(i, "gunpla")

    @discord.ui.button(label="Filmes/Anime", style=discord.ButtonStyle.primary, emoji="🎬", row=1)
    async def mv_btn(self, i, b): await self.update_selection(i, "movies")

    @discord.ui.button(label="Games", style=discord.ButtonStyle.primary, emoji="🎮", row=1)
    async def gm_btn(self, i, b): await self.update_selection(i, "games")

    @discord.ui.button(label="Música", style=discord.ButtonStyle.primary, emoji="🎵", row=2)
    async def ms_btn(self, i, b): await self.update_selection(i, "music")

    @discord.ui.button(label="Fashion/Roupa", style=discord.ButtonStyle.primary, emoji="👕", row=2)
    async def fs_btn(self, i, b): await self.update_selection(i, "fashion")

    @discord.ui.button(label="Geral", style=discord.ButtonStyle.primary, emoji="🌐", row=2)
    async def gr_btn(self, i, b): await self.update_selection(i, "general")

# --- 5. LOOP DE INTELIGÊNCIA ---
@tasks.loop(minutes=LOOP_MINUTES)
async def intelligence_gathering():
    log.info("Iniciando varredura de inteligência...")
    config = load_json_safe('config.json', {})
    sources = load_json_safe('sources.json', {"rss_feeds": [], "youtube_feeds": []})

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        for guild_id, settings in config.items():
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
                            if entry.link in sent_links: continue

                            title_lower = entry.title.lower()
                            # BARREIRA GUNDAM: Só entra se tiver relação com a franquia
                            keywords = ["gundam", "gunpla", "hathaway", "witch from mercury", "bandai hobby", "model kit"]
                            if not any(kw in title_lower for kw in keywords): continue

                            # CLASSIFICAÇÃO
                            category = "general"
                            if any(x in title_lower for x in ["gunpla", "model kit"]): category = "gunpla"
                            elif any(x in title_lower for x in ["movie", "anime", "series"]): category = "movies"
                            elif any(x in title_lower for x in ["game", "ps5", "xbox", "gbo2"]): category = "games"
                            elif any(x in title_lower for x in ["music", "opening", "ost"]): category = "music"
                            elif any(x in title_lower for x in ["fashion", "clothing", "apparel", "uniqlo"]): category = "fashion"

                            # VERIFICA SE O USUÁRIO ATIVOU ESTA CATEGORIA
                            if category in active_filters:
                                try:
                                    title_pt = GoogleTranslator(source='auto', target='pt').translate(entry.title)
                                except:
                                    title_pt = entry.title

                                embed = discord.Embed(title="🚨 GUNDAM INTEL DETECTED",
                                                      description=f"**[{category.upper()}]**\n{title_pt}",
                                                      color=discord.Color.gold())
                                embed.set_footer(text=f"Fonte: {url.split('/')[2]}")
                                await channel.send(embed=embed)
                                await channel.send(entry.link)

                                sent_links.add(entry.link)
                                save_json_safe('history.json', list(sent_links))
                                await asyncio.sleep(2)
                except Exception as e:
                    log.error(f"Erro no feed {url}: {e}")

# --- 6. COMANDO DASHBOARD ---
@bot.hybrid_command(name="dashboard", description="Gerencie os filtros de notícias de Gundam.")
@commands.has_permissions(administrator=True)
async def dashboard(ctx):
    await ctx.defer(ephemeral=True) # Evita o erro de timeout do Discord

    config = load_json_safe('config.json', {})
    config[str(ctx.guild.id)] = config.get(str(ctx.guild.id), {"filters": []})
    config[str(ctx.guild.id)]["channel_id"] = ctx.channel.id
    save_json_safe('config.json', config)

    view = FilterDashboard(ctx.guild.id)
    await ctx.followup.send(f"🛰️ **DASHBOARD MAFTY**\nEscolha o que monitorar em {ctx.channel.mention}:", view=view)

# --- 7. INICIALIZAÇÃO ---
@bot.event
async def on_ready():
    log.info(f"--- {bot.user} ONLINE ---")
    try:
        await bot.tree.sync() # Sincroniza os comandos de barra com o Discord
        log.info("Sincronização global concluída.")
    except Exception as e:
        log.error(f"Erro na sincronização: {e}")

    if not intelligence_gathering.is_running():
        intelligence_gathering.start()

try:
    bot.run(TOKEN)
except Exception as e:
    log.critical(f"Falha fatal: {e}")