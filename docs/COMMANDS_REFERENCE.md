# 📚 Referência Completa de Comandos — Gundam News Bot

[![Versão](https://img.shields.io/badge/Versão-2.1_Mafty_Sovereign-blue)](../readme.md)
[![Discord](https://img.shields.io/badge/Discord-Bot-5865F2?logo=discord&logoColor=white)](https://discord.com)
[![Admin](https://img.shields.io/badge/Comandos-Admin%20%7C%20Público-orange)](COMMANDS_LIST.md)

**Versão:** 2.1 "Mafty Sovereign"  
**Última Atualização:** Fevereiro 2026

| 📋 [Lista rápida de comandos](COMMANDS_LIST.md) | 🧹 [Tutorial /clean_state](TUTORIAL_CLEAN_STATE.md) |
|-------------------------------------------------|-----------------------------------------------------|

---

## 📋 Índice

- [🔧 Comandos Administrativos](#-comandos-administrativos)
- [📊 Comandos Informativos](#-comandos-informativos)
- [📖 Guia de Uso Detalhado](#-guia-de-uso-detalhado)

---

## 🔧 Comandos Administrativos

> **⚠️ Requerem permissão de Administrador no servidor Discord**

### `/set_canal`

**Descrição:** Define o canal onde o bot enviará notícias de Gundam.

**Sintaxe:**
```
/set_canal [canal:#noticias]
```

**Parâmetros:**
- `canal` (opcional): Canal de texto onde as notícias serão enviadas
  - Se não especificado, usa o canal atual

**Exemplos:**
```
/set_canal                    # Usa o canal atual
/set_canal canal:#noticias    # Define canal específico
```

**Validações:**
- ✅ Verifica se o canal é de texto
- ✅ Verifica permissões do bot (Enviar Mensagens, Incorporar Links)
- ✅ Mostra avisos se faltar permissão

**Resposta:**
- ✅ Confirmação com canal configurado
- ⚠️ Aviso se faltar permissão
- ❌ Erro se canal inválido

---

### `/dashboard`

**Descrição:** Abre painel visual interativo para configurar filtros e idioma.

**Sintaxe:**
```
/dashboard
```

**Funcionalidades:**
- 🎛️ Configura filtros por categoria (Gunpla, Filmes, Games, etc.)
- 🌐 Seleciona idioma (🇺🇸 🇧🇷 🇪🇸 🇮🇹 🇯🇵)
- 📌 Visualiza filtros ativos
- 🔄 Reseta configurações
- ⚙️ Configura o canal automaticamente

**Botões Disponíveis:**
- 🌟 **TUDO** - Liga/desliga todas as categorias
- 🤖 **Gunpla** - Kits, P-Bandai, Ver.Ka
- 🎬 **Filmes** - Anime, trailers, séries
- 🎮 **Games** - Jogos Gundam
- 🎵 **Música** - OST, álbuns
- 👕 **Fashion** - Roupas e merchandise
- 🌐 **Idioma** - Seleção de idioma
- 📌 **Ver filtros** - Lista filtros ativos
- 🔄 **Reset** - Limpa todos os filtros

**Nota:** O painel é **persistente** - funciona mesmo após restart do bot!

---

### `/setlang`

**Descrição:** Define o idioma do bot para o servidor.

**Sintaxe:**
```
/setlang idioma:[código]
```

**Parâmetros:**
- `idioma` (obrigatório): Código do idioma
  - `en_US` - 🇺🇸 English
  - `pt_BR` - 🇧🇷 Português
  - `es_ES` - 🇪🇸 Español
  - `it_IT` - 🇮🇹 Italiano
  - `ja_JP` - 🇯🇵 日本語

**Exemplos:**
```
/setlang idioma:pt_BR    # Português
/setlang idioma:en_US    # Inglês
/setlang idioma:ja_JP    # Japonês
```

**Resposta:**
- ✅ Confirmação com idioma configurado

---

### `/forcecheck`

**Descrição:** Força uma varredura imediata de todos os feeds.

**Sintaxe:**
```
/forcecheck
```

**Uso:**
- Útil para testar se o bot está funcionando
- Quando você sabe que saiu uma notícia urgente
- Não quer esperar o ciclo automático (ex.: 12h)

**Resposta:**
- ✅ Confirmação quando varredura concluída
- ❌ Erro se falhar

**Nota:** Respeita o lock de varredura - se já houver uma em execução, ignora.

---

### `/server_log`

**Descrição:** Exibe as últimas linhas do log do servidor (o mesmo que aparece ao rodar o bot, ex.: `docker-compose logs -f`). Apenas administradores.

**Sintaxe:**
```
/server_log [linhas:50]
```

**Parâmetros:**
- `linhas` (opcional): Número de linhas a exibir (10 a 100, padrão 50).

**Uso:**
- Ver em tempo quase real o que o bot está logando (varreduras, erros, avisos).
- Clicar em **Atualizar** na mensagem para renovar com as linhas mais recentes.

**Resposta:**
- 📋 Mensagem com as últimas N linhas em bloco de código `log`.
- Botão **Atualizar** para recarregar sem rodar o comando de novo.

**Nota:** Requer permissão de **Administrador**. O arquivo lido é `logs/bot.log` (no Docker: volume `./logs:/app/logs`).

---

### `/clean_state`

**Descrição:** Limpa partes específicas do `state.json` com backup automático.

> 📘 **Tutorial completo com diagramas:** [TUTORIAL_CLEAN_STATE.md](TUTORIAL_CLEAN_STATE.md)

**Sintaxe:**
```
/clean_state tipo:[tipo] confirmar:[sim/não]
```

**Parâmetros:**
- `tipo` (obrigatório): Tipo de limpeza
  - `dedup` - 🧹 Histórico de links enviados
  - `http_cache` - 🌐 Cache HTTP (ETags)
  - `html_hashes` - 🔍 Hashes de monitoramento HTML
  - `tudo` - ⚠️ Limpa tudo (use com cuidado!)
- `confirmar` (opcional): Confirmação explícita
  - `sim`, `yes`, `s`, `y`, `confirmar`, `confirm` - Confirma
  - Qualquer outro valor - Mostra estatísticas e pede confirmação

**Fluxo de Uso:**

**Passo 1 - Ver Estatísticas:**
```
/clean_state tipo:dedup confirmar:não
```
Mostra estatísticas atuais e pede confirmação.

**Passo 2 - Confirmar Limpeza:**
```
/clean_state tipo:dedup confirmar:sim
```
Executa limpeza após criar backup.

**Opções de Limpeza:**

| Tipo | O que Limpa | Impacto | Quando Usar |
|------|-------------|---------|-------------|
| 🧹 **dedup** | Histórico de links enviados | ⚠️ Bot repostará notícias recentes | Histórico corrompido |
| 🌐 **http_cache** | Cache HTTP (ETags, Last-Modified) | ℹ️ Mais requisições HTTP | Feeds não atualizam |
| 🔍 **html_hashes** | Hashes de monitoramento HTML | ⚠️ Sites detectados como "mudados" | Monitor HTML não funciona |
| ⚠️ **tudo** | Limpa tudo (exceto metadados) | 🚨 Todos os efeitos acima | Apenas em emergências |

**Proteções:**
- ✅ Backup automático antes de limpar
- ✅ Se backup falhar, limpeza é cancelada
- ✅ Confirmação dupla obrigatória
- ✅ Estatísticas antes/depois
- ✅ Logging de auditoria completo

**Exemplo Completo:**
```
# 1. Ver estatísticas
/clean_state tipo:dedup confirmar:não

Resposta:
🧹 Limpeza do state.json
Tipo selecionado: 🧹 Dedup (Histórico de links enviados)
⚠️ ATENÇÃO: Isso fará o bot repostar notícias já enviadas!

📊 Estatísticas Atuais:
Dedup: 15 feeds, 1.234 links
HTTP Cache: 33 URLs
HTML Hashes: 8 sites
Tamanho: 245.3 KB

✅ Para Confirmar
Use /clean_state tipo:dedup confirmar:sim

# 2. Confirmar
/clean_state tipo:dedup confirmar:sim

Resposta:
✅ Limpeza Concluída
Tipo: 🧹 Dedup (Histórico de links)
Backup criado: state_backup_20260213_152630.json

📊 Antes          📊 Depois
Dedup: 1234      Dedup: 0
HTTP: 33         HTTP: 33
HTML: 8          HTML: 8
```

---

## 📊 Comandos Informativos

> **✅ Disponíveis para todos os usuários**

### `/status`

**Descrição:** Mostra estatísticas completas do bot.

**Sintaxe:**
```
/status
```

**Informações Exibidas:**
- ⏰ **Uptime** - Tempo online desde o último restart
- 📡 **Varreduras** - Total de scans completados
- 📰 **Notícias Enviadas** - Total de notícias postadas
- 📦 **Cache Hits** - Total de hits de cache HTTP
- 🕐 **Última Varredura** - Timestamp da última varredura
- ⏳ **Próxima Varredura** - Quando será a próxima (contagem regressiva)

**Botão Adicional:**
- 🔄 **Verificar Agora** - Executa varredura manual

**Resposta:** Embed com todas as estatísticas

---

### `/feeds`

**Descrição:** Lista todas as fontes de feeds monitoradas.

**Sintaxe:**
```
/feeds
```

**Informações Exibidas:**
- Lista de até 15 feeds (com link clicável)
- Total de feeds monitorados
- Contador de feeds adicionais (se houver mais de 15)

**Resposta:** Embed com lista de feeds

---

### `/help`

**Descrição:** Mostra manual de ajuda com todos os comandos.

**Sintaxe:**
```
/help
```

**Informações Exibidas:**
- 📖 Lista de comandos administrativos
- 📊 Lista de comandos informativos
- Organizado por categoria

**Resposta:** Embed com manual completo

---

### `/about`

**Descrição:** Informações sobre o bot, desenvolvedor e tecnologias.

**Sintaxe:**
```
/about
```

**Informações Exibidas:**
- Nome e descrição do bot
- 👨‍💻 Desenvolvedor
- 📦 Versão
- 🛠️ Stack tecnológico
- Mensagem de rodapé

**Resposta:** Embed com informações do bot

---

### `/ping`

**Descrição:** Verifica latência do bot com a API do Discord.

**Sintaxe:**
```
/ping
```

**Resposta:**
```
🏓 Pong! Latência: 45ms
```

---

## 📖 Guia de Uso Detalhado

### 🚀 Primeira Configuração

1. **Configure o Canal:**
   ```
   /set_canal
   ```
   Ou use o dashboard:
   ```
   /dashboard
   ```

2. **Configure os Filtros:**
   - Use o painel do `/dashboard`
   - Clique nos botões para ativar/desativar categorias
   - Ou selecione "TUDO" para receber todas as notícias

3. **Configure o Idioma:**
   - Use `/setlang idioma:pt_BR`
   - Ou clique nas bandeiras no dashboard

4. **Verifique se Está Funcionando:**
   ```
   /forcecheck
   /status
   ```

---

### 🔧 Manutenção Regular

**Limpar Cache (quando necessário):**
```
# Ver estatísticas primeiro
/clean_state tipo:http_cache confirmar:não

# Se necessário, confirmar
/clean_state tipo:http_cache confirmar:sim
```

**Forçar Varredura:**
```
/forcecheck
```

**Verificar Status:**
```
/status
```

---

### ⚠️ Troubleshooting

**Bot não está enviando notícias:**
1. Verifique se canal está configurado: `/status`
2. Verifique se há filtros ativos: `/dashboard` → "Ver filtros"
3. Force uma varredura: `/forcecheck`

**Notícias duplicadas:**
- Limpe o dedup: `/clean_state tipo:dedup confirmar:sim`
- ⚠️ Isso fará o bot repostar notícias recentes!

**Feeds não atualizam:**
- Limpe o cache HTTP: `/clean_state tipo:http_cache confirmar:sim`
- Isso forçará novas requisições HTTP

**Monitor HTML não funciona:**
- Limpe os hashes: `/clean_state tipo:html_hashes confirmar:sim`
- Sites serão detectados como "mudados" novamente

---

## 🔒 Permissões Necessárias

### Para o Bot:
- ✅ **Enviar Mensagens** - Obrigatório
- ✅ **Incorporar Links** - Recomendado (para embeds)
- ✅ **Ler Histórico de Mensagens** - Opcional

### Para Usuários:
- ✅ **Administrador** - Para comandos administrativos
- ✅ **Nenhuma** - Para comandos informativos

---

## 📝 Notas Importantes

1. **Comandos são case-insensitive** - `/HELP` funciona igual a `/help`
2. **Comandos podem levar alguns segundos** - Especialmente `/forcecheck` e `/clean_state`
3. **Backups são criados automaticamente** - Em `backups/` antes de limpezas
4. **Logs de auditoria** - Todas as ações administrativas são logadas
5. **Painel é persistente** - Funciona mesmo após restart do bot

---

**Última Atualização:** Fevereiro 2026  
**Versão do Bot:** 2.1 "Mafty Sovereign"

---

| [📋 Lista de comandos](COMMANDS_LIST.md) | [🧹 Tutorial /clean_state](TUTORIAL_CLEAN_STATE.md) | [🧱 Arquitetura](ARCHITECTURE.md) | [../readme.md](../readme.md) |
