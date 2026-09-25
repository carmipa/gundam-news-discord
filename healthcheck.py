"""
HEALTHCHECK do contêiner: sai 0 se o bot bateu nos últimos 3 minutos, 1 se não.
"""
import sys

from utils.heartbeat import batimento_recente

if __name__ == "__main__":
    sys.exit(0 if batimento_recente() else 1)
