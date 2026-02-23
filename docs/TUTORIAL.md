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

* Útil para testar se o bot está funcionando ou quando você sabe que saiu uma notícia urgente e não quer esperar o ciclo automático (ex.: 12h).

### `/set_canal`

Define o canal onde o bot enviará notícias.
**Uso:** `/set_canal [canal:#noticias]`

* Se não especificar canal, usa o canal atual
* Verifica permissões do bot automaticamente
* Mais rápido que `/dashboard` para apenas configurar canal

**Exemplo:**
```
/set_canal                    # Usa o canal atual
/set_canal canal:#noticias    # Define canal específico
```

### `/setlang`

Define o idioma do bot para o servidor via comando (alternativa ao Dashboard).
**Uso:** `/setlang [idioma]`

* **Opções:** `en_US`, `pt_BR`, `es_ES`, `it_IT`, `ja_JP`.

### `/clean_state`

Limpa partes específicas do `state.json` com backup automático.
**Uso:** `/clean_state tipo:[tipo] confirmar:[sim/não]`

* **⚠️ Requer confirmação explícita** (`confirmar:sim`)
* **Cria backup automático** antes de limpar
* **Mostra estatísticas** antes e depois da limpeza

**Tipos de Limpeza:**
- 🧹 **dedup** - Histórico de links enviados (⚠️ pode causar repostagem)
- 🌐 **http_cache** - Cache HTTP (ETags) - seguro
- 🔍 **html_hashes** - Hashes de monitoramento HTML (⚠️ pode causar re-detecção)
- ⚠️ **tudo** - Limpa tudo (🚨 use apenas em emergências)

**Exemplo:**
```
# Passo 1: Ver estatísticas
/clean_state tipo:dedup confirmar:não

# Passo 2: Confirmar limpeza
/clean_state tipo:dedup confirmar:sim
```

**⚠️ Atenção:** Limpar `dedup` fará o bot repostar notícias já enviadas!

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
