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
LOG_LEVEL=INFO  # Use DEBUG para logs detalhados
HTTP_TIMEOUT=10  # Timeout HTTP em segundos (feeds e sites oficiais)
# Retries em feeds RSS (falhas transitórias: timeout, desconexão, HTTP 5xx)
FEED_FETCH_MAX_ATTEMPTS=3   # padrão: 3 tentativas por URL
FEED_FETCH_RETRY_BACKOFF_SEC=2.0  # reserva se FEED_FETCH_INTER_RETRY_DELAYS estiver vazio
FEED_FETCH_INTER_RETRY_DELAYS=2,5  # pausas (s) entre tentativas 1→2, 2→3, … (CSV)
FEED_HTTP_TIMEOUT_MAX_SEC=120  # teto (s) para timeout por feed em feed_fetch_overrides
FEED_FIRST_DELAY_MAX_SEC=30  # teto (s) para first_request_delay_sec por feed

# Segurança do Servidor Web (Opcional)
WEB_AUTH_TOKEN=seu_token_secreto_aqui  # Recomendado para produção
WEB_HOST=127.0.0.1  # 127.0.0.1 = apenas localhost, 0.0.0.0 = todos os IPs
WEB_PORT=8080
```

> **Segurança:** Configure `WEB_AUTH_TOKEN` em produção para proteger o dashboard web!

## Fontes de feeds (`sources.json`)

O bot aceita múltiplos formatos:

<details>
<summary><b>Formato com categorias (recomendado)</b></summary>

```json
{
  "rss_feeds": [
    "https://www.animenewsnetwork.com/news/rss.xml",
    "https://gundamnews.org/feed"
  ],
  "youtube_feeds": [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCejtUitnpnf8Be-v5NuDSLw"
  ],
  "official_sites_reference_(not_rss)": [
    "https://gundam-official.com/",
    "https://en.gundam-official.com/news"
  ],
  "feed_url_fallbacks": {
    "https://exemplo.com/feed/": [
      "https://exemplo.wordpress.com/feed/"
    ]
  },
  "feed_fetch_overrides": {
    "https://exemplo.com/feed": {
      "unstable": true,
      "http_timeout_sec": 28,
      "first_request_delay_sec": 1.5,
      "extra_headers": {
        "Referer": "https://exemplo.com/",
        "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8"
      },
      "note": "Opcional: explicação para quem edita o arquivo"
    }
  }
}
```

`feed_url_fallbacks` é **opcional**. Chave = URL canónica (a que está em `rss_feeds` / `youtube_feeds`); valor = lista de URLs alternativas. O **dedup** e o “cold start” usam só a URL canónica; fallbacks servem apenas se o GET na canónica falhar (403/404/429, 5xx após retries, 200 vazio, timeout, desconexão).

`feed_fetch_overrides` é **opcional**. Chaves são URLs **exatas** de cada GET (canónica ou cada fallback). Campos:

- **`unstable`** (bool): se após esgotar retries a falha for por conexão, timeout ou HTTP 5xx, o log usa **WARNING** “fonte instável” em vez de **ERROR** na conexão.
- **`http_timeout_sec`** (número): timeout só para esse feed (respeita `FEED_HTTP_TIMEOUT_MAX_SEC`).
- **`first_request_delay_sec`** (número): pausa **só na 1.ª tentativa** de cada varredura, depois do delay do YouTube (se aplicável), antes do GET (útil para WordPress/CDN; respeita `FEED_FIRST_DELAY_MAX_SEC`).
- **`extra_headers`**: objeto com cabeçalhos **permitidos** (whitelist): `Referer`, `Origin`, `Accept`, `Accept-Language`, `Accept-Encoding`, `Cache-Control`, `Pragma`, `Connection` (somente valor `close`). São fundidos ao pedido (podem suavizar “Server disconnected” em alguns hosts).
- **`note`**: só documentação humana; o bot não lê.

</details>

<details>
<summary><b>Formato lista simples</b></summary>

```json
[
  "https://www.animenewsnetwork.com/news/rss.xml",
  "https://gundamnews.org/feed"
]
```

</details>

---

**Relacionado:** [Verificação de fontes](https://github.com/carmipa/gundam-news-discord/blob/main/docs/SOURCES_VERIFICATION.md) · [Arquitetura](https://github.com/carmipa/gundam-news-discord/blob/main/docs/ARCHITECTURE.md)
