# Python 3.12: o 3.10 sai de suporte em outubro de 2026 (fim das correções de
# segurança). A suíte passa no 3.12 desde 2026-09-25, quando foi corrigido o teste
# que travava nele (wait_closed com conexão aberta).
FROM python:3.12-slim

# Metadata
LABEL maintainer="Paulo André Carminati"
LABEL description="Gundam News Discord Bot - Mafty Intelligence System"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Diretório de trabalho
WORKDIR /app

# Instala dependências do sistema (necessárias para certifi e SSL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements primeiro (melhor cache de layers). Só produção: pytest,
# flake8 e pip-audit ficam em requirements-dev.txt, fora da imagem.
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Usuário sem privilégio: o processo carrega o DISCORD_TOKEN, e uma falha
# explorável no bot não deve valer root dentro do contêiner.
#
# UID 1000 fixo porque os arquivos de estado são montados do host: no deploy,
# `chown 1000:1000` neles (ver docs/DEPLOY.md). Se esquecido, o bot RECUSA
# arrancar com mensagem clara (verificar_gravacao) em vez de rodar sem gravar
# o dedup e repostar tudo a cada ciclo.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin mafty

# Copia o código do projeto
COPY --chown=mafty:mafty . .

# /app também: a gravação atômica cria o temporário ao lado do arquivo de
# estado. Com /app de root (WORKDIR), nenhuma gravação passaria.
# Diretórios de dados persistentes (volumes)
RUN mkdir -p /app/data /app/logs && chown mafty:mafty /app && chown -R mafty:mafty /app/data /app/logs

USER mafty

# Healthcheck: o bot grava um batimento a cada 60s enquanto está conectado ao
# Discord; sem batimento há mais de 3 min, o contêiner fica `unhealthy`.
# (Antes só conferia se /app/config.json existia — verdadeiro com o bot mudo.)
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 \
    CMD ["python", "healthcheck.py"]

# Comando de execução
CMD ["python", "-u", "main.py"]
