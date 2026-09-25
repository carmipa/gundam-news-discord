"""
Batimento do processo para o HEALTHCHECK do Docker.

O healthcheck anterior só conferia se `/app/config.json` existia — verdadeiro com
o bot desconectado, travado ou morto por dentro, e até quando o Docker criava um
DIRETÓRIO no lugar do arquivo ausente. O contêiner aparecia `healthy` mudo.

Não importa discord: o script de healthcheck roda num processo Python separado
e precisa subir rápido e sem dependências pesadas.
"""
import os
import tempfile
import time
from typing import Optional

IDADE_MAXIMA_SEC = 180.0


def caminho_heartbeat() -> str:
    """Arquivo do batimento. Fora dos volumes: é estado do processo, não do bot."""
    return os.getenv("HEARTBEAT_FILE") or os.path.join(tempfile.gettempdir(), "mafty-heartbeat")


def registrar_batimento(conectado: bool, agora: Optional[float] = None) -> bool:
    """
    Marca o processo como vivo — só quando está conectado ao Discord.

    PROPÓSITO DE NEGÓCIO:
        O Docker precisa distinguir "processo rodando" de "bot funcionando".

    INVARIANTES DO DOMÍNIO:
        - Desconectado não bate: o arquivo envelhece e o healthcheck reprova.
        - Quem chama é um loop no event loop do bot; loop travado também deixa
          de bater — o que é exatamente o sinal desejado.

    COMPORTAMENTO EM CASO DE FALHA:
        Erro de disco devolve False sem levantar (o healthcheck reprovará).
    """
    if not conectado:
        return False
    agora = time.time() if agora is None else agora
    try:
        with open(caminho_heartbeat(), "w", encoding="utf-8") as f:
            f.write(f"{agora:.0f}\n")
        os.utime(caminho_heartbeat(), (agora, agora))
        return True
    except OSError:
        return False


def batimento_recente(idade_maxima: float = IDADE_MAXIMA_SEC, agora: Optional[float] = None) -> bool:
    """True se houve batimento há no máximo `idade_maxima` segundos."""
    agora = time.time() if agora is None else agora
    try:
        return (agora - os.path.getmtime(caminho_heartbeat())) <= idade_maxima
    except OSError:
        return False
