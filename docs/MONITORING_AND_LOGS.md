# Monitoramento e logs

[Voltar ao índice da documentação](https://github.com/carmipa/gundam-news-discord/blob/main/docs/README.md)

---

## Sistema de logging

O bot possui logging com:

- **Cores no Console** — Diferentes cores para cada nivel de log
- **Traceback** — Stack traces formatados
- **Sanitizacao Automatica** — Tokens e senhas sao mascarados
- **Rotacao de Arquivos** — Logs rotacionam automaticamente (5MB, 3 backups)
- **Niveis Configuraveis** — DEBUG, INFO, WARNING, ERROR, CRITICAL

### Exemplo de logs

```
2026-02-13 10:30:45 - [INFO] Bot conectado como: Mafty#1234 (ID: 123456789)
2026-02-13 10:30:46 - [INFO] Servidores conectados: 3
2026-02-13 10:30:47 - [INFO] Agendador de tarefas iniciado (12h).
2026-02-13 10:31:15 - [INFO] Iniciando varredura de inteligencia... (trigger=loop)
2026-02-13 10:31:20 - [WARNING] URL bloqueada por seguranca: http://localhost/test
2026-02-13 10:31:25 - [INFO] Varredura concluida. (enviadas=5, cache_hits=12/15)
```

### Ver logs

```bash
# Docker
docker-compose logs -f

# Local
tail -f logs/bot.log

grep ERROR logs/bot.log
grep WARNING logs/bot.log
```

---

**Documentação técnica:** [LOGGING_AND_EXCEPTIONS.md](https://github.com/carmipa/gundam-news-discord/blob/main/docs/LOGGING_AND_EXCEPTIONS.md) · [Melhorias de logging](https://github.com/carmipa/gundam-news-discord/blob/main/analysis/LOGGING_IMPROVEMENTS.md)

---

## Telemetria de ausência — o veredito por varredura

Um painel que mede só **sucesso** é indistinguível de um painel que não mede
nada: `feeds_falhos=0` significa tanto "nenhuma fonte falhou" quanto "o contador
nunca foi alimentado". Por isso cada varredura fecha com um veredito explícito e
o **motivo** dele.

```
✅ Varredura concluída. (enviadas=12, cache_hits=9, feeds_falhos=2,
                        feeds_vazios=0, traducoes_rejeitadas=0, trigger=loop)
🩺 Saúde da varredura: OK — 12 publicadas, 58 de 60 fontes entregaram
```

| veredito | nível de log | o que significa |
|----------|--------------|-----------------|
| `OK` | INFO | dentro do esperado — e o motivo diz por quê |
| `ATENCAO` | WARNING | degradação real, sem perda de função ainda |
| `ANOMALIA` | ERROR | o bot pode não estar a cumprir a função |

### O que dispara cada um

| condição | veredito |
|----------|----------|
| catálogo vazio (nenhuma fonte carregada) | `ANOMALIA` |
| ≥50% das fontes não entregaram | `ANOMALIA` |
| ≥25% das fontes não entregaram | `ATENCAO` |
| ≥24 ciclos seguidos sem publicar | `ANOMALIA` |
| ≥6 ciclos seguidos sem publicar | `ATENCAO` |
| alguma tradução rejeitada | `ATENCAO` |
| contadores inválidos | `ANOMALIA` |

Duas decisões de calibração que valem explicação:

- **Catálogo vazio é `ANOMALIA`, nunca `OK`.** É exatamente a falha que este
  instrumento existe para apanhar; um detector que reporta catálogo vazio como
  saudável tem um buraco no sítio onde devia enxergar.
- **O zero legítimo é dito com todas as letras.** "0 publicadas neste ciclo —
  sem novidade nas fontes que responderam" é um motivo registado, não silêncio.
  Silêncio e "nada a reportar" parecem iguais no log, e não são.

### `feeds_vazios` — o disfarce mais comum de fonte morta

Uma fonte que responde `200` com **zero entradas** não é uma fonte saudável sem
novidade: é o modo como um feed morre em silêncio (virou HTML, o endpoint passou
a devolver envelope vazio). O contador separa os dois casos, e o log traz a URL:

```
📭 Feed respondeu 200 sem nenhuma entrada: https://exemplo.com/feed
```

### Onde o veredito fica gravado

Em `state.json`, na chave `ultimo_veredito` — telemetria que morre com o processo
não serve para diagnosticar o que aconteceu de madrugada. É preservado pelo
`/clean_state` (é diagnóstico, não estado operacional) e sobrescrito no ciclo
seguinte.

```bash
python3 -c "import json; print(json.load(open('state.json'))['ultimo_veredito'])"
```

### Logs de degradação que valem procurar

| linha | classe de defeito |
|-------|-------------------|
| `🈯 Tradução rejeitada` | o serviço devolveu página de erro; foi publicado o original |
| `📭 Feed respondeu 200 sem nenhuma entrada` | possível fonte morta |
| `♻️ Cache HTTP descartado` | houve falha de entrega; a notícia será retentada |
| `❌ Web Dashboard não subiu` | acessório caiu, a varredura continua |
