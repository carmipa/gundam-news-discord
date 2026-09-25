"""
Comandos globais só para o dono do bot, e varredura manual por uma porta única.

Achados da auditoria de 2026-09-25:
  - /clean_state apagava o dedup de TODAS as guilds e bastava ser admin de UMA;
  - /server_log mostrava o log do processo (usuários e canais de todas as guilds)
    a qualquer admin de guild;
  - /now e o botão "Verificar Agora" não tinham permissão nem intervalo mínimo;
  - o botão dizia "Verificação concluída!" antes de a varredura rodar;
  - o botão Atualizar do /server_log chamava `defer_update()`, que não existe.

Caso-controle de fronteira (A1): o sinal que levantava a suspeita é "tem
Administrador". Os testes separam o admin que NÃO é dono (recusado) do dono
(aceito), e o admin da guild (aceito no /now) do membro comum (recusado).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord import app_commands

import core.scanner.engine as engine
from bot.cogs.admin import AdminCog, _LogRefreshView
from bot.cogs.status import StatusCog, ScanButton
from bot.permissoes import SomenteDonoDoBot, _exigir_dono, MENSAGEM_SOMENTE_DONO
from bot.varredura_manual import texto_do_pedido


def _interacao(eh_dono: bool = False, admin: bool = False, is_owner_levanta: bool = False):
    it = MagicMock()
    if is_owner_levanta:
        it.client.is_owner = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=500), "falhou"))
    else:
        it.client.is_owner = AsyncMock(return_value=eh_dono)
    it.user = MagicMock(id=123)
    it.guild = MagicMock(id=999)
    it.permissions = discord.Permissions(administrator=admin)
    # spec da classe real: método que não existe no discord.py (como o antigo
    # `defer_update`) levanta AttributeError aqui, igual em produção.
    it.response = MagicMock(spec=discord.InteractionResponse)
    it.response.is_done.return_value = False
    it.response.send_message = AsyncMock()
    it.response.edit_message = AsyncMock()
    it.followup.send = AsyncMock()
    return it


def _checks_de(comando) -> list:
    return [getattr(c, "__name__", repr(c)) for c in comando.checks]


class TestSomenteDono:
    @pytest.mark.asyncio
    async def test_dono_passa(self):
        assert await _exigir_dono(_interacao(eh_dono=True)) is True

    @pytest.mark.asyncio
    async def test_admin_que_nao_e_dono_e_recusado(self):
        # Mesmo sinal que antes bastava (Administrador), agora insuficiente.
        with pytest.raises(SomenteDonoDoBot):
            await _exigir_dono(_interacao(eh_dono=False, admin=True))

    @pytest.mark.asyncio
    async def test_falha_ao_consultar_o_dono_nega(self):
        with pytest.raises(SomenteDonoDoBot):
            await _exigir_dono(_interacao(is_owner_levanta=True))

    def test_clean_state_e_server_log_usam_o_check_do_dono(self):
        for comando in (AdminCog.clean_state_cmd, AdminCog.server_log):
            nomes = _checks_de(comando)
            assert "_exigir_dono" in nomes, (comando.name, nomes)
            assert not any("has_permissions" in n or "predicate" in n for n in nomes), (comando.name, nomes)

    @pytest.mark.asyncio
    async def test_handler_do_clean_state_explica_a_recusa(self):
        it = _interacao()
        cog = AdminCog(bot=MagicMock(), pedir_varredura=MagicMock())
        await cog.clean_state_error(it, SomenteDonoDoBot("x"))
        it.response.send_message.assert_awaited_once()
        assert it.response.send_message.call_args[0][0] == MENSAGEM_SOMENTE_DONO

    @pytest.mark.asyncio
    async def test_handler_do_server_log_explica_a_recusa(self):
        it = _interacao()
        cog = AdminCog(bot=MagicMock(), pedir_varredura=MagicMock())
        await cog.server_log_error(it, SomenteDonoDoBot("x"))
        assert it.response.send_message.call_args[0][0] == MENSAGEM_SOMENTE_DONO


class TestBotaoAtualizarDoLog:
    @pytest.mark.asyncio
    async def test_atualizar_edita_a_mensagem_pela_propria_interacao(self, tmp_path):
        log_file = tmp_path / "bot.log"
        log_file.write_text("linha 1\nlinha 2\n", encoding="utf-8")
        view = _LogRefreshView(linhas=10, timeout=None)
        it = _interacao(eh_dono=True)
        with patch("bot.cogs.admin.LOG_FILE_PATH", str(log_file)):
            await view.refresh.callback(it)
        it.response.edit_message.assert_awaited_once()
        assert "linha 2" in it.response.edit_message.call_args.kwargs["content"]

    @pytest.mark.asyncio
    async def test_botao_atualizar_recusa_quem_nao_e_dono(self):
        view = _LogRefreshView(linhas=10, timeout=None)
        it = _interacao(eh_dono=False, admin=True)
        assert await view.interaction_check(it) is False
        assert it.response.send_message.call_args[0][0] == MENSAGEM_SOMENTE_DONO

    @pytest.mark.asyncio
    async def test_botao_atualizar_aceita_o_dono(self):
        view = _LogRefreshView(linhas=10, timeout=None)
        assert await view.interaction_check(_interacao(eh_dono=True)) is True


class TestNowEBotaoExigemAdmin:
    @pytest.mark.asyncio
    async def test_now_recusa_membro_sem_admin(self):
        (check,) = StatusCog.now.checks
        with pytest.raises(app_commands.MissingPermissions):
            check(_interacao(admin=False))

    @pytest.mark.asyncio
    async def test_now_aceita_admin(self):
        (check,) = StatusCog.now.checks
        assert check(_interacao(admin=True)) is True

    @pytest.mark.asyncio
    async def test_botao_recusa_membro_sem_admin_e_nao_pede_varredura(self):
        pedir = MagicMock(return_value=(engine.PEDIDO_INICIADO, 0))
        it = _interacao(admin=False)
        await ScanButton(pedir).scan_now.callback(it)
        pedir.assert_not_called()
        it.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_botao_de_admin_pede_e_nao_afirma_conclusao(self):
        pedir = MagicMock(return_value=(engine.PEDIDO_INICIADO, 0))
        it = _interacao(admin=True)
        await ScanButton(pedir).scan_now.callback(it)
        pedir.assert_called_once_with("manual_button")
        texto = it.response.send_message.call_args[0][0]
        assert "concluída" not in texto.lower()


class TestPortaUnicaDaVarreduraManual:
    @pytest.fixture(autouse=True)
    def _isolar(self, monkeypatch):
        chamadas = []

        async def varredura_falsa(bot, trigger="manual"):
            chamadas.append(trigger)

        monkeypatch.setattr(engine, "run_scan_once", varredura_falsa)
        monkeypatch.setattr(engine, "MANUAL_SCAN_COOLDOWN_SEC", 600.0)
        monkeypatch.setattr(engine, "_inicio_ultima_varredura", 0.0)
        self.chamadas = chamadas

    @pytest.mark.asyncio
    async def test_primeiro_pedido_inicia(self):
        assert engine.solicitar_varredura_manual(MagicMock(), "command_now", agora=1000.0) == (engine.PEDIDO_INICIADO, 0)
        await asyncio.sleep(0)
        assert self.chamadas == ["command_now"]

    @pytest.mark.asyncio
    async def test_segundo_pedido_logo_depois_aguarda(self):
        engine.solicitar_varredura_manual(MagicMock(), "command_now", agora=1000.0)
        resultado, segundos = engine.solicitar_varredura_manual(MagicMock(), "manual_button", agora=1060.0)
        assert resultado == engine.PEDIDO_AGUARDE
        assert segundos == 540
        await asyncio.sleep(0)
        assert self.chamadas == ["command_now"]

    @pytest.mark.asyncio
    async def test_no_limite_do_intervalo_volta_a_iniciar(self):
        engine.solicitar_varredura_manual(MagicMock(), "a", agora=1000.0)
        assert engine.solicitar_varredura_manual(MagicMock(), "b", agora=1599.0)[0] == engine.PEDIDO_AGUARDE
        assert engine.solicitar_varredura_manual(MagicMock(), "c", agora=1600.0)[0] == engine.PEDIDO_INICIADO

    @pytest.mark.asyncio
    async def test_varredura_em_andamento_nao_e_duplicada(self):
        async with engine.scan_lock:
            assert engine.solicitar_varredura_manual(MagicMock(), "x", agora=5000.0) == (engine.PEDIDO_EM_ANDAMENTO, 0)
        await asyncio.sleep(0)
        assert self.chamadas == []

    @pytest.mark.asyncio
    async def test_varredura_do_ciclo_tambem_conta_para_o_intervalo(self, monkeypatch):
        monkeypatch.setattr(engine.time, "monotonic", lambda: 2000.0)
        monkeypatch.setattr(engine, "load_config_cached", lambda default=None: {})
        # O ciclo marca o início dentro do lock; config vazio encerra logo depois.
        await _run_scan_real(MagicMock())
        assert engine.solicitar_varredura_manual(MagicMock(), "now", agora=2100.0)[0] == engine.PEDIDO_AGUARDE

    @pytest.mark.asyncio
    async def test_intervalo_zero_desliga(self, monkeypatch):
        monkeypatch.setattr(engine, "MANUAL_SCAN_COOLDOWN_SEC", 0.0)
        engine.solicitar_varredura_manual(MagicMock(), "a", agora=1000.0)
        assert engine.solicitar_varredura_manual(MagicMock(), "b", agora=1001.0)[0] == engine.PEDIDO_INICIADO


_RUN_SCAN_ORIGINAL = engine.run_scan_once


async def _run_scan_real(bot):
    await _RUN_SCAN_ORIGINAL(bot, trigger="loop")


class TestTextoDoPedido:
    def test_nenhum_resultado_afirma_conclusao(self):
        for r in (engine.PEDIDO_INICIADO, engine.PEDIDO_EM_ANDAMENTO, engine.PEDIDO_AGUARDE, "desconhecido"):
            assert "concluída" not in texto_do_pedido(r, 120).lower()

    def test_aguarde_diz_quanto_falta(self):
        assert "2 min" in texto_do_pedido(engine.PEDIDO_AGUARDE, 90)
