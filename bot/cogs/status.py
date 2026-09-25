"""
Status cog - /status command to show bot statistics.
"""
import discord
import logging
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

from core.stats import stats
from settings import LOOP_MINUTES, LOOP_INTERVAL_STR
from bot.permissoes import responder_recusa, MENSAGEM_SOMENTE_ADMIN
from bot.varredura_manual import texto_do_pedido

log = logging.getLogger("MaftyIntel")



class ScanButton(discord.ui.View):
    """
    Botão "Verificar Agora" anexado ao /status.

    O /status é público, mas o botão dispara a varredura GLOBAL: vale a mesma
    regra do /now — Administrador da guild, e a porta única do engine, que impõe
    o intervalo mínimo entre varreduras.
    """

    def __init__(self, pedir_varredura):
        super().__init__(timeout=None)
        self.pedir_varredura = pedir_varredura

    @discord.ui.button(label="Verificar Agora", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="status_scan_now")
    async def scan_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        permissoes = getattr(interaction, "permissions", None)
        if not (permissoes and permissoes.administrator):
            await responder_recusa(interaction, MENSAGEM_SOMENTE_ADMIN)
            return
        try:
            resultado, segundos = self.pedir_varredura("manual_button")
            await interaction.response.send_message(texto_do_pedido(resultado, segundos), ephemeral=True)
        except Exception as e:
            log.exception(f"Erro ao pedir verificação manual: {type(e).__name__}: {e}")
            await responder_recusa(interaction, f"❌ Erro ao pedir a verificação: {type(e).__name__}")


class StatusCog(commands.Cog):
    """Cog com comando de status do bot."""
    
    def __init__(self, bot, pedir_varredura):
        self.bot = bot
        self.pedir_varredura = pedir_varredura
    
    @app_commands.command(name="status", description="Mostra estatísticas do bot Mafty.")
    async def status(self, interaction: discord.Interaction):
        """Exibe estatísticas e status atual do bot."""
        await interaction.response.defer(ephemeral=True) # Fix timeout
        
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
        
        embed.set_footer(text=f"Bot v2.1 | Intervalo: {LOOP_INTERVAL_STR}")
        
        # Adiciona o botão de scan
        view = ScanButton(self.pedir_varredura)
        
        # EPHEMERAL: Apenas o usuário que digitou vê a mensagem.
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="now", description="Força uma verificação imediata de notícias. (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def now(self, interaction: discord.Interaction):
        """
        Pede uma varredura imediata.

        PROPÓSITO DE NEGÓCIO:
            Não esperar o próximo ciclo depois de configurar filtros ou canal.

        INVARIANTES DO DOMÍNIO:
            - Exige Administrador: a varredura é global e consome o orçamento de
              rate limit das fontes para todos os servidores.
            - Passa pela porta única do engine (intervalo mínimo, sem sobreposição).
            - A resposta diz o que aconteceu de fato — iniciada, em andamento ou
              aguardando —, nunca que a varredura terminou.

        COMPORTAMENTO EM CASO DE FALHA:
            Exceção ao pedir é logada e o usuário recebe o tipo do erro.
        """
        try:
            resultado, segundos = self.pedir_varredura("command_now")
            await interaction.response.send_message(texto_do_pedido(resultado, segundos), ephemeral=True)
        except Exception as e:
            log.exception(f"Erro ao executar comando /now: {type(e).__name__}: {e}")
            await responder_recusa(interaction, f"❌ Erro: {type(e).__name__}")

    @now.error
    async def now_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Trata erros do /now."""
        if isinstance(error, app_commands.MissingPermissions):
            await responder_recusa(interaction, MENSAGEM_SOMENTE_ADMIN)
            return
        log.exception("Erro no comando /now", exc_info=error)


async def setup(bot, pedir_varredura):
    """Setup function para carregar o cog."""
    await bot.add_cog(StatusCog(bot, pedir_varredura))
