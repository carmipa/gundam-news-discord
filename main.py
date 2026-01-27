# =========================================================
# Gundam Intel Bot - "Mafty Sovereign" v2.1
# main.py (Modularized)
# =========================================================

import logging
import asyncio
import discord
from discord.ext import commands

from settings import TOKEN, COMMAND_PREFIX, LOG_LEVEL
from utils.storage import p, load_json_safe
from bot.views.filter_dashboard import FilterDashboard
from core.scanner import start_scheduler, run_scan_once
from web.server import start_web_server  # Novo web server

# Configuração de Logs
import os
import logging
from logging.handlers import RotatingFileHandler

# Configuração de Logs
# Garante que o diretório logs existe
os.makedirs("logs", exist_ok=True)

# Formatador
formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s")

# File Handler (Rotaciona a cada 5MB, mantém 3 arquivos)
file_handler = RotatingFileHandler("logs/bot.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
file_handler.setFormatter(formatter)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Root Logger Config
logging.basicConfig(
    level=LOG_LEVEL,
    handlers=[file_handler, console_handler]
)

log = logging.getLogger("MaftyIntel")


# =========================================================
# SETUP DO BOT
# =========================================================

async def main():
    # Intents
    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = True

    # Bot Instance
    bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

    # =========================================================
    # EVENTOS
    # =========================================================
    
    @bot.command()
    @commands.is_owner()
    async def sync(ctx):
        """Comando manual para sincronizar comandos Slash."""
        try:
            # Sync global
            synced = await bot.tree.sync()
            await ctx.send(f"✅ Sincronizado {len(synced)} comandos globalmente.")
            
            # Sync na guild atual também (garantia)
            if ctx.guild:
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced_guild = await ctx.bot.tree.sync(guild=ctx.guild)
                await ctx.send(f"✅ Sincronizado {len(synced_guild)} comandos na guild: {ctx.guild.name}")
        except Exception as e:
            await ctx.send(f"❌ Erro ao sincronizar: {e}")

    @bot.event
    async def on_ready():
        log.info(f"✅ Bot conectado como: {bot.user} (ID: {bot.user.id})")
        log.info(f"📊 Servidores conectados: {len(bot.guilds)}")

        # 0. Iniciar Web Server (Fase 10)
        await start_web_server(port=8080)

        # 1. Carregar Views Persistentes
        cfg = load_json_safe(p("config.json"), {})
        if isinstance(cfg, dict):
            for gid in cfg.keys():
                try:
                    bot.add_view(FilterDashboard(int(gid)))
                    log.info(f"View persistente registrada para guild {gid}")
                except Exception as e:
                    log.error(f"Erro view guild {gid}: {e}")

        # 2. Sync Comandos (Slash)
        try:
            # Sincroniza global (pode demorar) ou por guild
            # Para dev, sync por guild é mais rápido e garante update imediato
            # IMPORTANTE: É necessário copiar os globais para a guild antes de syncar a guild
            for guild in bot.guilds:
                bot.tree.copy_global_to(guild=discord.Object(id=guild.id))
                await bot.tree.sync(guild=discord.Object(id=guild.id))
                log.info(f"Comandos sincronizados (copy_global) em: {guild.name}")
        except Exception as e:
            log.error(f"Falha no sync de comandos: {e}")

        # 3. Iniciar Loop de Scanner
        start_scheduler(bot)

    # =========================================================
    # CARREGAR COGS
    # =========================================================
    
    # Função wrapper para injetar o bot no run_scan_once
    # Isso permite que os comandos chamem o scan manualmente
    async def bound_scan(trigger="manual"):
        await run_scan_once(bot, trigger)

    try:
        # Carrega extensões normais (que têm setup(bot))
        await bot.load_extension("bot.cogs.info")
        
        # Admin, Dashboard e Status precisam da função de scan injetada
        # Como load_extension não aceita args, importamos e setup manual 
        # ou usamos uma abordagem de injeção. 
        # Simplificação: Passamos via bot instance ou setup manual.
        
        # Abordagem Híbrida: Carregar Status normalmente, e Admin/Dashboard manualmente
        from bot.cogs.status import setup as setup_status
        from bot.cogs.admin import setup as setup_admin
        from bot.cogs.dashboard import setup as setup_dashboard
        
        await setup_status(bot, bound_scan)
        await setup_admin(bot, bound_scan)
        await setup_dashboard(bot, bound_scan)
        
        log.info("🧩 Cogs carregados com sucesso.")
    except Exception as e:
        log.exception(f"Falha ao carregar cogs: {e}")

    # =========================================================
    # START
    # =========================================================
    await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("🛑 Bot encerrado pelo usuário.")
    except Exception as e:
        log.exception(f"🔥 Erro fatal: {e}")
