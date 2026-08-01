# Configuração

[Voltar ao índice da documentação](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README.md)

---

## Variáveis de ambiente (`.env`)

```env
# OBRIGATÓRIO
DISCORD_TOKEN=seu_token_aqui

# OPCIONAL
COMMAND_PREFIX=!
LOOP_MINUTES=720
LOG_LEVEL=INFO  # DEBUG = todo o app verboso; ou mantenha INFO e use SCAN_VERBOSE
SCAN_VERBOSE=0   # 1 = logs da varredura (SEMAFORO, JITTER, PROXY, CACHE, FEED PRONTO) em INFO no servidor/Docker
HTTP_TIMEOUT=10  # Timeout HTTP em segundos (feeds e sites oficiais)
# Retries em feeds RSS (falhas transitórias: timeout, desconexão, HTTP 5xx)
FEED_FETCH_MAX_ATTEMPTS=3   # padrão: 3 tentativas por URL
FEED_FETCH_RETRY_BACKOFF_SEC=2.0  # reserva se FEED_FETCH_INTER_RETRY_DELAYS estiver vazio
FEED_FETCH_INTER_RETRY_DELAYS=2,5  # pausas (s) entre tentativas 1→2, 2→3, … (CSV)
FEED_HTTP_TIMEOUT_MAX_SEC=120  # teto (s) para "http_timeout_sec" por fonte
FEED_FIRST_DELAY_MAX_SEC=30  # teto (s) para "first_request_delay_sec" por fonte

# User-Agent padrão dos feeds: de navegador, porque a maioria dos portais de
# hobby japoneses bloqueia crawlers. Sobreponível por fonte com "user_agent".
# FEED_BROWSER_USER_AGENT=Mozilla/5.0 (...) Chrome/124.0.0.0 Safari/537.36
# UA identificável, para as fontes que fazem o inverso (a Natalie devolve 405
# para UA de navegador e 200 para UA de biblioteca HTTP).
# FEED_USER_AGENT=MaftyIntelBot/1.0 (+https://github.com/carmipa/gundam-news-discord) Python/3.10 aiohttp/3.9.5

# Reddit: intervalo mínimo (s) entre pedidos ao mesmo host.
# O Reddit dá ~1 pedido por janela de segundos POR IP a clientes anónimos
# (x-ratelimit-reset: 6). Sem espaçamento, os 8 feeds saem quase juntos e 7
# voltam 429. Ver a secção "Limites de terceiros" mais abaixo.
REDDIT_MIN_INTERVAL_SEC=12

# HTML Monitor: horas mínimas entre dois avisos do MESMO site oficial.
# Portais com banner rotativo mudam o hash a cada ciclo e geravam um post
# "🔄 Update" por hora sem notícia nova. 0 desliga o cooldown.
HTML_MONITOR_COOLDOWN_HOURS=24

# Segurança do Servidor Web (Opcional)
WEB_AUTH_TOKEN=seu_token_secreto_aqui  # Recomendado para produção
WEB_HOST=127.0.0.1  # 127.0.0.1 = apenas localhost, 0.0.0.0 = todos os IPs
WEB_PORT=8080
HOST_WEB_PORT=8080  # só Docker Compose: porta no host; muda se 8080 no VPS estiver ocupada

# Proxy Cloudflare Worker (Opcional). Se ficar vazio, TODOS os pedidos vão
# diretos — inclusive os que pedem proxy via "use_proxy".
CLOUDFLARE_PROXY_URL=
CLOUDFLARE_PROXY_SECRET=
```

> **Segurança:** Configure `WEB_AUTH_TOKEN` em produção para proteger o dashboard web!
>
> O `.env` **nunca** entra na imagem Docker: está no `.dockerignore` e o Compose
> injeta-o em runtime via `env_file`. Copiá-lo no build gravaria o `DISCORD_TOKEN`
> numa layer legível por qualquer um com acesso à imagem.

## Fontes de feeds (`sources.json`)

> ⚠️ **Schema mudou.** Os blocos de topo `feed_url_fallbacks` e
> `feed_fetch_overrides` (com `extra_headers` e `unstable`) **deixaram de ser
> lidos** no refactor que modularizou o fetcher. As opções passaram para dentro
> de cada fonte. Se ainda tiver esses blocos no ficheiro, eles são ignorados em
> silêncio — mova as opções para o objeto da fonte.

