# 📋 Lista de Comandos — Gundam News Bot

[![Discord](https://img.shields.io/badge/Discord-Bot-5865F2?logo=discord&logoColor=white)](https://discord.com)
[![Admin](https://img.shields.io/badge/Comandos-Admin%20%7C%20Público-orange)](#-comandos-administrativos)

Lista rápida do que **cada comando faz**. Para detalhes, sintaxe e exemplos, veja [COMMANDS_REFERENCE.md](COMMANDS_REFERENCE.md).

---

## 🔧 Comandos Administrativos

> Requerem permissão de **Administrador** no servidor.

| Comando | O que faz |
|--------|-----------|
| `/set_canal` | Define o canal de texto onde o bot envia notícias (ou usa o canal atual). |
| `/dashboard` | Abre o painel interativo para configurar filtros (Model Kits, Anime & Filmes, Games, Eventos, Merch, Músicas, Roupas, Hardware) e idioma. |
| `/setlang` | Define o idioma do bot para o servidor (pt_BR, en_US, es_ES, it_IT, ja_JP). |
| `/forcecheck` | Força uma varredura imediata de todos os feeds (não espera o ciclo automático). |
| `/clean_state` | Limpa partes do `state.json` (dedup, cache HTTP, hashes HTML ou tudo), com backup e confirmação. |
| `/server_log` | Exibe as últimas linhas do log do servidor (como no docker). Botão **Atualizar** renova. (Admin) |

---

## 📊 Comandos Informativos (públicos)

| Comando | O que faz |
|--------|-----------|
| `/status` | Mostra estatísticas: uptime, varreduras, notícias enviadas, cache hits, próxima varredura. |
| `/now` | Força uma verificação imediata de notícias (botão “Verificar agora” também no `/status`). |
| `/feeds` | Lista todas as fontes monitoradas (RSS, YouTube, sites oficiais). |
| `/help` | Mostra o manual de ajuda com todos os comandos. |
| `/about` | Informações sobre o bot, versão e tecnologias. |
| `/ping` | Verifica a latência do bot com a API do Discord. |

---

## 🧹 Resumo rápido: `/clean_state`

| Tipo | O que limpa | Efeito principal |
|------|-------------|------------------|
| 🧹 **dedup** | Histórico de links já enviados | ⚠️ Pode repostar notícias recentes |
| 🌐 **http_cache** | Cache HTTP (ETags) | Mais requisições; sem repostagem |
| 🔍 **html_hashes** | Hashes de monitoramento HTML | Sites detectados como “mudados” de novo |
| ⚠️ **tudo** | Tudo acima | 🚨 Use só em emergências |

**Uso em 2 passos:** primeiro `confirmar:não` (ver estatísticas), depois `confirmar:sim` (executar).  
**Tutorial completo:** [TUTORIAL_CLEAN_STATE.md](TUTORIAL_CLEAN_STATE.md)

---

## 🔗 Navegação

| Documento | Conteúdo |
|-----------|----------|
| [COMMANDS_REFERENCE.md](COMMANDS_REFERENCE.md) | Referência completa: sintaxe, parâmetros, exemplos |
| [TUTORIAL_CLEAN_STATE.md](TUTORIAL_CLEAN_STATE.md) | Tutorial passo a passo do comando de limpeza |
| [TUTORIAL.md](TUTORIAL.md) | Tutorial geral de todos os comandos |
| [../readme.md](../readme.md) | Visão geral do projeto e instalação |
