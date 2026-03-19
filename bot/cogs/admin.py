"""
Admin cog - Administrative commands (/forcecheck, /clean_state, /server_log).
"""
import io
import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from datetime import datetime

from utils.storage import p, load_json_safe, save_json_safe, create_backup, get_state_stats, clean_state

log = logging.getLogger("MaftyIntel")

# Caminho do arquivo de log (mesmo usado em utils.logger)
LOG_FILE_PATH = os.path.abspath("logs/bot.log")
DISCORD_MAX_MESSAGE_LENGTH = 2000
# Espaço reservado para header (ex.: "📋 **Log do servidor** (últimas 99 linhas) — ...")
LOG_HEADER_RESERVED = 120
MAX_LOG_DISPLAY_CHARS = DISCORD_MAX_MESSAGE_LENGTH - LOG_HEADER_RESERVED - 7  # 7 = "```log\n" + "\n```"
# Limite para o .txt anexado (últimas N linhas sem truncar por caractere; 200 KB)
MAX_LOG_FILE_CHARS = 200 * 1024

def _read_log_tail(filepath: str, n_lines: int = 50, max_chars: int = MAX_LOG_DISPLAY_CHARS) -> str:
    """
    Lê as últimas N linhas do arquivo de log sem carregar o arquivo inteiro.
    Retorna texto truncado a max_chars para caber na mensagem.
    """
    if not os.path.exists(filepath):
        return ""
    try:
        size = os.path.getsize(filepath)
        # Lê no máximo os últimos 200 KB para não carregar arquivo gigante
        read_size = min(size, 200 * 1024)
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            f.seek(max(0, size - read_size))
            if f.tell() > 0:
                f.readline()  # descarta linha parcial
            lines = f.readlines()
        tail = lines[-n_lines:] if len(lines) >= n_lines else lines
        text = "".join(tail).strip()
        if len(text) > max_chars:
            text = "...\n" + text[-max_chars:]
        return text or "(arquivo vazio)"
    except (OSError, IOError) as e:
        log.warning(f"Falha ao ler log para /server_log: {e}")
        return f"(erro ao ler arquivo: {e})"


def _build_log_message(header: str, content: str) -> str:
    """Monta mensagem header + code block do log garantindo <= 2000 caracteres (limite do Discord)."""
    code_wrapper_len = 7  # "```log\n" + "\n```"
    max_content = DISCORD_MAX_MESSAGE_LENGTH - len(header) - code_wrapper_len
    if len(content) > max_content:
        content = "...\n" + content[-(max_content - 4) :]
    body = f"```log\n{content}\n```"
    return header + body


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
            await interaction.response.send_message("⏳ Varredura forçada iniciada em segundo plano. Pode demorar devido à quantidade de notícias. Acompanhe o canal!", ephemeral=True)
            import asyncio
            asyncio.create_task(self.run_scan_once(trigger="forcecheck"))
        except Exception as e:
            log.exception(f"❌ Erro crítico em /forcecheck: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Falha ao iniciar varredura.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Falha ao iniciar varredura.", ephemeral=True)
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
        tipo="Limpar: dedup, http_cache, html_hashes ou tudo",
        confirmar="Sim = executar limpeza; Não = só mostrar preview"
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

    # -------------------------------------------------------------------------
    # /server_log — visualizar log do servidor (últimas N linhas + botão Atualizar)
    # -------------------------------------------------------------------------

    @app_commands.command(
        name="server_log",
        description="Exibe as últimas linhas do log do servidor. Botão Atualizar renova. (Admin)"
    )
    @app_commands.describe(linhas="Número de linhas (10-100, padrão 50)")
    @app_commands.checks.has_permissions(administrator=True)
    async def server_log(self, interaction: discord.Interaction, linhas: int = 50):
        """Envia as últimas N linhas do logs/bot.log (mesmo log que roda no servidor/docker) e botão Atualizar."""
        await interaction.response.defer(ephemeral=True)
        linhas = max(10, min(100, linhas))
        filepath = LOG_FILE_PATH
        content = _read_log_tail(filepath, n_lines=linhas)
        if not content or content.startswith("(erro"):
            await interaction.followup.send(
                f"📋 **Log do servidor**\n\n{content or 'Arquivo de log não encontrado ou vazio.'}",
                ephemeral=True
            )
            return
        header = f"📋 **Log do servidor** (últimas {linhas} linhas) — use **Atualizar** para ver o que entrou agora.\n"
        view = _LogRefreshView(linhas=linhas, timeout=300)
        msg_content = _build_log_message(header, content)
        # Anexo .txt com o log completo (até MAX_LOG_FILE_CHARS) para quando o resumo na mensagem é truncado
        content_for_file = _read_log_tail(filepath, n_lines=linhas, max_chars=MAX_LOG_FILE_CHARS)
        log_file = discord.File(
            io.BytesIO(content_for_file.encode("utf-8")),
            filename="bot_log.txt"
        )
        await interaction.followup.send(msg_content, ephemeral=True, view=view, files=[log_file])

    @server_log.error
    async def server_log_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Trata erros do /server_log."""
        if isinstance(error, app_commands.MissingPermissions):
            try:
                await interaction.response.send_message(
                    "❌ Você precisa de **Administrador** para ver o log do servidor.",
                    ephemeral=True
                )
            except Exception as e:
                log.warning(f"⚠️ Falha silenciosa ao notificar erro de permissão ao administrador: {e}")
            return
        log.exception("Erro no comando /server_log", exc_info=error)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Erro ao ler o log.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Erro ao ler o log.", ephemeral=True)
        except Exception as e:
            log.warning(f"⚠️ Falha silenciosa ao enviar feedback de erro de log ao administrador: {e}")


class _LogRefreshView(discord.ui.View):
    """View com botão para atualizar o conteúdo do log na mesma mensagem."""

    def __init__(self, linhas: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.linhas = linhas

    @discord.ui.button(label="Atualizar", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer_update()
        try:
            content = _read_log_tail(LOG_FILE_PATH, n_lines=self.linhas)
            header = f"📋 **Log do servidor** (últimas {self.linhas} linhas) — atualizado.\n"
            if not content or content.startswith("(erro"):
                msg = header + (f"```\n{content or '(arquivo vazio)'}\n```" if content else "```\n(arquivo vazio)\n```")
            else:
                msg = _build_log_message(header, content)
            msg = msg[:DISCORD_MAX_MESSAGE_LENGTH]
            await interaction.message.edit(content=msg, view=self)
        except Exception as e:
            log.exception("Erro ao atualizar log no botão Atualizar: %s", e)
            try:
                await interaction.followup.send(
                    "Não foi possível atualizar o log. Tente **/server_log** de novo.",
                    ephemeral=True
                )
            except Exception as e:
                log.warning(f"⚠️ Falha silenciosa ao notificar erro de atualização da view: {e}")


async def setup(bot, run_scan_once_func):
    """
    Setup function para carregar o cog.
    
    Args:
        bot: Instância do bot Discord
        run_scan_once_func: Função de scan a ser injetada
    """
    await bot.add_cog(AdminCog(bot, run_scan_once_func))
