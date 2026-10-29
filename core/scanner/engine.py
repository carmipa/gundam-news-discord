"""
Engine module - The main orchestration logic for the scanning process.
"""
import asyncio
import copy
import logging
import time
import aiohttp
import ssl
import certifi
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple

import discord
from discord.ext import tasks

from settings import (
    LOOP_MINUTES, 
    LOOP_INTERVAL_STR, 
    MAX_CONCURRENT_FEEDS,
    FEED_FETCH_JITTER_MIN,
    FEED_FETCH_JITTER_MAX,
    MAX_ENTRIES_PER_FEED,
    MAX_YOUTUBE_ENTRIES_PER_FEED,
    HISTORY_LIMIT,
    HTML_MONITOR_COOLDOWN_SEC,
    HTML_MONITOR_COOLDOWN_HOURS,
    MANUAL_SCAN_COOLDOWN_SEC,
)
from utils.storage import p, load_json_safe, save_json_safe, load_config_cached
from core.stats import stats, avaliar_varredura, VEREDITO_OK, VEREDITO_ATENCAO
from core.filters import match_intel

# Novas importacoes modularizadas
from .fetcher import load_sources, fetch_feed, _fallback_urls
from .logutil import scan_verbose
from .processor import load_history, save_history, prune_dedup, sanitize_link, parse_entry_dt, is_recent
from .notifier import create_embed, resolve_thumbnail
from utils.translator import save_translation_cache
from core.html_monitor import check_official_sites

log = logging.getLogger("MaftyIntel.scanner")
scan_lock = asyncio.Lock()

PEDIDO_INICIADO = "iniciada"
PEDIDO_EM_ANDAMENTO = "em_andamento"
PEDIDO_AGUARDE = "aguarde"

# Instante (time.monotonic) do início da varredura mais recente, de qualquer
# gatilho. 0.0 = nenhuma ainda neste processo.
_inicio_ultima_varredura: float = 0.0
# Referências fortes às tarefas manuais: o event loop só guarda referência fraca,
# e uma tarefa sem dono pode ser recolhida pelo GC no meio da varredura.
_tarefas_manuais: Set["asyncio.Task[None]"] = set()


def solicitar_varredura_manual(
    bot: discord.Client, trigger: str, agora: Optional[float] = None
) -> Tuple[str, int]:
    """
    Porta única para varredura pedida por pessoa (comando, botão, painel).

    PROPÓSITO DE NEGÓCIO:
        A varredura é global — percorre todas as fontes e publica em todas as
        guilds. Pedido manual serve para "não esperar o próximo ciclo", não para
        encadear varreduras: cada uma consome o orçamento de rate limit do Reddit,
        do YouTube e do Google Translate do IP inteiro.

    INVARIANTES DO DOMÍNIO:
        - Nunca duas varreduras ao mesmo tempo (o `scan_lock` segue valendo).
        - Entre o início de qualquer varredura e o de uma manual passam pelo menos
          MANUAL_SCAN_COOLDOWN_SEC segundos, venha o pedido de qualquer guild.
        - O resultado devolvido diz a verdade: "iniciada" só quando a tarefa foi
          de fato criada — nunca "concluída" antes de a varredura rodar.

    COMPORTAMENTO EM CASO DE FALHA:
        Não levanta. Devolve (PEDIDO_EM_ANDAMENTO, 0) se já há varredura,
        (PEDIDO_AGUARDE, segundos_restantes) dentro do intervalo mínimo, ou
        (PEDIDO_INICIADO, 0). Erro DENTRO da varredura fica no log do engine.
    """
    global _inicio_ultima_varredura
    agora = time.monotonic() if agora is None else agora
    if scan_lock.locked():
        return PEDIDO_EM_ANDAMENTO, 0
    if MANUAL_SCAN_COOLDOWN_SEC > 0 and _inicio_ultima_varredura:
        restante = MANUAL_SCAN_COOLDOWN_SEC - (agora - _inicio_ultima_varredura)
        if restante > 0:
            log.info(f"Varredura manual recusada (trigger={trigger}): intervalo mínimo, faltam {restante:.0f}s.")
            return PEDIDO_AGUARDE, int(restante + 0.999)
    # Marca já aqui, e não só dentro do run_scan_once: dois pedidos no mesmo
    # instante passariam ambos pela checagem antes de a tarefa pegar o lock.
    _inicio_ultima_varredura = agora
    tarefa = asyncio.create_task(run_scan_once(bot, trigger=trigger))
    _tarefas_manuais.add(tarefa)
    tarefa.add_done_callback(_tarefas_manuais.discard)
    return PEDIDO_INICIADO, 0


