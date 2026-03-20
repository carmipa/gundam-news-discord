# Instalação

[Voltar ao índice da documentação](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README.md)

---

## Pré-requisitos

- Python 3.10 ou superior
- Token de bot do Discord ([Portal de Desenvolvedores](https://discord.com/developers/applications))
- Git (para clonar o repositório)

## Passo a passo (ambiente local)

```bash
# 1. Clone o repositório
git clone https://github.com/carmipa/gundam-news-discord.git
cd gundam-news-discord

# 2. Crie ambiente virtual
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

# 3. Instale dependências
pip install -r requirements.txt

# 4. Configure o ambiente
cp .env.example .env
# Edite o .env com seu token
```

## Instalação com Docker (recomendado)

```bash
git clone https://github.com/carmipa/gundam-news-discord.git
cd gundam-news-discord

cp .env.example .env
nano .env  # Adicione seu DISCORD_TOKEN

docker-compose up -d
docker-compose logs -f
```

**Deploy detalhado:** [DEPLOY.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/DEPLOY.md)

---

**Próximo passo:** [Configuração](https://github.com/carmipa/gundam-news-discord/blob/main/docs/CONFIGURATION.md) · [Comandos](https://github.com/carmipa/gundam-news-discord/blob/main/docs/COMMANDS_LIST.md)
