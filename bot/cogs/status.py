"""
Status cog - /status command to show bot statistics.
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

from core.stats import stats
from settings import LOOP_MINUTES



class ScanButton(discord.ui.View):
    def __init__(self, run_scan_func):
        super().__init__(timeout=None)
        self.run_scan = run_scan_func

    @discord.ui.button(label="Verificar Agora", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="status_scan_now")
    async def scan_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            # Feedback imediato
            await interaction.followup.send("🔎 Iniciando verificação manual...", ephemeral=True)
            
            # Executa o scan
            await self.run_scan(trigger="manual_button")
            
            # Confirmação
            await interaction.followup.send("✅ Verificação concluída! Se houver notícias novas, elas foram enviadas para o canal.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erro ao verificar: {e}", ephemeral=True)


class StatusCog(commands.Cog):
    """Cog com comando de status do bot."""
    
    def __init__(self, bot, run_scan_once_func):
        self.bot = bot
        self.run_scan_once = run_scan_once_func
    
    @app_commands.command(name="status", description="Mostra estatísticas do bot Mafty.")
    async def status(self, interaction: discord.Interaction):
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
        
        # Adiciona o botão de scan
        view = ScanButton(self.run_scan_once)
        
        # EPHEMERAL: Apenas o usuário que digitou vê a mensagem.
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="now", description="Força uma verificação imediata de notícias.")
    async def now(self, interaction: discord.Interaction):
        """Verifica notícias imediatamente."""
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("🚀 Iniciando varredura manual (comando /now)...", ephemeral=True)
            await self.run_scan_once(trigger="command_now")
            await interaction.followup.send("✅ Scan finalizado.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erro: {e}", ephemeral=True)


async def setup(bot, run_scan_once_func):
    """Setup function para carregar o cog."""
    await bot.add_cog(StatusCog(bot, run_scan_once_func))
