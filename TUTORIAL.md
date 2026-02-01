# 🎮 Tutorial de Comandos - Gundam News Bot

Este guia explica como utilizar todos os comandos disponíveis no **Mafty Intelligence System**.

---

## 🔐 Comandos de Administrador

*Estes comandos exigem permissão de **Administrador** no servidor.*

### `/dashboard`

Abre o **Painel de Controle** interativo.
**Uso:** Digite `/dashboard` no canal onde deseja que o painel apareça (ele é visível apenas para você).

* **Funcionalidades:**
  * Ativar/Desativar filtros (Gunpla, Filmes, Games, etc).
  * **Botão TUDO:** Liga ou desliga todas as categorias.
  * **Trocar Idioma:** Clique nas bandeiras (🇺🇸, 🇧🇷, 🇪🇸, 🇮🇹, 🇯🇵) para alterar o idioma das notícias.
  * **Ver Filtros:** Mostra lista textual do que está ativo.
  * **Reset:** Limpa todas as configurações.

### `/forcecheck`

Força uma varredura **imediata** de todas as fontes de notícias.
**Uso:** `/forcecheck`

* Útil para testar se o bot está funcionando ou quando você sabe que saiu uma notícia urgente e não quer esperar o ciclo automático (30 min).

### `/setlang`

Define o idioma do bot para o servidor via comando (alternativa ao Dashboard).
**Uso:** `/setlang [idioma]`

* **Opções:** `en_US`, `pt_BR`, `es_ES`, `it_IT`, `ja_JP`.

---

## 🌍 Comandos Públicos

*Disponíveis para todos os usuários.*

### `/status`

Mostra um relatório completo de saúde do bot.
**Exibe:**

* Tempo online (Uptime).
* Uso de Memória e CPU.
* Total de notícias enviadas desde o reinício.
* Latência (Ping) da API do Discord.

### `/feeds`

Lista todas as fontes de onde o bot retira as notícias.

* Mostra Sites RSS, Canais do YouTube e Sites Oficiais monitorados.

### `/help`

Exibe o menu de ajuda rápida com a lista de comandos.

### `/about`

Mostra informações sobre o desenvolvimento do bot, versão e tecnologias usadas (Python/Discord.py).

### `/ping`

Testa a velocidade de resposta do bot em milissegundos.

---

## 💡 Dicas de Uso

1. **Vídeos no Chat:**
    O bot possui um player nativo! Links do YouTube e Twitch postados por ele podem ser assistidos diretamente dentro do Discord, sem abrir o navegador.

2. **Filtros Inteligentes:**
    O bot usa um sistema de "camadas". Se você notar que notícias gerais de anime (como One Piece) não aparecem, é porque o filtro **Anti-Spam** está funcionando corretamente, focando apenas no universo Gundam.

3. **Monitoramento Oficial:**
    Além de RSS, o bot "olha" visualmente sites oficiais (como o Gundam.info ou Bandai Hobby) para detectar novidades que não aparecem em feeds comuns.
