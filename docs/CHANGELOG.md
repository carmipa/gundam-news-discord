# 📝 Changelog - Gundam News Bot

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

---

## [Unreleased]

## Auditoria de manutenção — 2026-08-30

Varredura das 9 classes de defeito do procedimento de manutenção de bots.
Baseline da suíte: 125 testes. Depois: 194, zero falha, flake8 e pip-audit limpos.

### Segurança

- **Dependências fixadas com `==` em vez de `>=`** — com `>=`, qualquer rebuild puxa a versão mais recente de cada pacote e uma release comprometida entra em produção sem ninguém decidir nada. Não é hipótese: o `deep-translator` teve a conta do PyPI tomada por phishing em 2022 (PYSEC-2022-252) e a release maliciosa roubava **variáveis de ambiente no momento do install** — e neste bot o ambiente carrega o `DISCORD_TOKEN`. Verificado em 2026-08-30: as releases maliciosas (1.11.2, 1.11.3) foram retiradas do PyPI, a imagem tem a 1.11.4 legítima e nenhum ficheiro do pacote instalado toca `os.environ`, `subprocess` ou download. O alerta fica marcado no pacote e **não tem versão de correção** — aceite conscientemente, com o pin a impedir que um comprometimento futuro entre sozinho.

### Corrigido

- **Tradução: página de erro do serviço publicada como notícia** (classe 3.1). O `deep_translator` não levanta quando o Google responde com página de erro — devolve o corpo dela como se fosse a tradução, e nenhum `try/except` apanha isso, porque o adaptador mente *dentro* do contrato. A validação era `if trad:`, que só rejeita vazio. O lixo era publicado como título **e** resumo, **gravado no cache persistente em disco** (sobrevivendo ao restart) e o link marcado como entregue no dedup — a notícia verdadeira nunca mais sairia. Havia ainda um segundo defeito no mesmo caminho: com `trad = None`, o `return trad` devolvia `None` apesar da assinatura declarar `-> str`. Agora a saída é validada contra assinaturas de página de erro, só entra no cache o que passa, e o retorno é sempre `str` — na dúvida, o original.
- **Arranque: acessório derrubando a varredura** (classe 3.3). `await start_web_server()` era o passo 0 do `on_ready`, sem proteção. Exceção em handler de evento do discord.py é apenas registada — e tudo depois dela deixa de correr, incluindo o `start_scheduler` do passo 3. O resultado é o pior modo de falha possível: bot online, respondendo a comandos, que **nunca varre**, sem erro visível. E o cenário é alcançável: `_startup_done` só é marcado no fim do handler, portanto uma falha intermédia faz a reconexão seguinte reexecutar tudo e bater em `OSError(EADDRINUSE)` na porta já aberta — bot mudo permanentemente até restart. O web server e o preparo de views/canais (que grava config em disco e podia levantar) passaram a ser isolados.
- **Event loop preso pelo parse de HTML** (classe 3.8). `BeautifulSoup` corria dentro das corrotinas do HTML Monitor e do OpenGraph. Medido nesta VPS com 12 páginas reais do catálogo: 2,88s de bloqueio acumulado, pior caso 611ms numa página de 295KB — extrapolado para os ~120 sites vigiados, **~29s de event loop parado por ciclo contra ~41s de intervalo de heartbeat**. Perder o heartbeat faz o Discord derrubar a conexão, e a reconexão redispara o `on_ready` — as duas classes combinam-se. O parse foi movido para `run_in_executor`: bloqueio medido caiu de 3236ms para 113ms (**29x**).
- **`Invalid Form Body` retentado para sempre.** Medido em produção: `400 Bad Request (error code: 50035)` de hora em hora, durante dias, na mesma guild — 26 ocorrências em 4 semanas. Como a falha de envio não marca o link no dedup, o ciclo seguinte tentava outra vez, indefinidamente. A causa: o resumo é cortado a 2000 caracteres **antes** de traduzir, e a tradução expande — 2000 caracteres de japonês passam largamente os 4096 da descrição. Todos os campos do embed passaram a respeitar os limites da API, incluindo o teto de 6000 da **soma**, que é o modo de falha menos óbvio.
- **Cache HTTP contando entrega falhada como sucesso** (classe 3.2). O ETag é gravado assim que o corpo chega, muito antes de a notícia sair. Com a entrega a falhar, o cache ficava gravado e a varredura seguinte recebia 304 — nem chegava a ver a notícia que não saiu; com o feed parado, ela nunca mais era tentada. O cache dos feeds com falha de entrega passou a ser descartado antes de gravar o state.
- **Motivo da rejeição descartado** (classe 3.9). Cinco `except Exception:` nus em `notifier.py` e `processor.py` capturavam a falha e deitavam fora a causa. Passaram a registar o motivo — falha invisível é falha que ninguém corrige.
- **Três nomes indefinidos (`F821`)** apanhados pelo portão de lint em código que o pytest não exercita: `url` em vez de `link` no notifier e duas referências a `cfg` fora de escopo em `main.py`.

