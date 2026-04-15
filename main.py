# =========================================================
# Gundam Intel Bot - "Mafty Sovereign" v2.1
# main.py (Modularized)
# =========================================================
"""
Ponto de entrada do bot Discord.
- Carrega config, inicia web server, registra views e cogs.
- Sobe o agendador de varreduras e, ao detectar novo commit, envia anúncio de atualização.
- Exceções de libs (discord, aiohttp) não são convertidas; erros do domínio podem usar utils.exceptions.
"""
import logging
import asyncio
from datetime import datetime
import discord
from discord.ext import commands

from settings import TOKEN, COMMAND_PREFIX, LOG_LEVEL
from utils.storage import p, load_json_safe
from bot.views.filter_dashboard import FilterDashboard
from core.scanner import start_scheduler, run_scan_once
from web.server import start_web_server  # Novo web server
from utils.git_info import get_git_changes, get_current_hash, get_commits_since
from utils.storage import save_json_safe

# Configuração de Logs
from utils.logger import setup_logger

# Configura o logger global com rotação de arquivos e cores no console
log = setup_logger(name="MaftyIntel", log_file="logs/bot.log", level=LOG_LEVEL)


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

    @bot.event
    async def on_interaction(interaction: discord.Interaction):
        """Registra no log todo uso de comando (slash) para acompanhamento."""
        if interaction.type != discord.InteractionType.application_command:
            return
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        command_name = interaction.command.name if interaction.command else "?"
        guild_id = interaction.guild.id if interaction.guild else "DM"
        user = interaction.user
        options = interaction.data.get("options", []) if interaction.data else []
        parts = []
        for o in options:
            if isinstance(o, dict):
                name = o.get("name", "")
                val = o.get("value", "")
                parts.append(f"{name}={val}" if name else str(val))
        opts_str = " ".join(parts)
        log.info(
            f"📌 [{now_str}] Comando: /{command_name} | por {user} (ID: {user.id}) | Guild: {guild_id}"
            + (f" | {opts_str}" if opts_str.strip() else "")
        )

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
        except discord.HTTPException as e:
            log.error(f"Erro HTTP ao sincronizar comandos: {e.status} - {e.text}")
            await ctx.send(f"❌ Erro HTTP ao sincronizar: {e.status}")
        except Exception as e:
            log.exception(f"Erro ao sincronizar comandos: {type(e).__name__}: {e}")
            await ctx.send(f"❌ Erro ao sincronizar: {type(e).__name__}")

    @bot.event
    async def on_ready():
        log.info(f"✅ Bot conectado como: {bot.user} (ID: {bot.user.id})")
        log.info(f"📊 Servidores conectados: {len(bot.guilds)}")

        # 0. Iniciar Web Server (Fase 10)
        # Host e porta agora vêm de variáveis de ambiente (padrão: 127.0.0.1:8080)
        await start_web_server()

        # 1. Carregar Views Persistentes
        cfg = load_json_safe(p("config.json"), {})
        if isinstance(cfg, dict):
            for gid in cfg.keys():
                try:
                    bot.add_view(FilterDashboard(int(gid)))
                    log.info(f"View persistente registrada para guild {gid}")
                except ValueError as e:
                    log.error(f"Erro ao converter guild_id '{gid}' para inteiro: {e}")
                except Exception as e:
                    log.error(f"Erro ao registrar view persistente para guild {gid}: {type(e).__name__}: {e}", exc_info=True)

            # Valida canais configurados: avisa se algum canal não existe (ex.: foi deletado)
            cfg_changed = False
            for gid, gdata in list(cfg.items()):
                if not isinstance(gdata, dict): continue
                channel_id = gdata.get("channel_id")
                if not channel_id: continue
                try:
                    ch = bot.get_channel(int(channel_id))
                    if ch is None:
                        guild_name = ""
                        try:
                            g = bot.get_guild(int(gid))
                            if g:
                                guild_name = f" (servidor: {g.name})"
                        except (ValueError, TypeError):
                            pass
                        log.warning(
                            f"⚠️ Canal configurado não encontrado ao iniciar: channel_id {channel_id}, Guild {gid}{guild_name}. "
                            "Removendo do config para evitar falhas."
                        )
                        gdata["channel_id"] = None
                        cfg_changed = True
                except (ValueError, TypeError):
                    pass
                    
            if cfg_changed:
                save_json_safe(p("config.json"), cfg)

        # 2. Sync Comandos (Slash)
        try:
            # Sincroniza global (pode demorar) ou por guild
            # Para dev, sync por guild é mais rápido e garante update imediato
            # IMPORTANTE: É necessário copiar os globais para a guild antes de syncar a guild
            for guild in bot.guilds:
                bot.tree.copy_global_to(guild=discord.Object(id=guild.id))
                await bot.tree.sync(guild=discord.Object(id=guild.id))
                log.info(f"Comandos sincronizados (copy_global) em: {guild.name}")
        except discord.HTTPException as e:
            log.error(f"Erro HTTP no sync de comandos: {e.status} - {e.text}")
        except Exception as e:
            log.exception(f"Falha no sync de comandos: {type(e).__name__}: {e}")

        # 3. Iniciar Loop de Scanner
        start_scheduler(bot)

        # 4. Anúncio de Versão (Git Check)
        try:
            current_hash = get_current_hash()
            state_file = p("state.json")
            state = load_json_safe(state_file, {})
            last_hash = state.get("last_announced_hash")

            if current_hash:
                # Texto do(s) último(s) commit(s) como "o que foi feito" nesta atualização
                # Como o usuário pediu para anunciar a cada reinício, mostramos sempre as últimas alterações.
                commits = get_commits_since(last_hash if current_hash != last_hash else None, max_commits=1)
                changes_block = "\n".join(f"• {c}" for c in commits)
                if len(changes_block) > 3800:
                    changes_block = changes_block[:3797] + "..."
                repo_url = "https://github.com/carmipa/gundam-news-discord"
                description = (
                    f"**Última atualização/correção aplicada:**\n{changes_block}\n\n"
                    f"**Repository:** [github.com/carmipa/gundam-news-discord]({repo_url})"
                )

                now = datetime.now()
                date_str = now.strftime("%Y.%m.%d")
                time_str = now.strftime("%H:%M")
                # Alerta: atualização do sistema (deploy) — 🔄 📦 teal RGB(26,188,156)
                UPDATE_COLOR = discord.Color.from_rgb(26, 188, 156)
                embed = discord.Embed(
                    title=f"🔄 📦 System update — {date_str}",
                    description=description,
                    color=UPDATE_COLOR
                )
                embed.set_author(
                    name="🔄 Stability update",
                    icon_url=bot.user.display_avatar.url if bot.user and bot.user.display_avatar else None
                )
                embed.set_footer(text=f"🔄 Update applied | Deploy: {time_str} BRT")

                # Envia para TODOS os canais configurados (cada servidor vê o anúncio)
                sent = 0
                if isinstance(cfg, dict):
                    for gid, gdata in cfg.items():
                        if not isinstance(gdata, dict):
                            continue
                        ch_id = gdata.get("channel_id")
                        if not ch_id:
                            continue
                        ch = bot.get_channel(int(ch_id))
                        if ch:
                            try:
                                await ch.send(embed=embed)
                                sent += 1
                                log.info(f"📢 Anúncio de atualização enviado ao canal {ch.name} (Guild {gid})")
                            except Exception as e:
                                log.warning(f"Falha ao enviar anúncio no canal {ch_id}: {e}")

                if sent > 0:
                    state["last_announced_hash"] = current_hash
                    save_json_safe(state_file, state)
                    log.info(f"📢 Atualização {current_hash} anunciada em {sent} canal(is).")
                else:
                    log.warning("⚠️ Erro ao encontrar canais para anunciar o reinício/atualização do bot.")
            else:
                log.info("ℹ️ Não foi possível obter o hash do Git para anúncio.")

        except Exception as e:
            log.exception(f"❌ Falha ao processar anúncio de versão: {type(e).__name__}: {e}")

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
