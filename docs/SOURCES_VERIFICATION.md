# 🔎 Revisão de fontes — Verificação de `sources.json`

[![Verificação](https://img.shields.io/badge/Verificação-Fontes_ativas-blue)](../readme.md)
[![Script](https://img.shields.io/badge/Script-tests%2Ftest_sources.py-green)](../tests/test_sources.py)

Como **revisar e testar** todas as fontes em uso (RSS, YouTube, HTML Monitor).

---

## 🔄 Retries no bot (varredura de feeds)

Na **varredura real** (`core/scanner.py`), cada feed RSS pode ser tentado várias vezes quando a falha parece **transitória**:

- **Erro de conexão** (`ClientError`, ex.: servidor desconectou).
- **Timeout** de leitura.
- **HTTP 5xx** (servidor instável).

Entre tentativas o bot usa **backoff exponencial** (base configurável, teto 30 s). Erros **definitivos** (403, 404, 429, 4xx genérico) **não** são repetidos.

Variáveis: `FEED_FETCH_MAX_ATTEMPTS`, `FEED_FETCH_RETRY_BACKOFF_SEC` — ver [CONFIGURATION.md](CONFIGURATION.md).

**Fontes lentas ou instáveis:** use a chave opcional `feed_fetch_overrides` no mesmo `sources.json` (URL exata → `unstable`, `http_timeout_sec`, `note`). Ver secção “Fontes de feeds” em [CONFIGURATION.md](CONFIGURATION.md).

---

## 🧹 Ajustes recentes em `sources.json` (manutenção)

- Removidos ou migrados feeds que só geravam ruído (404, HTML em vez de RSS, duplicados com HTML watcher): por exemplo `bandai-hobby.net/feed/`, `p-bandai.com/us/rss`, feeds `en.gundam-official` / tamashii / GCG em formato RSS problemático — substituídos por URLs de **página** no monitor HTML onde faz sentido.
- Reddit **r/Gundam** retirado do monitor HTML (usar só `.rss`); removidos **gundam-navi-app** (serviço encerrado) e **gunplatv.com** (DNS).
- Feed WordPress do Kimi: URL direta `kimithebuilderblog.wordpress.com/feed/`.

Rodar `python tests/test_sources.py` após qualquer edição manual de fontes.

---

## 📋 Como rodar a verificação

Na **raiz do projeto**:

```bash
python tests/test_sources.py
```

- Lê `sources.json` (rss_feeds, youtube_feeds, official_sites_reference_(not_rss)).
- Para cada URL: faz GET, valida resposta (RSS/Atom parseável ou HTML com título).
- Escreve o resultado em **`verification_results.txt`** e imprime um **resumo** no console.

**Tempo estimado:** 2–5 minutos (depende da rede e do número de URLs).

---

## 📊 Último resumo (exemplo)

| Tipo     | OK  | Falhas |
|----------|-----|--------|
| RSS      | 20  | 10     |
| YouTube  | 2*  | 10*    |
| HTML     | 96  | 3      |
| **Total**| 118 | 23     |

\* YouTube pode variar (404/500 temporários). Recomenda-se rodar de novo em outro horário antes de remover canais.

---

## ❌ Fontes que costumam falhar (para revisar)

### RSS

| URL | Motivo |
|-----|--------|
| `https://www.crunchyroll.com/news/rss?lang=en-us` | XML mal formado (parse error) |
| `https://www.gundamkitscollection.com/feeds/posts/default/-/The%20Gundam%20Base` | Feed vazio (categoria) |
| `https://www.gundamkitscollection.com/feeds/posts/default/-/Gundam%20Card%20Game` | Feed vazio |
| `https://www.gundamkitscollection.com/feeds/posts/default/-/Gundam%20Hangar` | Feed vazio |
| `https://tamashiiweb.com/rss/news/?wovn=en` | HTTP 404 |
| `https://p-bandai.com/us/news/rss` | HTTP 400 |
| `https://www.gundam-base.net/rss.xml` | Timeout (redundante: `/feed` e `/rss` já funcionam) |
| `https://www.gundam-base.net/index.rdf` | Timeout |
| `https://www.gundam-base.net/news/rss.xml` | Timeout |
| `https://www.gundam-base.net/news/feed` | Feed vazio |

### YouTube

- Vários canais podem retornar **HTTP 404** (canal removido/privado) ou **500** (temporário). Conferir no relatório e, se persistir, remover o `channel_id` de `youtube_feeds`.

### HTML Monitor

| URL | Motivo |
|-----|--------|
| `https://store.bandainamcoent.com/` | HTTP 403 (bloqueio bot) |
| `https://www.toy-people.com/en/` | HTTP 403 |

---

## 🧹 Limpeza sugerida em `sources.json`

1. **RSS:** Remover feeds que falham de forma estável (404, 400, feed vazio, timeout redundante), por exemplo:
   - Crunchyroll (parse error),
   - tamashiiweb (404),
   - p-bandai/us/news/rss (400),
   - GKC por categoria (The Gundam Base, Gundam Card Game, Gundam Hangar) se quiser menos ruído,
   - gundam-base.net: manter só `/feed` e `/rss`; remover `rss.xml`, `index.rdf`, `news/rss.xml`, `news/feed` se quiser evitar timeouts/duplicidade.

2. **YouTube:** Após rodar de novo e ver quais canais ficam 404 de forma consistente, remover esses `channel_id` de `youtube_feeds`.

3. **HTML:** Opcional remover ou comentar URLs que retornam 403 (ex.: store.bandainamcoent.com, toy-people.com) para reduzir log de falha.

Depois de alterar `sources.json`, rode de novo:

```bash
python tests/test_sources.py
```

e confira `verification_results.txt` e o resumo no console.