### Adicionado

- **Telemetria de ausência** (classe 3.6). O painel media só sucesso: `feeds_falhos=0` era indistinguível de "o contador nunca foi alimentado". Cada varredura passou a fechar com um **veredito explícito e o motivo** (`OK` / `ATENCAO` / `ANOMALIA`), persistido no `state.json` para sobreviver ao restart. Mede o que **não** aconteceu: fontes que responderam 200 sem nenhuma entrada (o disfarce mais comum de fonte morta), traduções rejeitadas, e ciclos seguidos sem publicar. Catálogo vazio é `ANOMALIA`, nunca `OK` — é a falha que o instrumento existe para apanhar. O zero legítimo é dito com todas as letras, em vez de silêncio.
- **Guardas calibradas** para cada correção: 69 testes novos (125 → 194), cada regra com controle positivo (tem de acusar) **e** negativo (tem de ficar calada). O caso que separa validação de censura: uma notícia que legitimamente *fala* de "Error 404" tem de passar. A guarda do event loop mede o **atraso do loop**, não "se o parse acontece" — a propriedade certa nunca é *se*, é *onde* e *com que efeito*.


## Sessão anterior — 2026-08-01

### Segurança

- **`.env` deixou de entrar na imagem Docker** — o `.dockerignore` não o excluía e o `COPY . .` gravava `DISCORD_TOKEN`, `CLOUDFLARE_PROXY_SECRET` e a senha do dashboard numa layer legível por `docker history`/`save`. O Compose já o injetava em runtime via `env_file`; nunca foi preciso na imagem.
- **Dashboard web deixou de ser publicado em todas as interfaces** — o Compose publicava `"${HOST_WEB_PORT}:${WEB_PORT}"`, que o Docker liga a `0.0.0.0`. Na VPS isto estava corrigido à mão, num `docker-compose.yml` alterado localmente que nunca voltou ao repositório — ou seja, qualquer deploy novo a partir do repo nascia com o dashboard exposto. O bind passou a ser `${HOST_WEB_BIND:-127.0.0.1}`, seguro por omissão e sobreponível para quem tiver proxy com TLS à frente.
- **Sanitizador de logs deixou de destruir o diagnóstico** — o padrão `([a-zA-Z0-9_-]{20,})` truncava **qualquer** sequência longa para 8 caracteres, sem proteger nada que as regras de rótulo já não cobrissem. Domínios viravam `unicorn-....jp`, `TLSV1_ALERT_INTERNAL_ERROR` virava `TLSV1_AL...` e IDs de canal do YouTube ficavam ilegíveis. Substituído por 5 padrões ancorados (rótulo `token=`/`secret=`, `Authorization: Bearer/Bot`, forma estrutural do token do Discord, webhook e segredo em query string).

### Adicionado

