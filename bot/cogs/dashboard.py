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
        try:
            msg = await interaction.channel.send(
                "🛰️ **MAFTY INTELLIGENCE DASHBOARD**\n"
                "Configure os filtros de notícias abaixo:",
                view=view
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ **Erro:** O bot não tem permissão para '**Enviar Mensagens**' neste canal.\n"
                "Por favor, ajuste as permissões do cargo do bot para este canal.",
                ephemeral=True
            )
            return
        # Confirma ao usuário
        await interaction.followup.send(
            f"✅ Dashboard criado! Canal configurado: <#{channel_id}>\nIniciando primeira varredura em segundo plano...",
            ephemeral=True
        )
        
        # Dispara varredura em background
        import asyncio
        asyncio.create_task(self.run_scan_once(trigger="dashboard"))
    
    @app_commands.command(name="set_canal", description="Define o canal onde o bot enviará notícias.")
    @app_commands.describe(canal="Canal de texto para notícias (opcional: usa o atual)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_canal(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        """
        Define o canal onde o bot enviará notícias de Gundam.
        Se nenhum canal for especificado, usa o canal atual.
        """
        # Tenta fazer defer, mas trata se a interação já expirou
        try:
            await interaction.response.defer(ephemeral=True)
            use_followup = True
        except discord.NotFound:
            # Interação expirada, tentará usar followup se possível
            log.warning("Interação expirada ao tentar defer em /set_canal")
            use_followup = False
        except Exception as e:
            log.error(f"Erro ao fazer defer em /set_canal: {type(e).__name__}: {e}")
            use_followup = False
        
        guild_id = str(interaction.guild.id)
        
        # Usa o canal fornecido ou o canal atual
        target_channel = canal if canal else interaction.channel
        channel_id = target_channel.id
        
        # Valida que o canal é de texto
        if not isinstance(target_channel, discord.TextChannel):
            msg = "❌ O canal deve ser um canal de texto!"
            try:
                if use_followup:
                    await interaction.followup.send(msg, ephemeral=True)
                elif not interaction.response.is_done():
                    await interaction.response.send_message(msg, ephemeral=True)
                else:
                    # Interação expirada, envia no canal
                    await target_channel.send(f"{interaction.user.mention}: {msg}")
            except (discord.NotFound, discord.InteractionResponded):
                # Interação expirada ou já respondida, envia no canal
                try:
                    await target_channel.send(f"{interaction.user.mention}: {msg}")
                except Exception as e:
                    log.error(f"Erro ao enviar mensagem de erro: {e}")
            return
        
        # Verifica permissões do bot no canal
        bot_member = interaction.guild.get_member(self.bot.user.id)
        if bot_member:
            permissions = target_channel.permissions_for(bot_member)
            if not permissions.send_messages:
                msg = (
                    f"❌ O bot não tem permissão para enviar mensagens no canal <#{channel_id}>!\n"
                    f"Por favor, conceda a permissão **Enviar Mensagens** ao bot."
                )
                try:
                    if use_followup:
                        await interaction.followup.send(msg, ephemeral=True)
                    elif not interaction.response.is_done():
                        await interaction.response.send_message(msg, ephemeral=True)
                    else:
                        await target_channel.send(f"{interaction.user.mention}: {msg}")
                except (discord.NotFound, discord.InteractionResponded):
                    try:
                        await target_channel.send(f"{interaction.user.mention}: {msg}")
                    except Exception as e:
                        log.error(f"Erro ao enviar mensagem de erro: {e}")
                return
            
            if not permissions.embed_links:
                msg = (
                    f"⚠️ O bot não tem permissão para enviar embeds no canal <#{channel_id}>.\n"
                    f"As notícias podem não aparecer corretamente. Considere conceder a permissão **Incorporar Links**."
                )
                try:
                    if use_followup:
                        await interaction.followup.send(msg, ephemeral=True)
                    elif not interaction.response.is_done():
                        await interaction.response.send_message(msg, ephemeral=True)
                    # Aviso não crítico, não precisa fallback
                except (discord.NotFound, discord.InteractionResponded):
                    pass  # Aviso não crítico, pode ignorar
        
        # Carrega config
        cfg = load_json_safe(p("config.json"), {})
        if not isinstance(cfg, dict):
            cfg = {}
        
        # Garante estrutura
        if guild_id not in cfg:
            cfg[guild_id] = {}
        
        # Obtém canal anterior para mensagem informativa
        old_channel_id = cfg[guild_id].get("channel_id")
        
        # Define novo canal
        cfg[guild_id]["channel_id"] = channel_id
        
        # Garante que filtros existam (não remove se já existirem)
        if "filters" not in cfg[guild_id]:
            cfg[guild_id]["filters"] = []
        
        # Salva
        save_json_safe(p("config.json"), cfg)
        
        log.info(f"Canal configurado para guild {guild_id}: {channel_id} (anterior: {old_channel_id})")
        
        # Mensagem de confirmação
        if old_channel_id and old_channel_id != channel_id:
            msg = (
                f"✅ Canal configurado com sucesso!\n\n"
                f"**Canal anterior:** <#{old_channel_id}>\n"
                f"**Canal atual:** <#{channel_id}>\n\n"
                f"As próximas notícias serão enviadas neste canal."
            )
        else:
            msg = (
                f"✅ Canal configurado com sucesso!\n\n"
                f"**Canal:** <#{channel_id}>\n\n"
                f"As notícias serão enviadas neste canal."
            )
        
        # Envia mensagem de confirmação
        try:
            if use_followup:
                await interaction.followup.send(msg, ephemeral=True)
            elif not interaction.response.is_done():
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                # Interação já foi respondida, envia no canal
                await target_channel.send(f"{interaction.user.mention}: {msg}")
        except (discord.NotFound, discord.InteractionResponded):
            # Interação expirada ou já respondida, tenta enviar no canal
            try:
                await target_channel.send(f"{interaction.user.mention}: {msg}")
            except Exception as e:
                log.warning(f"Não foi possível enviar confirmação: {type(e).__name__}: {e}")
        except Exception as e:
            log.error(f"Erro inesperado ao enviar confirmação: {type(e).__name__}: {e}")
            # Última tentativa: enviar no canal
            try:
                await target_channel.send(f"{interaction.user.mention}: ✅ Canal configurado: <#{channel_id}>")
            except Exception as e:
                log.warning(f"⚠️ Falha final inesperada ao confirmar canal: {e}")
    
    @set_canal.error
    async def set_canal_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Trata erros do comando /set_canal."""
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
        
        log.exception("Erro no comando /set_canal", exc_info=error)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Ocorreu um erro ao configurar o canal. Verifique os logs.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Ocorreu um erro ao configurar o canal. Verifique os logs.",
                    ephemeral=True
                )
        except Exception as e:
            log.warning(f"Erro ao enviar mensagem de erro ao usuário: {type(e).__name__}: {e}")

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
                log.debug("Interaction não encontrada ao tentar enviar mensagem de erro")
            except Exception as e:
                log.warning(f"Erro ao enviar mensagem de erro ao usuário: {type(e).__name__}: {e}")
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
