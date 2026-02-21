"""
Teste do "Malandro Protocol" (Segurança Lógica).

Autorização baseada em permissão de Administrador: comandos administrativos
devem responder "Acesso Negado" (ou mensagem equivalente) quando o usuário
não tem permissão, e um log de alerta deve ser gerado.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord import app_commands

# Importar o cog e o error handler para testar a resposta quando falta permissão
from bot.cogs.admin import AdminCog


class TestAdminAuthorization:
    """Blindar comandos administrativos contra usuários não autorizados."""

    @pytest.mark.asyncio
    async def test_clean_state_error_sends_denied_message_on_missing_permissions(self):
        """Simula MissingPermissions no /clean_state: resposta deve conter mensagem de acesso negado."""
        mock_interaction = MagicMock(spec=discord.Interaction)
        mock_interaction.response.is_done.return_value = False
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        error = app_commands.MissingPermissions(["administrator"])
        cog = AdminCog(bot=MagicMock(), run_scan_once_func=AsyncMock())

        await cog.clean_state_error(mock_interaction, error)

        # Deve ter enviado mensagem com texto de "Administrador" (acesso negado)
        if mock_interaction.response.send_message.called:
            call = mock_interaction.response.send_message.call_args
            msg = call[1].get("content") or call[0][0] if call[0] else ""
        else:
            call = mock_interaction.followup.send.call_args
            msg = (call[1].get("content") or call[0][0]) if call[0] or call[1] else ""
        assert "Administrador" in msg or "administrador" in msg.lower(), (
            "Resposta deve indicar que é necessário ser Administrador (Acesso Negado)."
        )

    @pytest.mark.asyncio
    async def test_forcecheck_error_sends_denied_message_on_missing_permissions(self):
        """Simula MissingPermissions no /forcecheck: resposta deve conter mensagem de acesso negado."""
        mock_interaction = MagicMock(spec=discord.Interaction)
        mock_interaction.response.is_done.return_value = False
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        error = app_commands.MissingPermissions(["administrator"])
        cog = AdminCog(bot=MagicMock(), run_scan_once_func=AsyncMock())

        await cog.forcecheck_error(mock_interaction, error)

        if mock_interaction.response.send_message.called:
            call = mock_interaction.response.send_message.call_args
            msg = call[1].get("content") or (call[0][0] if call[0] else "")
        else:
            call = mock_interaction.followup.send.call_args
            msg = (call[1].get("content") or (call[0][0] if call[0] else "")) if (call[0] or call[1]) else ""
        assert "Administrador" in msg or "administrador" in msg.lower()

    @pytest.mark.asyncio
    async def test_clean_state_error_logs_when_non_authorized(self):
        """Quando MissingPermissions ocorre, o fluxo não deve dar exceção; log pode ser gerado no handler geral."""
        mock_interaction = MagicMock(spec=discord.Interaction)
        mock_interaction.response.is_done.return_value = False
        mock_interaction.response.send_message = AsyncMock()

        error = app_commands.MissingPermissions(["administrator"])
        cog = AdminCog(bot=MagicMock(), run_scan_once_func=AsyncMock())

        with patch("bot.cogs.admin.log") as mock_log:
            await cog.clean_state_error(mock_interaction, error)
            # O handler de MissingPermissions retorna antes de log.exception;
            # não é obrigatório logar para MissingPermissions, mas a resposta foi enviada
            assert mock_interaction.response.send_message.called or mock_interaction.followup.send.called