- **Categorias de filtro: Músicas & Trilhas 🎵, Roupas & Vestuário 👕 e Hardware & PC 💻** — a última cobre as edições Gundam de placas-mãe, GPUs, SSDs, gabinetes e periféricos, que saem esporadicamente e antes não tinham como ser assinadas isoladamente.
- **Keywords em japonês passaram a funcionar nas categorias** — kana e kanji contam como `\w`, então o `\b` nunca casava no meio de uma frase (`アニメ主題歌決定`). Keywords CJK passaram a ser casadas por substring, como já acontecia nos hints do portão Gundam.
- **Throttle por host no fetcher** — lock e espaçamento mínimo por domínio (`REDDIT_MIN_INTERVAL_SEC`), com a retentativa de 429 guiada por `Retry-After`/`x-ratelimit-reset` em vez do backoff fixo.
- **Cooldown do HTML Monitor** (`HTML_MONITOR_COOLDOWN_HOURS`, padrão 24h) — avisos de site oficial não passam por dedup nem history, então portais com banner rotativo postavam "🔄 Update" de hora em hora sem notícia nova.
- **`user_agent` por fonte** em `sources.json`, e `enabled: false` passou a ser respeitado também pelo HTML Monitor.
- **`translation_cache.json` virou volume** no Compose — sem isso o ficheiro morria a cada `up --build` e a varredura seguinte re-scrapava o Google em rajada.

### Corrigido

- **`/clean_state` não conhecia o cooldown do HTML Monitor** — a chave `html_monitor_posted` foi acrescentada ao `state.json` nesta mesma versão e ficou de fora da limpeza. Limpar `html_hashes` (ou `tudo`) re-inicializava os sites, mas o cooldown sobrevivente silenciava por 24h o aviso da deteção seguinte, que é legítima; e `tudo` deixava de significar tudo. O `state.json` de produção já tinha 4 entradas de cooldown quando isto foi detetado. Agora é limpo junto com os hashes, conta nas estatísticas do preview e aparece no log de auditoria. `tests/test_clean_state_cooldown.py` inclui uma guarda genérica que falha se qualquer chave nova de estado escrita pelo engine não for tratada pelo `clean_state`.
- **Filtros legados silenciosamente mortos** — `config.json` de servidores anteriores à renomeação guardava `gunpla`, `filmes` e `musica`, que não existiam no `CAT_MAP`. `CAT_MAP.get(nome, [])` devolvia lista vazia e o filtro rejeitava tudo **sem nenhum log**. Medido na produção: 4 guilds afetadas, 2 delas com canal ativo recebendo zero notícias. Agora `gunpla` e `filmes` são traduzidos na leitura (e o config migra no primeiro save do painel) e `musica` virou categoria de pleno direito.
- **Fonte de rate limit do Reddit mal diagnosticada** — o log dizia `(via proxy: True)` mesmo com `CLOUDFLARE_PROXY_URL` vazio, porque reportava a *intenção* e não o roteamento real. A causa verdadeira é o orçamento por IP do Reddit. O log passou a reportar o que de facto acontece.
- **Fronteira de keywords numéricas** — `\b00\b` casava `12:00`, porque `:` conta como fronteira de palavra. Keywords só de dígitos passaram a usar fronteira estrita, que também exclui `2000` e `300`; keywords de texto mantêm o `\b` clássico.
- **Fontes mortas em `sources.json`** — `gundamnews.org` e `unicorn-gundam-statue.jp` desativados com motivo registado; `gundampodcast.com` → Pinecast; `schizophonic9.com` → `schizophonic9-2.com`; Kimi the Builder passou a ter o WordPress.com como canónico; Natalie mantida com `user_agent` próprio.
- **Suíte de testes voltou a correr por inteiro** — `test_filters_regex.py` não coletava (importava `is_trusted_gundam_source`, que nunca existiu) e `test_gundam_logic_manual.py` chamava `sys.exit(1)` no import, derrubando o pytest com `INTERNALERROR`. Também corrigidos `test_user_news.py` (função `test_item` coletada como teste com fixtures inexistentes), `test_readme_exists` (procurava `readme.md` minúsculo, falhando em Linux) e `test_aiohttp_timeout_usage` (inspecionava `run_scan_once`, mas o timeout mudou para `fetch_feed`). De 58 testes verdes com 2 ficheiros mortos para **110 verdes, zero falhas, sem exclusões**.
- **Arranque do container** — `core/scanner/notifier.py` importava `Optional` e `aiohttp.ClientSession` nas anotações sem import explícito, gerando `NameError` e restart em loop no Docker.

### Documentação