Cada lista aceita strings soltas ou objetos. O objeto é o formato atual:

```json
{
  "rss_feeds": [
    "https://www.animenewsnetwork.com/news/rss.xml",

    {
      "name": "Natalie Comic",
      "url": "https://natalie.mu/comic/feed/news",
      "category": "news",
      "language": "ja",
      "user_agent": "MaftyIntelBot/1.0 (+https://github.com/carmipa/gundam-news-discord) Python/3.10 aiohttp/3.9.5",
      "notes": "O WAF devolve 405 para UA de navegador e 200 para UA de biblioteca HTTP."
    },
    {
      "name": "Kimi the Builder Blog",
      "url": "https://kimithebuilderblog.wordpress.com/feed/",
      "fallbacks": ["https://exemplo.alternativo.com/feed/"],
      "http_timeout_sec": 28,
      "first_request_delay_sec": 1.5
    },
    {
      "name": "Gundam News",
      "url": "https://gundamnews.org/feed",
      "enabled": false,
      "disabled_reason": "TLS do servidor quebrado (TLSV1_ALERT_INTERNAL_ERROR)."
    }
  ],
  "youtube_feeds": [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCejtUitnpnf8Be-v5NuDSLw"
  ],
  "official_sites": [
    { "name": "GUNDAM Official", "url": "https://gundam-official.com/", "region": "jp" }
  ]
}
```

### Campos por fonte

| Campo | Tipo | Efeito |
|-------|------|--------|
| `url` | string | **Obrigatório.** URL canónica — é ela que serve de chave do dedup e das estatísticas, mesmo quando quem responde é um fallback |
| `enabled` | bool | `false` remove a fonte da fila. Vale para feeds RSS **e** para `official_sites` (HTML Monitor) |
| `disabled_reason` | string | Só documentação. Registe **porquê** e o que reativa |
| `fallbacks` | lista | URLs alternativas, tentadas por ordem se a canónica falhar (403/404/429, 5xx após retries, timeout, desconexão) |
| `user_agent` | string | Sobrepõe o UA de navegador. Use para fontes que só respondem a clientes HTTP identificados |
| `http_timeout_sec` | número | Timeout só desta fonte (limitado por `FEED_HTTP_TIMEOUT_MAX_SEC`) |
| `first_request_delay_sec` | número | Pausa antes do primeiro GET da varredura (limitado por `FEED_FIRST_DELAY_MAX_SEC`) |
| `use_proxy` | bool | Força o roteamento pelo Cloudflare Worker. **Sem efeito se `CLOUDFLARE_PROXY_URL` estiver vazio** |
| `name`, `category`, `language`, `region`, `notes` | string | Só documentação; o bot não decide nada com eles |

Um `304 Not Modified` não conta como falha e **não** aciona fallback: significa
que o cache HTTP está a funcionar.

---

## Limites de terceiros

Nem toda falha de feed é bug. As que estão diagnosticadas:

| Fonte | Sintoma | Natureza |
|-------|---------|----------|
| Reddit | 429 em quase todos os feeds | Orçamento por IP (~1 pedido/janela de segundos). Mitigado pelo throttle por host; **não** se resolve esperando mais. Cobertura total exigiria a API OAuth |
| Natalie | 405 com UA de navegador | Regra de WAF. Resolvido com `user_agent` de biblioteca HTTP |
| Lojas (1999.co.jp, gundamplanet, usagundamstore) | 403/429 a partir do VPS | Bloqueio de IP de datacenter |

> Antes de marcar uma fonte como morta, reproduza a falha **fora** do servidor.
> Foi o que separou fonte de facto morta de bloqueio de IP na auditoria de
> 2026-08-01 — ver [Verificação de fontes](https://github.com/carmipa/gundam-news-discord/blob/main/docs/SOURCES_VERIFICATION.md).

---

**Relacionado:** [Verificação de fontes](https://github.com/carmipa/gundam-news-discord/blob/main/docs/SOURCES_VERIFICATION.md) · [Arquitetura](https://github.com/carmipa/gundam-news-discord/blob/main/docs/ARCHITECTURE.md)
