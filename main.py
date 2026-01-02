import discord
import os
import json
import feedparser
import asyncio
import logging
import aiohttp
import ssl  # Importado para lidar com o erro de certificado SSL
from discord.ext import tasks, commands
from discord import app_commands
from deep_translator import GoogleTranslator
from settings import TOKEN, COMMAND_PREFIX, LOOP_MINUTES

# --- 1. CONFIGURAÇÃO DE LOGS ---
# Define como as mensagens de erro e status aparecerão no terminal.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
log = logging.getLogger("MaftyBot")

# --- 2. CONFIGURAÇÃO DO BOT E INTENTS ---
# Intents são permissões que o Bot precisa. Message Content é vital para ler comandos de prefixo.
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


# --- 3. PERSISTÊNCIA DE DADOS (JSON) ---
# Funções para salvar e carregar configurações, garantindo que o bot não esqueça o canal após reiniciar.
def load_json_safe(filename, default_value):
    try:
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        log.error(f"Erro ao ler {filename}: {e}")
    return default_value


def save_json_safe(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        log.error(f"Erro ao salvar {filename}: {e}")


# Carrega o histórico de links para evitar posts repetidos.
sent_links = set(load_json_safe('history.json', []))


# --- 4. INTERFACE DO DASHBOARD (BOTÕES) ---
# Cria a visualização com botões para o usuário escolher o que quer monitorar.
class FilterDashboard(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)  # Interface persistente
        self.guild_id = str(guild_id)

    async def update_selection(self, interaction, category):
        """Lógica para ativar/desativar filtros no banco de dados JSON."""
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

    # Definição dos botões individuais
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


# --- 5. LOOP DE INTELIGÊNCIA (RSS FEEDS) ---
# Esta função roda sozinha a cada X minutos procurando notícias.
@tasks.loop(minutes=LOOP_MINUTES)
async def intelligence_gathering():
    log.info("Iniciando varredura de inteligência...")
    config = load_json_safe('config.json', {})
    sources = load_json_safe('sources.json', {"rss_feeds": [], "youtube_feeds": []})

    # CORREÇÃO SSL: Cria um contexto que não falha no Windows por falta de certificado local
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
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
                                # Pula se já enviamos este link antes
                                if entry.link in sent_links: continue

                                title_lower = entry.title.lower()
                                # Filtro rigoroso: Só passa se tiver keywords de Gundam
                                gundam_keywords = ["gundam", "gunpla", "hg ", "mg ", "rg ", "pg ", "hathaway",
                                                   "model kit"]
                                if not any(kw in title_lower for kw in gundam_keywords): continue

                                # Classificação Automática por Categoria
                                category = "general"
                                if any(x in title_lower for x in ["gunpla", "model kit"]):
                                    category = "gunpla"
                                elif any(x in title_lower for x in ["movie", "anime"]):
                                    category = "movies"
                                elif any(x in title_lower for x in ["game", "gbo2"]):
                                    category = "games"

                                # Se o servidor quer essa categoria, envia!
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
                                    await channel.send(entry.link)  # Link fora para gerar preview

                                    sent_links.add(entry.link)
                                    save_json_safe('history.json', list(sent_links))
                                    await asyncio.sleep(2)  # Evita spam (Rate Limit)
                    except Exception as e:
                        log.error(f"Erro no feed {url}: {e}")
            except Exception as e:
                log.error(f"Erro no servidor {guild_id}: {e}")


# --- 6. COMANDOS HÍBRIDOS (VITAL PARA APP DIRECTORY) ---
# @bot.hybrid_command permite que o comando funcione como !dashboard E como /dashboard
@bot.hybrid_command(name="dashboard", description="Abre o painel de controle de inteligência Mafty.")
@commands.has_permissions(administrator=True)
async def dashboard(ctx):
    """Registra o canal e envia a interface de botões."""
    config = load_json_safe('config.json', {})
    config[str(ctx.guild.id)] = config.get(str(ctx.guild.id), {"filters": []})
    config[str(ctx.guild.id)]["channel_id"] = ctx.channel.id
    save_json_safe('config.json', config)

    view = FilterDashboard(ctx.guild.id)
    await ctx.send(f"🛰️ **MAFTY DASHBOARD ATIVADO**\nO sistema enviará notícias de Gundam neste canal.", view=view)


# --- 7. INICIALIZAÇÃO E SINCRONIZAÇÃO ---
@bot.event
async def on_ready():
    log.info(f"--- {bot.user} CONECTADO COM SUCESSO ---")

    # Isso "avisa" ao Discord que o bot tem Slash Commands.
    # Sem isso, o App Directory nunca liberará seu bot.
    try:
        synced = await bot.tree.sync()
        log.info(f"Sucesso! {len(synced)} comandos de barra sincronizados globalmente.")
    except Exception as e:
        log.error(f"Falha na sincronização: {e}")

    # Inicia o loop de notícias se não estiver rodando
    if not intelligence_gathering.is_running():
        intelligence_gathering.start()


# Roda o Bot usando o Token do arquivo settings.py ou .env
try:
    bot.run(TOKEN)
except Exception as e:
    log.critical(f"Erro ao iniciar o bot: {e}")