- **`CONFIGURATION.md` descrevia um schema morto** — ensinava a configurar `feed_url_fallbacks`, `feed_fetch_overrides`, `extra_headers` e `unstable` como blocos de topo do `sources.json`. Nenhum deles é lido por código algum desde a modularização do fetcher: quem seguisse a doc configuraria coisas que não fazem nada, em silêncio. Reescrito para o formato real (opções dentro do objeto de cada fonte) com aviso de migração.
- **`DASHBOARD_AND_FILTERS.md` reescrito** — listava categorias que não existiam com esses nomes e confundia `BLACKLIST` com `NEGATIVE_KEYWORDS`. Agora traz as 9 categorias reais com a chave de `config.json` de cada uma, as regras de casamento por tipo de keyword (texto, numérica, japonês), as duas listas de bloqueio com os valores extraídos do código e o passo a passo para adicionar categorias.
- **`SOURCES_VERIFICATION.md`** — nova secção sobre como decidir se uma fonte morreu (reproduzir a falha **fora** do servidor antes de desativar, que é o que separa fonte morta de bloqueio de IP) e a tabela da auditoria de 2026-08-01.
- **Arquitetura** — Documentação alinhada ao pacote `core/scanner/` (engine, fetcher, processor, notifier): coleta principal via **RSS/Atom/YouTube (syndication)**; HTML Monitor para sites sem feed; Open Graph apenas como enriquecimento de thumbnail.
- **Estrutura do projeto**, **SOURCES_VERIFICATION**, READMEs EN/ES/IT/JP: referências atualizadas de `core/scanner.py` → `core/scanner/`.

---

## [2.1.0] - 2026-02-13

### ✨ Adicionado

- **Novo comando `/set_canal`** - Comando dedicado para configurar o canal onde o bot enviará notícias
- **Sistema de segurança aprimorado** (`utils/security.py`)
  - Validação de URLs (anti-SSRF)
  - Bloqueio de IPs privados e domínios locais
  - Sanitização de logs automática
- **Rate limiting** no servidor web
- **Autenticação opcional** no servidor web via token
- **Headers de segurança HTTP** (CSP, X-Frame-Options, etc.)
- **Sistema de logging melhorado**
  - Logs coloridos no console
  - Traceback colorido para exceções
  - Sanitização automática de informações sensíveis
  - Tratamento específico de exceções com contexto

### 🔒 Segurança

- ✅ Validação de URLs antes de fazer requisições HTTP
- ✅ Proteção anti-SSRF (Server-Side Request Forgery)
- ✅ Rate limiting em comandos críticos
- ✅ Sanitização de logs (tokens, senhas mascarados)
- ✅ Headers de segurança HTTP configurados
- ✅ Validação de certificados SSL

### 🐛 Corrigido

- **Erros silenciosos corrigidos** - Todos os `except: pass` agora logam adequadamente
- **Tratamento de exceções melhorado** - Exceções específicas com contexto detalhado
- **Teste de SSL corrigido** - Agora verifica o pacote `core/scanner/` (fetcher/engine) ao invés de `main.py`

### 📝 Melhorado

- **Documentação completa** - READMEs atualizados em 4 idiomas (PT, EN, ES, IT, JP)
- **Logs mais informativos** - Tipo de exceção, contexto e traceback completo
- **Mensagens de erro melhoradas** - Mais claras e específicas
- **Validação de permissões** - Verificação automática ao configurar canal

### 📚 Documentação

- Adicionado `SECURITY_GRC_ANALYSIS.md` - Análise completa de segurança e GRC
- Adicionado `LOGGING_IMPROVEMENTS.md` - Documentação das melhorias de logging
- READMEs atualizados com:
  - Diagramas de arquitetura melhorados
  - Shields/badges atualizados
  - Instruções detalhadas de segurança
  - Exemplos de uso do novo comando `/set_canal`

---

## [2.0.0] - Versão Anterior

### Funcionalidades Principais

- Scanner periódico de feeds RSS/Atom/YouTube
- Dashboard interativo persistente
- Sistema de filtros por categoria
- Multi-guild e multi-idioma
- Web dashboard
- Auto-cleanup de cache
- Cold start para novas fontes

---

**Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/)**