def _log_next_run() -> None:
    """Próximo horário estimado após o fim de uma varredura (alinhado ao intervalo LOOP_MINUTES)."""
    nxt = datetime.now() + timedelta(minutes=LOOP_MINUTES)
    log.info(
        f"⏳ Aguardando próxima varredura às {nxt:%Y-%m-%d %H:%M:%S} "
        f"(em {LOOP_INTERVAL_STR})..."
    )

def _chaves_de_cache_por_feed(sources: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Mapeia a URL canônica de cada fonte para TODAS as chaves que o fetcher pode
    ter gravado no cache HTTP: a própria e cada fallback.

    O fetcher grava ETag/Last-Modified com a chave da URL que respondeu. Quando o
    feed é servido por um fallback e a entrega falha, descartar só a canônica
    deixava o ETag do fallback: o ciclo seguinte recebia 304 dele e a notícia
    que não saiu nunca mais era vista.
    """
    mapa: Dict[str, List[str]] = {}
    for src in sources:
        url = src.get("url")
        if not url:
            continue
        mapa[url] = [url] + _fallback_urls(src.get("metadata", {}) or {})
    return mapa


def _persistir_progresso(state_file: str, state: Dict[str, Any], history_list: List[str]) -> None:
    """
    Grava o que já foi entregue ANTES de a varredura terminar.

    PROPÓSITO DE NEGÓCIO:
        Container reiniciado no meio da varredura (deploy, OOM, queda do host)
        não pode fazer o ciclo seguinte repostar o que já saiu.

    INVARIANTES DO DOMÍNIO:
        - Grava dedup e history do que foi entregue até aqui.
        - NÃO grava o cache HTTP deste ciclo: `state["http_cache"]` ainda é o do
          ciclo anterior (o novo vive à parte até o fim). Gravado agora, os feeds
          ainda não processados receberiam 304 depois do restart e as notícias
          deles se perderiam. Com o cache antigo, são rebaixados de novo e o
          dedup impede a repostagem do que já saiu.

    COMPORTAMENTO EM CASO DE FALHA:
        Falha de disco é registrada por `save_json_safe` e a varredura segue:
        a gravação final tenta de novo.
    """
    save_history(history_list)
    save_json_safe(state_file, state)


async def run_scan_once(bot: discord.Client, trigger: str = "manual") -> None:
    """
    Executa um ciclo de varredura: feeds, sites oficiais, entrega e persistência.

    PROPÓSITO DE NEGÓCIO:
        Levar cada notícia nova a cada guild configurada, uma vez.

    INVARIANTES DO DOMÍNIO:
        - INV-ENTREGA-01: um link entregue numa guild não é reentregue a ela
          enquanto estiver na janela do dedup — nem depois de restart no meio do
          ciclo (`_persistir_progresso`).
        - INV-ENTREGA-02: falha de envio numa guild não tira dela a notícia
          porque OUTRA guild recebeu. O link só entra no history quando nenhuma
          guild elegível falhou; até lá fica no dedup como pendente e é retentado
          nos ciclos seguintes, dentro da janela de recência.
        - INV-ENTREGA-03: fora da janela de 7 dias só publica na primeira
          varredura de um feed nunca visto (a chave do feed no dedup é a marca).
        - A iteração é sobre uma CÓPIA do config: /dashboard ou /set_canal
          configurando guild nova durante a varredura não a interrompe mais.

    COMPORTAMENTO EM CASO DE FALHA:
        Falha isolada de feed, de guild ou de site é logada e o ciclo continua.
        Config vazio encerra sem gravar nada. Exceção inesperada sobe para o
        chamador (o loop registra); o progresso já persistido fica.
    """
    global _inicio_ultima_varredura
    if scan_lock.locked():
        log.info(f"Scan skipped (already running). Trigger: {trigger}")
        return

    async with scan_lock:
        _inicio_ultima_varredura = time.monotonic()
        log.info(f"🔎 Iniciando varredura de inteligência... (trigger={trigger})")
        config_carregado = load_config_cached({})
        if not config_carregado or not isinstance(config_carregado, dict):
            return
        # Cópia rasa: o dict em cache é o MESMO objeto que /dashboard e /set_canal
        # alteram. Iterar sobre ele com `await` no meio levantava
        # "dictionary changed size during iteration" quando uma guild nova era
        # configurada durante a varredura — antes de gravar o que já tinha saído.
        config: Dict[str, Any] = dict(config_carregado)

        sources = load_sources()
        scan_verbose(log, f"📋 [FILA] {len(sources)} fonte(s) RSS/agregada(s) carregada(s).")
        chaves_de_cache = _chaves_de_cache_por_feed(sources)
        state_file = p("state.json")
        state = load_json_safe(state_file, {})
        state.setdefault("dedup", {})
        state.setdefault("http_cache", {})
        state.setdefault("html_monitor", {})
        # Cache HTTP deste ciclo, separado do persistido: só substitui o antigo
        # no fim (ver `_persistir_progresso`).
        http_cache_ciclo: Dict[str, Any] = copy.deepcopy(state["http_cache"])

        history_list, history_set = load_history()
        # Links entregues neste ciclo por qualquer feed: o mesmo link em dois
        # feeds não sai duas vezes na mesma varredura, mesmo sem ir ao history.
        entregues_no_ciclo: Set[str] = set()
        # Links com falha de entrega em alguma guild: ficam fora do history e
        # dentro do dedup, para a retentativa só atingir quem não recebeu.
        links_pendentes: Set[str] = set()

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)

        sent_count = 0
        # Feeds cuja entrega ao Discord falhou neste ciclo. O ETag/Last-Modified
        # deles é DESCARTADO no fim: gravado, o ciclo seguinte receberia 304 e
        # nem sequer veria a notícia que não chegou a sair. "Entreguei lixo" não
        # pode contar como "entreguei".
        feeds_com_falha_de_entrega: set = set()
        cache_hits_start = stats.cache_hits_total
        feeds_failed_start = stats.feeds_failed
        feeds_vazios_start = stats.feeds_vazios
        traducoes_rejeitadas_start = stats.traducoes_rejeitadas
        traducoes_falhas_servico_start = stats.traducoes_falhas_servico
        traducoes_suspensas_start = stats.traducoes_suspensas

        async with aiohttp.ClientSession(connector=connector) as session:
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)

            async def throttled_fetch(src_obj):
                url_log = src_obj.get("url", "Desconhecida")
                scan_verbose(
                    log,
                    f"⏳ [SEMAFORO] {url_log} aguardando liberação na fila "
                    f"(máx. {MAX_CONCURRENT_FEEDS} simultâneos)...",
                )
                async with semaphore:
                    jitter = random.uniform(FEED_FETCH_JITTER_MIN, FEED_FETCH_JITTER_MAX)
                    scan_verbose(
                        log,
                        f"🎲 [JITTER] Aguardando {jitter:.2f}s antes de buscar: {url_log}",
                    )
                    await asyncio.sleep(jitter)
                    return await fetch_feed(session, src_obj, http_cache_ciclo)

            tasks_list = [throttled_fetch(src) for src in sources]
            results = await asyncio.gather(*tasks_list, return_exceptions=True)

            for result in results:
                # return_exceptions=True: uma falha isolada num feed não derruba a varredura inteira
                if isinstance(result, Exception):
                    log.error(f"Falha não tratada ao buscar feed: {type(result).__name__}: {result}")
                    continue
                if not result: continue
                # O título vem do fetcher para a sonda de fontes o poder comparar
                # com o nome configurado; aqui só interessa a URL e as entradas.
                url, entries, _titulo_do_feed = result

                # Cold start = feed NUNCA visto. É a presença da chave que conta,
                # não ter links: um feed sem post na janela fica com {} e continua
                # "visto" (prune_dedup preserva a chave).
                is_cold_start = url not in state["dedup"]
                state["dedup"].setdefault(url, {})
                entregou_neste_feed = False

                is_youtube_feed = ("youtube.com" in url or "youtu.be" in url)
                max_items = (
                    MAX_YOUTUBE_ENTRIES_PER_FEED
                    if is_youtube_feed
                    else MAX_ENTRIES_PER_FEED
                )
                if is_youtube_feed and max_items <= 0:
                    max_items = len(entries)

                limit_label = "sem limite" if (is_youtube_feed and MAX_YOUTUBE_ENTRIES_PER_FEED <= 0) else str(max_items)
                scan_verbose(
                    log,
                    f"📊 [PROCESSANDO] Até {limit_label} entradas de {len(entries)} em {url} "
                    f"(cold start: {is_cold_start})",
                )
                for entry in entries[:max_items]:
                    link = sanitize_link(entry.get("link", ""))
                    if not link or link in history_set or link in entregues_no_ciclo:
                        continue

                    # Dedup per guild (new logic)
                    if link in state["dedup"][url] and "LEGACY" in state["dedup"][url][link]:
                        continue

                    # Filter by date
                    entry_dt = parse_entry_dt(entry)
                    if not is_cold_start and not is_recent(entry_dt):
                        scan_verbose(
                            log,
                            f"⏭️ [IGNORADO] Notícia antiga ou fora da janela: {link}",
                        )
                        continue

                    posted_anywhere = False
                    falhou_em_alguma_guild = False
                    if link not in state["dedup"][url]: state["dedup"][url][link] = []

                    # Resolve a imagem 1x por notícia e reaproveita o embed por idioma
                    # entre servidores — evita fetch OpenGraph e tradução duplicados.
                    thumb = None
                    thumb_done = False
                    embeds_by_lang: Dict[str, Any] = {}

                    for gid, gdata in config.items():
                        if not isinstance(gdata, dict): continue
                        if gid in state["dedup"][url][link]: continue

                        channel_id = gdata.get("channel_id")
                        if not channel_id: continue

                        if not match_intel(
                            str(gid),
                            entry.get("title", ""),
                            entry.get("summary", ""),
                            config,
                            source_url=url,
                        ):
                            scan_verbose(
                                log,
                                f"🚫 [FILTRO] Item não passou em match_intel (guild={gid}): "
                                f"{(entry.get('title') or '')[:100]} | {link[:120]}",
                            )
                            continue

                        channel = bot.get_channel(int(channel_id))
                        if not channel: continue

                        # Notify
                        try:
                            target_lang = gdata.get("language", "en_US")
                            if target_lang not in embeds_by_lang:
                                if not thumb_done:
                                    thumb = await resolve_thumbnail(entry, session)
                                    thumb_done = True
                                embeds_by_lang[target_lang] = await create_embed(
                                    bot, entry, target_lang, config, session=session, thumbnail_url=thumb
                                )
                            embed = embeds_by_lang[target_lang]

                            is_video = any(x in link for x in ["youtube.com", "youtu.be", "twitch.tv"])
                            msg_content = link if is_video else None
                            await channel.send(content=msg_content, embed=embed)

                            if any(x in link for x in ("youtube.com", "youtu.be")):
                                title_snip = (entry.get("title") or "")[:140]
                                log.info(
                                    f"🎥 [YOUTUBE POST] guild={gid} canal={channel_id} "
                                    f"| {title_snip} | {link}"
                                )

                            state["dedup"][url][link].append(str(gid))
                            posted_anywhere = True
                            sent_count += 1
                        except Exception as e:
                            log.error(f"Error sending to guild {gid}: {e}")
                            feeds_com_falha_de_entrega.add(url)
                            falhou_em_alguma_guild = True

                    if posted_anywhere:
                        entregues_no_ciclo.add(link)
                        entregou_neste_feed = True
                    if falhou_em_alguma_guild:
                        links_pendentes.add(link)
                        log.warning(
                            f"🔁 [PENDENTE] {link} não chegou a todas as guilds; "
                            "fica fora do history e será retentado no próximo ciclo."
                        )
                    elif state["dedup"][url][link]:
                        # Entregue a todas as guilds elegíveis (agora ou em ciclo
                        # anterior): pode entrar no history.
                        history_set.add(link)
                        history_list.append(link)

                if entregou_neste_feed:
                    _persistir_progresso(state_file, state, history_list)

            # --- HTML MONITOR (Official Sites) ---
            log.info("🔎 Verificando sites oficiais (HTML Watcher)...")
            html_anterior = dict(state["html_monitor"])
            html_updates, new_html_state = await check_official_sites(state["html_monitor"])
            state["html_monitor"] = new_html_state

            # Cooldown por site: o hash muda a cada ciclo em portais com banner/ranking
            # rotativo, o que gerava um "🔄 Update" por hora sem notícia nova. Estas
            # atualizações não têm link único, então não passam pelo dedup/history dos
            # feeds — o cooldown é o que impede a repostagem.
            html_posted_at = state.setdefault("html_monitor_posted", {})
            now_ts = time.time()

            for update in html_updates:
                site_url = update.get("link", "")
                if HTML_MONITOR_COOLDOWN_SEC > 0 and site_url:
                    try:
                        last_ts = float(html_posted_at.get(site_url, 0))
                    except (TypeError, ValueError):
                        last_ts = 0.0
                    if last_ts and (now_ts - last_ts) < HTML_MONITOR_COOLDOWN_SEC:
                        restante = (HTML_MONITOR_COOLDOWN_SEC - (now_ts - last_ts)) / 3600
                        scan_verbose(
                            log,
                            f"🔕 [HTML COOLDOWN] {site_url} avisado há menos de "
                            f"{HTML_MONITOR_COOLDOWN_HOURS:.0f}h (faltam {restante:.1f}h).",
                        )
                        continue

                # Trata atualizações de HTML como entradas de feed para processamento uniforme
                # check_official_sites já retorna dicts compatíveis com create_embed
                html_sent = False
                html_tentou = False
                html_embeds_by_lang: Dict[str, Any] = {}
                for gid, gdata in config.items():
                    if not isinstance(gdata, dict): continue
                    channel_id = gdata.get("channel_id")
                    if not channel_id: continue

                    # Filtra por palavras-chave (opcional, mas recomendado)
                    if not match_intel(str(gid), update.get("title", ""), update.get("summary", ""), config):
                        continue

                    channel = bot.get_channel(int(channel_id))
                    if not channel: continue

                    html_tentou = True
                    try:
                        target_lang = gdata.get("language", "en_US")
                        # Para sites oficiais, passamos um entry fake; embed reaproveitado por idioma
                        if target_lang not in html_embeds_by_lang:
                            html_embeds_by_lang[target_lang] = await create_embed(bot, update, target_lang, config, session=session)
                        embed = html_embeds_by_lang[target_lang]
                        await channel.send(embed=embed)
                        sent_count += 1
                        html_sent = True
                    except Exception as e:
                        log.error(f"Error sending HTML update to guild {gid}: {e}")

                # Só arma o cooldown se o aviso de facto saiu para alguma guild —
                # senão um item barrado pelo filtro bloquearia o site por 24h.
                if html_sent and site_url:
                    html_posted_at[site_url] = now_ts
                elif html_tentou and site_url:
                    # Havia guild para receber e TODAS falharam: o hash novo já
                    # estava gravado, e a mudança nunca mais seria anunciada.
                    # Volta o hash anterior para o próximo ciclo detectar de novo.
                    if site_url in html_anterior:
                        state["html_monitor"][site_url] = html_anterior[site_url]
                    else:
                        state["html_monitor"].pop(site_url, None)
                    log.warning(
                        f"🔁 [HTML PENDENTE] Aviso de {site_url} falhou em todas as guilds; "
                        "hash anterior restaurado para nova tentativa."
                    )

        # Cleanup and Save
        # O cache HTTP deste ciclo substitui o persistido só agora, sem os feeds
        # que tiveram falha de entrega (e sem os fallbacks deles), para que a
        # varredura seguinte volte a receber 200 (e as entradas) em vez de 304.
        if feeds_com_falha_de_entrega:
            descartados = 0
            for url_falho in feeds_com_falha_de_entrega:
                for chave in chaves_de_cache.get(url_falho, [url_falho]):
                    if http_cache_ciclo.pop(chave, None) is not None:
                        descartados += 1
            if descartados:
                log.warning(
                    f"♻️ Cache HTTP descartado de {descartados} URL(s) de feed(s) com falha de "
                    "entrega, para a notícia poder ser retentada no próximo ciclo."
                )
        state["http_cache"] = http_cache_ciclo

        # Corta o history aos últimos HISTORY_LIMIT e alinha o dedup à mesma janela,
        # para o state.json não crescer indefinidamente (auto-poda a cada varredura).
        # Os pendentes ficam no dedup: é ele que diz quem já recebeu.
        save_history(history_list)
        keep_links = set(history_list[-HISTORY_LIMIT:]) | links_pendentes
        dedup_before, dedup_after = prune_dedup(state["dedup"], keep_links)
        if dedup_before != dedup_after:
            log.info(
                f"🧹 [AUTO-PODA] dedup do state.json: {dedup_before} → {dedup_after} links "
                f"(teto {HISTORY_LIMIT})."
            )
        save_json_safe(state_file, state)
        # Persiste o cache de tradução (evita rajada de scraping no Google após restart)
        save_translation_cache()

        stats.scans_completed += 1
        stats.news_posted += sent_count
        stats.last_scan_time = datetime.now()

        cache_hits = stats.cache_hits_total - cache_hits_start
        feeds_failed = stats.feeds_failed - feeds_failed_start
        feeds_vazios = stats.feeds_vazios - feeds_vazios_start
        traducoes_rejeitadas = stats.traducoes_rejeitadas - traducoes_rejeitadas_start
        traducoes_falhas_servico = stats.traducoes_falhas_servico - traducoes_falhas_servico_start
        traducoes_suspensas = stats.traducoes_suspensas - traducoes_suspensas_start

        # Ausência de entrega acumulada: um ciclo sem publicar é rotina; a
        # sequência é que distingue "dia parado" de "bot mudo".
        if sent_count > 0:
            stats.ciclos_sem_envio = 0
        else:
            stats.ciclos_sem_envio += 1

        veredito = avaliar_varredura(
            fontes_totais=len(sources),
            feeds_falhos=feeds_failed,
            feeds_vazios=feeds_vazios,
            enviadas=sent_count,
            cache_hits=cache_hits,
            traducoes_rejeitadas=traducoes_rejeitadas,
            ciclos_sem_envio=stats.ciclos_sem_envio,
            traducoes_falhas_servico=traducoes_falhas_servico,
            traducoes_suspensas=traducoes_suspensas,
        )
        stats.ultimo_veredito = veredito
        # Persistido no state para sobreviver ao restart: telemetria que morre com
        # o processo não serve para diagnosticar o que aconteceu de madrugada.
        state["ultimo_veredito"] = veredito
        save_json_safe(state_file, state)

        log.info(
            f"✅ Varredura concluída. (enviadas={sent_count}, cache_hits={cache_hits}, "
            f"feeds_falhos={feeds_failed}, feeds_vazios={feeds_vazios}, "
            f"traducoes_rejeitadas={traducoes_rejeitadas}, "
            f"traducoes_falhas_servico={traducoes_falhas_servico}, "
            f"traducoes_suspensas={traducoes_suspensas}, trigger={trigger})"
        )
        nivel = log.info if veredito["veredito"] == VEREDITO_OK else (
            log.warning if veredito["veredito"] == VEREDITO_ATENCAO else log.error
        )
        nivel(f"🩺 Saúde da varredura: {veredito['veredito']} — " + " | ".join(veredito["motivos"]))
        _log_next_run()

def start_scheduler(bot: discord.Client):
    @tasks.loop(minutes=LOOP_MINUTES)
    async def intelligence_gathering():
        try:
            await run_scan_once(bot, trigger="loop")
        except Exception as e:
            log.exception(f"Loop error: {e}")

    @intelligence_gathering.before_loop
    async def _before(): await bot.wait_until_ready()
    
    intelligence_gathering.start()
    log.info(
        f"🛰️ Scanner de Inteligência ativado! Ciclo: {LOOP_INTERVAL_STR} "
        f"({LOOP_MINUTES} min entre execuções do loop)."
    )
    _log_next_run()
