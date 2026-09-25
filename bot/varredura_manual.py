"""
Texto que o usuário lê depois de pedir uma varredura manual.
"""
from core.scanner import PEDIDO_INICIADO, PEDIDO_EM_ANDAMENTO, PEDIDO_AGUARDE


def texto_do_pedido(resultado: str, segundos: int) -> str:
    """
    Traduz o resultado de `solicitar_varredura_manual` para a mensagem da interface.

    PROPÓSITO DE NEGÓCIO:
        Quem clica precisa saber o que de fato aconteceu. Antes, o botão dizia
        "Verificação concluída!" no instante em que a tarefa era criada — antes de
        a varredura rodar — e o usuário concluía que não havia notícia nova.

    INVARIANTES DO DOMÍNIO:
        - Nunca afirma conclusão: a varredura roda em segundo plano, e o que ela
          publicar chega ao canal configurado.
        - Recusa diz o motivo e quanto falta, para ninguém clicar de novo às cegas.

    COMPORTAMENTO EM CASO DE FALHA:
        Resultado desconhecido devolve mensagem neutra, sem afirmar que iniciou.
    """
    if resultado == PEDIDO_INICIADO:
        return (
            "🔎 Varredura iniciada em segundo plano. "
            "Se houver notícias novas, elas chegam ao canal configurado em alguns minutos."
        )
    if resultado == PEDIDO_EM_ANDAMENTO:
        return "⏳ Já existe uma varredura em andamento. O que ela encontrar chega ao canal configurado."
    if resultado == PEDIDO_AGUARDE:
        minutos = max(1, (segundos + 59) // 60)
        return (
            f"🕐 Uma varredura rodou há pouco. A próxima manual fica disponível em ~{minutos} min "
            "(a varredura é única para todos os servidores e respeita os limites das fontes)."
        )
    return "⚠️ Não foi possível confirmar o pedido de varredura. Tente novamente mais tarde."
