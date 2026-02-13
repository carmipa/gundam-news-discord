"""
Admin cog - Administrative commands (/forcecheck).
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging

log = logging.getLogger("MaftyIntel")


class AdminCog(commands.Cog):
    """Cog com comandos administrativos."""
    
    def __init__(self, bot, run_scan_once_func):
        self.bot = bot
        self.run_scan_once = run_scan_once_func
    
    @app_commands.command(name="forcecheck", description="Força varredura imediata de feeds.")
    @app_commands.checks.has_permissions(administrator=True)
    async def forcecheck(self, interaction: discord.Interaction):
        """Força uma varredura imediata sem abrir o dashboard."""
        try:
            await interaction.response.defer(ephemeral=True)
            await self.run_scan_once(trigger="forcecheck")
            await interaction.followup.send("✅ Varredura forçada concluída!", ephemeral=True)
        except Exception as e:
            log.exception(f"❌ Erro crítico em /forcecheck: {e}")
            try:
                await interaction.followup.send("❌ Falha ao executar varredura.", ephemeral=True)
            except discord.HTTPException as http_err:
                log.warning(f"Falha ao enviar mensagem de erro ao usuário: {http_err}")
            except Exception as unexpected_err:
                log.error(f"Erro inesperado ao tentar notificar usuário sobre falha: {unexpected_err}")
    
    @forcecheck.error
    async def forcecheck_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Trata erros do comando /forcecheck."""
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ Você precisa ter **Administrador** para usar este comando."
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    await interaction.followup.send(msg, ephemeral=True)
            except discord.NotFound:
                log.debug("Interaction não encontrada ao tentar enviar mensagem de erro")
            except Exception as e:
                log.warning(f"Erro ao enviar mensagem de erro ao usuário: {type(e).__name__}: {e}")
            return
        
        log.exception("Erro no comando /forcecheck", exc_info=error)


async def setup(bot, run_scan_once_func):
    """
    Setup function para carregar o cog.
    
    Args:
        bot: Instância do bot Discord
        run_scan_once_func: Função de scan a ser injetada
    """
    await bot.add_cog(AdminCog(bot, run_scan_once_func))
