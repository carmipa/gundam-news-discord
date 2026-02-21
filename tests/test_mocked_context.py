"""
Teste de Contexto "Mockado" (equivalente a ContextLoads em outros stacks).

Permite que os testes subam sem conexão real ao Discord: carregar módulos e cogs
com mocks para discord.py, para que o GitHub Actions (e outros CI) rodem os testes
sem DISCORD_TOKEN. Projeto: Python + discord.py (não usa JDA/Spring).
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestContextLoadsWithoutDiscord:
    """Sistema sobe em ambiente de teste sem conexão real ao Discord."""

    def test_import_main_modules_without_token(self):
        """Importar módulos principais não deve exigir DISCORD_TOKEN ou conexão."""
        # Não definir TOKEN não deve quebrar imports
        import utils.storage
        import utils.cache
        import utils.security
        import core.filters
        import core.stats
        assert utils.storage.load_json_safe is not None
        assert utils.cache.load_http_state is not None

    def test_import_admin_cog_without_bot_connection(self):
        """AdminCog pode ser importado e instanciado com mocks (sem bot real)."""
        from bot.cogs.admin import AdminCog
        fake_bot = MagicMock()
        fake_scan = AsyncMock()
        cog = AdminCog(bot=fake_bot, run_scan_once_func=fake_scan)
        assert cog.bot is fake_bot
        assert cog.run_scan_once is fake_scan

    def test_import_info_cog_without_bot_connection(self):
        """InfoCog pode ser importado e instanciado com mock de bot."""
        from bot.cogs.info import InfoCog
        fake_bot = MagicMock()
        cog = InfoCog(fake_bot)
        assert cog.bot is fake_bot

    def test_import_dashboard_cog_without_bot_connection(self):
        """DashboardCog pode ser importado com mock."""
        from bot.cogs.dashboard import DashboardCog
        fake_bot = MagicMock()
        cog = DashboardCog(fake_bot)
        assert cog.bot is fake_bot

    def test_import_status_cog_without_bot_connection(self):
        """StatusCog pode ser importado com mock (requer run_scan_once)."""
        from bot.cogs.status import StatusCog
        fake_bot = MagicMock()
        cog = StatusCog(fake_bot, run_scan_once_func=AsyncMock())
        assert cog.bot is fake_bot

    def test_settings_loads_without_discord_token(self):
        """settings pode ser importado; TOKEN pode ser None em teste."""
        import settings
        assert hasattr(settings, "TOKEN")
        assert hasattr(settings, "HTTP_TIMEOUT")


class TestCommandLogicWithMockedInteraction:
    """Lógica de comando pode ser exercitada com Interaction mockada (sem conexão Discord real)."""

    @pytest.mark.asyncio
    async def test_clean_state_error_handler_with_mock_interaction(self):
        """Handler de erro do clean_state responde ao mock sem conexão real."""
        from discord import app_commands
        from bot.cogs.admin import AdminCog

        mock_interaction = MagicMock()
        mock_interaction.response.is_done.return_value = False
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        cog = AdminCog(bot=MagicMock(), run_scan_once_func=AsyncMock())
        error = app_commands.MissingPermissions(["administrator"])

        await cog.clean_state_error(mock_interaction, error)

        assert mock_interaction.response.send_message.called or mock_interaction.followup.send.called
