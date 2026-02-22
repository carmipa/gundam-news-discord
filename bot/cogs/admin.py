"""
Admin cog - Administrative commands (/forcecheck, /clean_state).
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from datetime import datetime

from utils.storage import p, load_json_safe, save_json_safe, create_backup, get_state_stats, clean_state

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
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await interaction.followup.send(f"✅ Varredura forçada concluída! ({now_str})", ephemeral=True)
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
    
    @app_commands.command(name="clean_state", description="Limpa partes do state.json (requer confirmação).")
    @app_commands.describe(
        tipo="Tipo de limpeza: dedup (histórico), http_cache (cache HTTP), html_hashes (monitor HTML), ou tudo",
        confirmar="Escolha 'Sim' para executar a limpeza; 'Não' só mostra o que seria feito"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name="🧹 Dedup (Histórico de links)", value="dedup"),
        app_commands.Choice(name="🌐 HTTP Cache (ETags)", value="http_cache"),
        app_commands.Choice(name="🔍 HTML Hashes (Monitor de sites)", value="html_hashes"),
        app_commands.Choice(name="⚠️ TUDO (Limpa tudo)", value="tudo"),
    ])
    @app_commands.choices(confirmar=[
        app_commands.Choice(name="Não (só mostrar o que seria feito)", value="não"),
        app_commands.Choice(name="Sim (executar limpeza)", value="sim"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def clean_state_cmd(
        self, 
        interaction: discord.Interaction, 
        tipo: str,
        confirmar: str = "não"
    ):
        """
        Limpa partes específicas do state.json.
        Requer confirmação explícita: escolha "Sim" para executar.
        """
        await interaction.response.defer(ephemeral=True)
        
        # Valida confirmação (confirmar pode ser None se o usuário não preencher)
        confirmar_val = (confirmar or "não").strip().lower()
        if confirmar_val not in ("sim", "yes", "s", "y", "confirmar", "confirm"):
            # Mostra estatísticas e pede confirmação
            state_file = p("state.json")
            state = load_json_safe(state_file, {})
            
            if not state:
                await interaction.followup.send(
                    "⚠️ state.json está vazio ou não existe.",
                    ephemeral=True
                )
                return
            
            stats = get_state_stats(state)
            guild_id = interaction.guild.id if interaction.guild else "DM"
            log.info(
                f"🧹 /clean_state: Preview solicitado (tipo={tipo}) por {interaction.user} (ID: {interaction.user.id}) [Guild: {guild_id}]"
            )
            
            # Tamanho do arquivo
            file_size = 0
            if os.path.exists(state_file):
                file_size = os.path.getsize(state_file) / 1024  # KB
            
            # Descrição do tipo
            tipo_desc_map = {
                "dedup": "🧹 **Dedup** (Histórico de links enviados)",
                "http_cache": "🌐 **HTTP Cache** (ETags e Last-Modified)",
                "html_hashes": "🔍 **HTML Hashes** (Monitoramento de sites)",
                "tudo": "⚠️ **TUDO** (Limpa tudo exceto metadados)"
            }
            tipo_desc = tipo_desc_map.get(tipo, tipo)
            
            # Avisos por tipo
            avisos = {
                "dedup": "⚠️ **ATENÇÃO:** Isso fará o bot repostar notícias já enviadas!",
                "http_cache": "ℹ️ Isso aumentará requisições HTTP, mas não causará repostagem.",
                "html_hashes": "⚠️ **ATENÇÃO:** Sites HTML serão detectados como 'mudados' novamente!",
                "tudo": "🚨 **ATENÇÃO CRÍTICA:** Isso limpará TUDO e pode causar repostagem em massa!"
            }.get(tipo, "")
            
            embed = discord.Embed(
                title="🧹 Limpeza do state.json",
                description=f"**Tipo selecionado:** {tipo_desc}\n\n{avisos}",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="📊 Estatísticas Atuais",
                value=(
                    f"**Dedup:** {stats['dedup_feeds']} feeds, {stats['dedup_total_links']} links\n"
                    f"**HTTP Cache:** {stats['http_cache_urls']} URLs\n"
                    f"**HTML Hashes:** {stats['html_hashes_sites']} sites\n"
                    f"**Tamanho:** {file_size:.1f} KB"
                ),
                inline=False
            )
            
            if stats['last_cleanup']:
                embed.add_field(
                    name="🕐 Última Limpeza Automática",
                    value=stats['last_cleanup'],
                    inline=False
                )
            
            embed.add_field(
                name="✅ Para Confirmar",
                value=f"Execute novamente `/clean_state`, escolha o mesmo tipo e em **confirmar** selecione **Sim (executar limpeza)**.",
                inline=False
            )
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            embed.add_field(name="📅 Data e hora", value=now_str, inline=False)
            embed.set_footer(text="⚠️ Um backup automático será criado antes da limpeza")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Confirmação recebida - procede com limpeza
        from core.scanner import scan_lock
        
        guild_id = interaction.guild.id if interaction.guild else "DM"
        log.info(
            f"🧹 /clean_state: Iniciando limpeza (tipo={tipo}) solicitado por {interaction.user} (ID: {interaction.user.id}) [Guild: {guild_id}]"
        )
        
        try:
            async with scan_lock:
                state_file = p("state.json")
                state = load_json_safe(state_file, {})
                
                if not state:
                    await interaction.followup.send(
                        "⚠️ state.json está vazio ou não existe.",
                        ephemeral=True
                    )
                    return
                
                # Estatísticas antes
                stats_before = get_state_stats(state)
                
                # Cria backup antes de limpar
                backup_path = create_backup(state_file)
                if not backup_path:
                    log.warning(f"🧹 /clean_state: Falha ao criar backup de state.json. Limpeza cancelada. User: {interaction.user.id} Guild: {guild_id}")
                    await interaction.followup.send(
                        "❌ Falha ao criar backup. Limpeza cancelada por segurança.",
                        ephemeral=True
                    )
                    return
                
                # Limpa state
                new_state, _ = clean_state(state, tipo)
                
                # Salva novo state
                save_json_safe(state_file, new_state)
                log.info(f"🧹 state.json salvo com sucesso após limpeza (tipo={tipo})")
                
                # Estatísticas depois
                stats_after = get_state_stats(new_state)
            
            # Log de auditoria
            log.info(
                f"[AUDIT] STATE_CLEANED | User: {interaction.user} (ID: {interaction.user.id}) | "
                f"Guild: {interaction.guild.id} | Type: {tipo} | "
                f"Backup: {os.path.basename(backup_path)} | "
                f"Before: dedup={stats_before['dedup_total_links']} links, "
                f"http_cache={stats_before['http_cache_urls']} URLs, "
                f"html_hashes={stats_before['html_hashes_sites']} sites | "
                f"After: dedup={stats_after['dedup_total_links']} links, "
                f"http_cache={stats_after['http_cache_urls']} URLs, "
                f"html_hashes={stats_after['html_hashes_sites']} sites"
            )
            
            # Mensagem de sucesso
            tipo_desc_map = {
                "dedup": "🧹 Dedup (Histórico de links)",
                "http_cache": "🌐 HTTP Cache (ETags)",
                "html_hashes": "🔍 HTML Hashes (Monitor de sites)",
                "tudo": "⚠️ TUDO (Limpa tudo)"
            }
            tipo_desc = tipo_desc_map.get(tipo, tipo)
            
            embed = discord.Embed(
                title="✅ Limpeza Concluída",
                description=f"**Tipo:** {tipo_desc}\n\n**Backup criado:** `{os.path.basename(backup_path)}`",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📊 Antes",
                value=(
                    f"Dedup: {stats_before['dedup_total_links']} links\n"
                    f"HTTP Cache: {stats_before['http_cache_urls']} URLs\n"
                    f"HTML Hashes: {stats_before['html_hashes_sites']} sites"
                ),
                inline=True
            )
            
            embed.add_field(
                name="📊 Depois",
                value=(
                    f"Dedup: {stats_after['dedup_total_links']} links\n"
                    f"HTTP Cache: {stats_after['http_cache_urls']} URLs\n"
                    f"HTML Hashes: {stats_after['html_hashes_sites']} sites"
                ),
                inline=True
            )
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            embed.set_footer(text=f"Executado por {interaction.user.display_name} em {now_str}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except ValueError as e:
            # Inclui InvalidCleanTypeError (herda de ValueError)
            log.error(f"Erro de validação em /clean_state: {e}")
            await interaction.followup.send(
                f"❌ Erro: {e}",
                ephemeral=True
            )
        except Exception as e:
            log.exception(f"Erro crítico em /clean_state: {type(e).__name__}: {e}")
            await interaction.followup.send(
                f"❌ Erro inesperado ao limpar state.json: {type(e).__name__}",
                ephemeral=True
            )
    
    @clean_state_cmd.error
    async def clean_state_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Trata erros do comando /clean_state."""
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
        
        log.exception("Erro no comando /clean_state", exc_info=error)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Ocorreu um erro ao executar o comando. Verifique os logs.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Ocorreu um erro ao executar o comando. Verifique os logs.",
                    ephemeral=True
                )
        except Exception as e:
            log.warning(f"Erro ao enviar mensagem de erro ao usuário: {type(e).__name__}: {e}")


async def setup(bot, run_scan_once_func):
    """
    Setup function para carregar o cog.
    
    Args:
        bot: Instância do bot Discord
        run_scan_once_func: Função de scan a ser injetada
    """
    await bot.add_cog(AdminCog(bot, run_scan_once_func))
