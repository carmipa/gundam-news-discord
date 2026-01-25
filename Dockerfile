FROM python:3.10-slim

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

# Copia requirements primeiro (melhor cache de layers)
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia código do bot
# Copia todo o código do projeto
COPY . .

# Cria diretórios para dados persistentes (serão volumes)
RUN mkdir -p /app/data /app/logs

# Healthcheck (verifica se bot está rodando e se config existe)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('/app/config.json') else 1)"

# Comando de execução
CMD ["python", "-u", "main.py"]
