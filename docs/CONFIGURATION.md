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
  ]
}
```

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
