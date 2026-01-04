"""
Dashboard cog - /dashboard command to configure filters.
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging

from bot.views.filter_dashboard import FilterDashboard
from utils.storage import p, load_json_safe, save_json_safe

log = logging.getLogger("MaftyIntel")


class DashboardCog(commands.Cog):
    """Cog com comando dashboard."""
    
    def __init__(self, bot, run_scan_once_func):
        self.bot = bot
        self.run_scan_once = run_scan_once_func
    
    @app_commands.command(name="dashboard", description="Abre o painel Mafty.")
    @app_commands.checks.has_permissions(administrator=True)
    async def dashboard(self, interaction: discord.Interaction):
        """
        Abre o painel Mafty e configura o canal atual.
        Em seguida, dispara uma varredura imediata.
        """
        # Defer pois vai fazer varredura
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        channel_id = interaction.channel.id
        
        # Carrega config
        cfg = load_json_safe(p("config.json"), {})
        if not isinstance(cfg, dict):
            cfg = {}
        
        # Garante estrutura
        if guild_id not in cfg:
            cfg[guild_id] = {}
        
        # Define canal
        cfg[guild_id]["channel_id"] = channel_id
        
        # Garante filtros
        if "filters" not in cfg[guild_id]:
            cfg[guild_id]["filters"] = []
        
        # Salva
        save_json_safe(p("config.json"), cfg)
        
        log.info(f"Dashboard aberto na guild {guild_id}, canal {channel_id}")
        
        # Cria view
        view = FilterDashboard(int(guild_id))
        
        # Envia painel no canal
        msg = await interaction.channel.send(
            "🛰️ **MAFTY INTELLIGENCE DASHBOARD**\n"
            "Configure os filtros de notícias abaixo:",
            view=view
        )
        
        # Confirma ao usuário
        await interaction.followup.send(
            f"✅ Dashboard criado! Canal configurado: <#{channel_id}>",
            ephemeral=True
        )
        
        # Dispara varredura
        await self.run_scan_once(trigger="dashboard")
    
    @dashboard.error
    async def dashboard_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Trata erros do comando /dashboard."""
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ Você precisa ter **Administrador** para usar este comando."
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    await interaction.followup.send(msg, ephemeral=True)
            except discord.NotFound:
                pass
            return
        
        log.exception("Erro no comando /dashboard", exc_info=error)


async def setup(bot, run_scan_once_func):
    """
    Setup function para carregar o cog.
    
    Args:
        bot: Instância do bot Discord
        run_scan_once_func: Função de scan a ser injetada
    """
    await bot.add_cog(DashboardCog(bot, run_scan_once_func))
