# 🔎 Revisão de fontes — Verificação de `sources.json`

[![Verificação](https://img.shields.io/badge/Verificação-Fontes_ativas-blue)](../readme.md)
[![Script](https://img.shields.io/badge/Script-tests%2Ftest_sources.py-green)](../tests/test_sources.py)

Como **revisar e testar** todas as fontes em uso (RSS, YouTube, HTML Monitor).

---

## 🔄 Retries no bot (varredura de feeds)

Na **varredura real** (`core/scanner/fetcher.py` / `engine.py`), cada feed RSS pode ser tentado várias vezes quando a falha parece **transitória**:

- **Erro de conexão** (`ClientError`, ex.: servidor desconectou).
- **Timeout** de leitura.
- **HTTP 5xx** (servidor instável).

Entre tentativas o bot usa **`FEED_FETCH_INTER_RETRY_DELAYS`** (padrão `2,5` segundos entre 1→2 e 2→3); se a lista acabar, cai no backoff exponencial com `FEED_FETCH_RETRY_BACKOFF_SEC`. Em **429**, o valor pedido pelo servidor (`Retry-After` ou `x-ratelimit-reset`) tem prioridade sobre o backoff configurado. Esgotadas as tentativas, o bot passa para a **próxima URL** da cadeia se a fonte declarar `fallbacks`.

Variáveis: `FEED_FETCH_MAX_ATTEMPTS`, `FEED_FETCH_INTER_RETRY_DELAYS`, `FEED_FETCH_RETRY_BACKOFF_SEC` — ver [CONFIGURATION.md](CONFIGURATION.md).

**Fontes lentas, instáveis ou exigentes:** as opções vivem **dentro do objeto da fonte** em `sources.json` (`http_timeout_sec`, `first_request_delay_sec`, `user_agent`, `fallbacks`, `enabled`). Os antigos blocos de topo `feed_fetch_overrides` e `feed_url_fallbacks` já **não são lidos**. Ver secção “Fontes de feeds” em [CONFIGURATION.md](CONFIGURATION.md).

### Throttle por host

Alguns hosts dão orçamento de pedidos por IP, não por sessão. O fetcher serializa
os pedidos a esses hosts e espaça-os (`REDDIT_MIN_INTERVAL_SEC`), porque o semáforo
global (`MAX_CONCURRENT_FEEDS`) sozinho deixa-os sair quase em paralelo.

---

## 🩺 Como decidir se uma fonte morreu

**Reproduza a falha fora do servidor antes de desativar.** Este é o passo que
separa fonte de facto morta de bloqueio do IP do VPS — sem ele, desativa-se uma
fonte saudável e o problema real fica escondido.

```bash
# do seu PC, com UA de navegador
curl -sSL -o /dev/null -w '%{http_code} %{content_type}\n' -A "Mozilla/5.0 (...) Chrome/124" "<URL>"
# e depois a partir do servidor, para comparar
ssh vps 'curl -sSL -o /dev/null -w "%{http_code}\n" "<URL>"'
```

| Resultado | Leitura |
|-----------|---------|
| Falha em ambos | Fonte morta. Desative com `enabled: false` + `disabled_reason` |
| OK fora, falha no VPS | Bloqueio de IP. Não desative — trate com throttle, UA ou proxy |
| 405/403 só com UA de navegador | Regra de WAF invertida. Resolva com `user_agent` |
| NXDOMAIN | Domínio extinto. Confirme com um resolver público (`nslookup dominio 8.8.8.8`) |

---

## 🧹 Ajustes em `sources.json` (manutenção)

### 2026-08-01 — auditoria de fontes mortas

Todas as falhas abaixo foram reproduzidas **fora** do VPS antes de agir.

| Fonte | Diagnóstico | Ação |
|-------|-------------|------|
| `gundamnews.org` (feed e site) | `TLSV1_ALERT_INTERNAL_ERROR` em TLS 1.2 e 1.3, apex e www, em schannel e OpenSSL | `enabled: false`. Reativar quando o handshake voltar |
| `natalie.mu/comic/feed/news` | 405 só com UA de navegador; 200 com UA de biblioteca HTTP | Mantida, com `user_agent` |
| `gundampodcast.com/feed/podcast` | 404; o site é uma vitrine Squarespace sem RSS | Trocado por `pinecast.com/feed/gundam-podcast` |
| `schizophonic9.com/index.rdf` | 404; o blog migrou de domínio | Trocado por `schizophonic9-2.com/?xml` (FC2) + fallback |
| `kimithebuilderblog.com/feed/` | 301 → `/404.html` | WordPress.com passou a canónico |
| `unicorn-gundam-statue.jp` | NXDOMAIN (confirmado via 8.8.8.8); a estátua encerra exibição em ago/2026 | `enabled: false` |
| Reddit (8 feeds) | 429 por orçamento de IP, não bloqueio | Throttle por host + retentativa guiada pelo servidor |

### Anteriores

- Removidos ou migrados feeds que só geravam ruído (404, HTML em vez de RSS, duplicados com HTML watcher): `bandai-hobby.net/feed/`, `p-bandai.com/us/rss`, feeds `en.gundam-official` / tamashii / GCG em formato RSS problemático — substituídos por URLs de **página** no monitor HTML onde faz sentido.
- Reddit **r/Gundam** retirado do monitor HTML (usar só `.rss`); removidos **gundam-navi-app** (serviço encerrado) e **gunplatv.com** (DNS).

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
