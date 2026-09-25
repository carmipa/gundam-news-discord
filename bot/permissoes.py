"""
Permissões dos comandos que afetam o bot inteiro, e não só a guild de quem chama.

Um admin de guild manda na SUA guild. Operações cujo efeito atravessa todas as
guilds — apagar o dedup global, ler o log do processo — pertencem ao dono do bot.
"""
import logging

import discord
from discord import app_commands

log = logging.getLogger("MaftyIntel")


class SomenteDonoDoBot(app_commands.CheckFailure):
    """O comando é global e quem chamou não é o dono da aplicação."""


async def _exigir_dono(interaction: discord.Interaction) -> bool:
    """
    Check de app_commands que só deixa passar o dono da aplicação no Discord.

    PROPÓSITO DE NEGÓCIO:
        O bot atende várias guilds com um único estado (dedup, history, log).
        Ser administrador de UMA guild não pode dar poder sobre as outras.

    INVARIANTES DO DOMÍNIO:
        - A identidade do dono vem do Discord (`Bot.is_owner`, que consulta a
          aplicação ou a equipe), nunca de configuração editável por guild.
        - Falha fechada: qualquer erro ao determinar o dono NEGA o acesso.

    COMPORTAMENTO EM CASO DE FALHA:
        Levanta `SomenteDonoDoBot` (subclasse de CheckFailure) quando o usuário
        não é o dono ou quando não foi possível verificar — o handler de erro do
        comando responde com a recusa. Nunca devolve False em silêncio.
    """
    try:
        eh_dono = await interaction.client.is_owner(interaction.user)
    except Exception as e:
        log.error(f"Não foi possível verificar o dono do bot ({type(e).__name__}: {e}). Acesso negado.")
        raise SomenteDonoDoBot("não foi possível verificar o dono do bot") from e
    if not eh_dono:
        guild_id = interaction.guild.id if interaction.guild else "DM"
        log.warning(
            f"[AUDIT] ACESSO_NEGADO_DONO | User: {interaction.user} (ID: {interaction.user.id}) | "
            f"Guild: {guild_id} | Comando: /{interaction.command.name if interaction.command else '?'}"
        )
        raise SomenteDonoDoBot("comando restrito ao dono do bot")
    return True


def somente_dono():
    """Decorador de app_commands: restringe o comando ao dono do bot."""
    return app_commands.check(_exigir_dono)


MENSAGEM_SOMENTE_DONO = (
    "❌ Este comando afeta **todos os servidores** onde o bot está e é restrito ao **dono do bot**."
)
MENSAGEM_SOMENTE_ADMIN = "❌ Você precisa ter **Administrador** para usar este comando."


async def responder_recusa(interaction: discord.Interaction, mensagem: str) -> None:
    """
    Envia a recusa de acesso de forma efêmera, pela via que ainda estiver aberta.

    PROPÓSITO DE NEGÓCIO:
        Quem foi recusado precisa ler o motivo; uma interação sem resposta vira
        "Esta interação falhou", que não diz nada.

    INVARIANTES DO DOMÍNIO:
        - A recusa é sempre efêmera: não expõe a tentativa ao canal.

    COMPORTAMENTO EM CASO DE FALHA:
        Interação expirada ou erro HTTP é registrado em log e engolido — a recusa
        já aconteceu no check; falhar ao avisar não pode virar exceção nova.
    """
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(mensagem, ephemeral=True)
        else:
            await interaction.followup.send(mensagem, ephemeral=True)
    except discord.NotFound:
        log.debug("Interação expirada ao enviar recusa de acesso.")
    except Exception as e:
        log.warning(f"Falha ao enviar recusa de acesso: {type(e).__name__}: {e}")
