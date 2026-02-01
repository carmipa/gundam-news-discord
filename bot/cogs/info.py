"""
Info cog - Informational commands (/help, /about, /feeds, /ping, /setlang).
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging

from core.stats import stats
from core.scanner import load_sources
from utils.translator import t
from utils.storage import p, load_json_safe, save_json_safe

log = logging.getLogger("MaftyIntel")


class InfoCog(commands.Cog):
    """Cog com comandos informativos e de idioma."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="ping", description="Verifica a latência do bot.")
    async def ping(self, interaction: discord.Interaction):
        # Detecta idioma
        lang = t.detect_lang(str(interaction.guild_id), interaction.guild_locale)
        latency = round(self.bot.latency * 1000)
        
        msg = t.get('commands.ping.response', lang=lang, latency=latency)
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="about", description="Sobre o Mafty Intelligence System.")
    async def about(self, interaction: discord.Interaction):
        lang = t.detect_lang(str(interaction.guild_id), interaction.guild_locale)
        
        embed = discord.Embed(
            title=t.get('bot.name', lang=lang),
            description=t.get('commands.about.description', lang=lang),
            color=discord.Color.from_rgb(255, 0, 32)
        )
        
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        
        embed.add_field(name=t.get('commands.about.developer', lang=lang), value="Paulo André Carminati", inline=False)
        embed.add_field(name=t.get('commands.about.stack', lang=lang), value="Python 3.10 • Discord.py • Docker", inline=True)
        embed.add_field(name=t.get('commands.about.version', lang=lang), value="v2.1 (Multi-lang)", inline=True)
        
        embed.set_footer(text=t.get('commands.about.footer', lang=lang))
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setlang", description="Define o idioma do bot para este servidor.")
    @app_commands.describe(idioma="Escolha: en_US, pt_BR, es_ES, it_IT")
    @app_commands.choices(idioma=[
        app_commands.Choice(name="🇺🇸 English", value="en_US"),
        app_commands.Choice(name="🇧🇷 Português", value="pt_BR"),
        app_commands.Choice(name="🇪🇸 Español", value="es_ES"),
        app_commands.Choice(name="🇮🇹 Italiano", value="it_IT"),
        app_commands.Choice(name="🇯🇵 日本語", value="ja_JP")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def setlang(self, interaction: discord.Interaction, idioma: str):
        """Define o idioma do servidor."""
        gid = str(interaction.guild_id)
        
        # Salva na config
        cfg = load_json_safe(p("config.json"), {})
        if gid not in cfg: cfg[gid] = {}
        
        cfg[gid]["language"] = idioma
        save_json_safe(p("config.json"), cfg)
        
        msgs = {
            "pt_BR": "✅ Idioma alterado para **Português**.",
            "en_US": "✅ Language set to **English**.",
            "es_ES": "✅ Idioma cambiado a **Español**.",
            "it_IT": "✅ Lingua impostata su **Italiano**."
        }
        
        await interaction.response.send_message(msgs.get(idioma, "✅ Language updated."), ephemeral=True)

    @app_commands.command(name="feeds", description="Lista todos os feeds monitorados.")
    async def feeds(self, interaction: discord.Interaction):
        lang = t.detect_lang(str(interaction.guild_id), interaction.guild_locale)
        urls = load_sources()
        total = len(urls)
        
        display_urls = urls[:15]
        remaining = total - 15
        
        lista = "\n".join(f"• <{u}>" for u in display_urls)
        if remaining > 0:
            lista += t.get('commands.feeds.more', lang=lang, count=remaining)
            
        embed = discord.Embed(
            title=t.get('commands.feeds.title', lang=lang, total=total),
            description=lista,
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Mostra a lista de comandos disponíveis.")
    async def help_cmd(self, interaction: discord.Interaction):
        lang = t.detect_lang(str(interaction.guild_id), interaction.guild_locale)
        
        embed = discord.Embed(
            title=t.get('commands.help.title', lang=lang),
            color=discord.Color.gold()
        )
        
        keys = ['dashboard', 'forcecheck', 'status', 'feeds', 'about', 'ping']
        vals = {k: t.get(f'commands.help.{k}', lang=lang) for k in keys}
        
        embed.add_field(
            name=t.get('commands.help.config', lang=lang),
            value=f"{vals['dashboard']}\n{vals['forcecheck']}",
            inline=False
        )
        
        embed.add_field(
            name=t.get('commands.help.info', lang=lang),
            value=f"{vals['status']}\n{vals['feeds']}\n{vals['about']}\n{vals['ping']}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(InfoCog(bot))
