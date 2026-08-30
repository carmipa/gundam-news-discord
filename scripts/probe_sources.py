"""
Sonda de saúde de fontes — usa o CAMINHO REAL deste bot, não um cliente HTTP paralelo.

PROPÓSITO DE NEGÓCIO:
    Responder, com evidência colável, se cada fonte do catálogo ainda rende
    notícia. Fonte morta em silêncio é a falha mais comum deste tipo de bot: ela
    responde 200, devolve zero entradas ou conteúdo congelado, e ninguém nota
    porque "0 notícias hoje" parece um dia calmo. Num bot irmão foram 20 de 64
    fontes mortas sem que o resumo da varredura acusasse uma única.

INVARIANTES DO DOMÍNIO:
  1. Sonda pelo `fetch_feed` / `fetch_page_hash` DESTE bot — o mesmo
     `validate_url`, o mesmo `user_agent` por fonte (a Natalie devolve 405 a UA
     de navegador), os mesmos fallbacks, o mesmo throttle por host e o mesmo
     parser. Sonda com cliente próprio mede outra coisa e aprova o que a
     produção recusa.
  2. `http_cache` vazio de propósito: com o cache real, fonte saudável
     responderia 304 e a sonda não veria entrada nenhuma — leitura
     indistinguível de fonte morta.
  3. O TÍTULO do feed é sempre impresso ao lado do nome configurado. Fonte
     trocada responde 200 com itens recentes; só o título denuncia.
  4. DOIS CRITÉRIOS, porque este catálogo tem duas naturezas. Os ~64 feeds
     (RSS/YouTube/Reddit/tracker) medem-se por entradas e idade. Os ~120
     `official_sites` são páginas institucionais vigiadas por hash — medi-las
     com critério de feed produziria 120 falhas falsas. Foi exatamente esse o
     engano cometido num bot irmão, com 29 sites.
  5. A sonda só vale depois da CALIBRAÇÃO: um controle positivo que TEM de
     passar e um negativo que TEM de reprovar. Instrumento que nunca foi visto
     dizendo NÃO não prova nada quando diz SIM.
  6. Imprime o volume PÓS-FILTRO — quantas entradas passariam no `match_intel`.
     Sem isso, admitir fonte nova é palpite: um feed com 100 itens dos quais
     nenhum é sobre Gundam custa banda e não rende nada.

COMPORTAMENTO EM CASO DE FALHA: três estados de saída, nunca dois.
  0 = PASSOU        todas as fontes sondadas estão saudáveis
  1 = REPROVOU      pelo menos uma está doente
  2 = NÃO VERIFICOU calibração falhou ou não havia alvo — não é aprovação nem
                    reprovação

Uso:
    python scripts/probe_sources.py --feeds
    python scripts/probe_sources.py --sites
    python scripts/probe_sources.py --catalogo --json /tmp/sonda.json
    python scripts/probe_sources.py https://exemplo.com/feed
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import aiohttp  # noqa: E402
import certifi  # noqa: E402
import httpx  # noqa: E402

from core.filters import match_intel  # noqa: E402
from core.html_monitor import fetch_page_hash  # noqa: E402
from core.scanner.fetcher import fetch_feed, load_sources  # noqa: E402
from core.scanner.processor import parse_entry_dt  # noqa: E402
from utils.storage import load_json_safe, p  # noqa: E402

IDADE_MAXIMA_DIAS = 180

# Concorrência BAIXA de propósito. A sonda é ferramenta de diagnóstico: pode ser
# lenta, mas não pode contaminar o que mede.
#
# Medido em 2026-08-30, e da forma mais didática possível — por engano meu: três
# sondagens seguidas do catálogo completo esgotaram o orçamento do YouTube para o
# IP do VPS, e os feeds passaram a devolver `Error 404 (Not Found)!!1`. Um canal
# que minutos antes tinha respondido "SUNRISE Music" passou a dar zero entradas.
# A sonda estava a produzir a doença que dizia estar a medir.
#
# Consequência prática, e não é detalhe: resultado do YouTube logo depois de uma
# sondagem completa NÃO é confiável. Se muitos canais aparecerem mortos de uma
# vez, espere e repita antes de mexer no catálogo — desativar fonte saudável por
# leitura contaminada é pior que não ter sondado.
CONCORRENCIA = 2

# Pausa entre lotes, pelo mesmo motivo.
PAUSA_ENTRE_PEDIDOS_SEG = 0.7

# Controles. Positivo: feed grande e estável, já no catálogo, que tem de passar.
# Negativo: channel_id sintaticamente válido e inexistente — a mesma forma dos
# IDs corrompidos que um bot irmão carregou durante meses sem notar.
CONTROLE_POSITIVO = "https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us"
CONTROLE_NEGATIVO = (
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCzzzzzzzzzzzzzzzzzzzzzz"
)
# Controle do modo SITES: página que existe e responde 200 com corpo.
CONTROLE_POSITIVO_SITE = "https://gundam-official.com/"
CONTROLE_NEGATIVO_SITE = "https://gundam-official.com/pagina-que-nao-existe-sonda"

# Config sintética para medir o volume pós-filtro: uma guild que aceita tudo, para
# a contagem refletir o portão Gundam e não a escolha de categorias de ninguém.
_CONFIG_SONDA = {"__sonda__": {"channel_id": 1, "filters": ["todos"]}}


def chave_de_comparacao(texto: str) -> str:
    """
    Normaliza um título para comparar com o nome configurado no catálogo.

    PROPÓSITO DE NEGÓCIO:
        Apanhar fonte trocada — o defeito em que a URL responde 200 com itens
        recentes, mas de outro sítio, e só o título denuncia.

    INVARIANTES DO DOMÍNIO:
        - Ignora o que não distingue fonte: maiúsculas, espaços (inclusive o
          ideográfico U+3000, comum em títulos japoneses), hífen, travessão,
          parênteses e pontuação. Comparar as strings cruas produziu TRÊS falsos
          positivos num bot irmão, todos por pontuação.
        - Alarme falso gasta a atenção de quem lê e ensina a ignorar o aviso
          verdadeiro; na dúvida, calar é melhor.

    COMPORTAMENTO EM CASO DE FALHA:
        Entrada que não for `str` devolve string vazia, e o chamador não emite
        aviso nenhum.
    """
    if not isinstance(texto, str):
        return ""
    fora = " \t　-–—()[]｜|:：・.,'\"!?＆&"
    return "".join(c for c in texto.lower() if c not in fora)


def _tem_cjk(texto: str) -> bool:
    """True se o texto contém kana, kanji ou largura total."""
    return any("　" <= c <= "鿿" or "＀" <= c <= "￯" for c in texto)


# Limiar de similaridade abaixo do qual a sonda avisa que o título diverge.
#
# CALIBRADO contra os 63 pares reais do catálogo em 2026-08-30, não escolhido a
# gosto. A primeira versão comparava por substring e acusou 24 de 64 — quase
# todos falsos, por ordem trocada ("Tokyo Toshokan – Gundam" contra "gundam -
# Tokyo Toshokan") ou por o título ser descritivo ("r/Gunpla – News flair" contra
# "Gunpla: search results - flair:News"). Alarme falso gasta a atenção de quem lê.
#
# Com trigramas e este limiar sobram 14, dos quais 11 são ACHADOS legítimos: o
# catálogo guarda canais do YouTube com nome de posição ("Canal YT – UCPjm") em
# vez do nome real, e a sonda revela o verdadeiro. Os restantes 3 são falsos
# positivos aceites conscientemente: acrónimo ("r/GBO2" contra "Gundam Battle
# Operation 2") e descrição longa do subreddit.
LIMIAR_DIVERGENCIA = 0.15


def _trigramas(texto: str) -> set:
    return {texto[i:i + 3] for i in range(max(0, len(texto) - 2))} or {texto}


def _similaridade(a: str, b: str) -> float:
    """Jaccard sobre trigramas: tolera ordem trocada e sufixo descritivo."""
    ta, tb = _trigramas(a), _trigramas(b)
    return len(ta & tb) / max(1, len(ta | tb))


@dataclass
class Resultado:
    url: str
    nome_configurado: str
    titulo: str
    tipo: str  # "feed" ou "site"
    entradas: int
    pos_filtro: int
    idade_dias: Optional[int]
    saudavel: bool
    motivo: str

    def diverge(self) -> bool:
        """
        True só quando a divergência de título é INFORMATIVA.

        Comparar títulos em alfabetos diferentes não diz nada: metade deste
        catálogo é japonesa e o `sources.json` guarda o nome em inglês. A
        primeira versão acusou `ガンダムベース` contra "Gundam Base" — o mesmo
        site, escrito nas duas línguas. Alarme falso gasta a atenção de quem lê
        e ensina a ignorar o aviso verdadeiro; por isso, quando um lado é CJK e
        o outro é latino, a sonda cala-se.

        Continua a acusar o que interessa: nome e título ambos latinos que não
        se contêm ("Gundam Base" respondendo "Anime Corner"), que é a forma real
        de fonte trocada.
        """
        a = chave_de_comparacao(self.titulo)
        b = chave_de_comparacao(self.nome_configurado)
        if not a or not b:
            return False
        if _tem_cjk(a) != _tem_cjk(b):
            return False
        if a in b or b in a:
            return False
        return _similaridade(a, b) < LIMIAR_DIVERGENCIA

    def linha(self) -> str:
        marca = "OK   " if self.saudavel else "FALHA"
        idade = f"{self.idade_dias}d" if self.idade_dias is not None else "-"
        aviso = "  <-- TITULO DIVERGE DO NOME CONFIGURADO" if self.diverge() else ""
        corpo = (
            f"[{marca}] {self.nome_configurado}\n"
            f"         {self.url}\n"
        )
        if self.tipo == "feed":
            corpo += (
                f"         entradas={self.entradas} pos_filtro={self.pos_filtro} "
                f"recente={idade} titulo={self.titulo!r}{aviso}"
            )
        else:
            corpo += f"         titulo={self.titulo!r}{aviso}"
        if not self.saudavel:
            corpo += f"\n         motivo: {self.motivo}"
        return corpo


def _nome_por_url() -> Dict[str, str]:
    """Mapa url -> name declarado no sources.json, para todas as secções."""
    bruto = load_json_safe(p("sources.json"), {})
    saida: Dict[str, str] = {}
    if not isinstance(bruto, dict):
        return saida
    for bloco in bruto.values():
        if not isinstance(bloco, list):
            continue
        for item in bloco:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                saida[item["url"].strip()] = item.get("name") or item["url"].strip()
    return saida


def urls_de_sites() -> List[str]:
    """URLs vigiadas pelo HTML Monitor (respeitando `enabled: false`)."""
    from core.html_monitor import _html_monitor_urls_from_sources

    bruto = load_json_safe(p("sources.json"), {})
    return _html_monitor_urls_from_sources(bruto if isinstance(bruto, dict) else {})


async def sondar_feed(session, fonte: Dict[str, Any], nomes: Dict[str, str]) -> Resultado:
    """Sonda um feed pelo caminho real do bot, com cache vazio (invariante 2)."""
    url = fonte["url"]
    nome = nomes.get(url) or fonte.get("metadata", {}).get("name") or url

    resultado = await fetch_feed(session, fonte, {})

    if resultado is None:
        return Resultado(
            url, nome, "", "feed", 0, 0, None, False,
            "o fetch do próprio bot desistiu (rede, status != 200 após retries, "
            "SSRF, ou 304 inesperado com cache vazio)",
        )

    _, entradas, titulo = resultado

    if not entradas:
        return Resultado(
            url, nome, titulo, "feed", 0, 0, None, False,
            "200 sem entradas (feed descontinuado, bloqueio parcial, ou HTML no lugar de XML)",
        )

    agora = datetime.now(timezone.utc)
    idades = []
    for e in entradas:
        dt = parse_entry_dt(e)
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        idades.append((agora - dt).days)

    # Volume pós-filtro (invariante 6): quantas entradas passariam o portão Gundam.
    pos_filtro = sum(
        1 for e in entradas
        if match_intel(
            "__sonda__",
            e.get("title", ""),
            e.get("summary", ""),
            _CONFIG_SONDA,
            source_url=url,
        )
    )

    if not idades:
        return Resultado(
            url, nome, titulo, "feed", len(entradas), pos_filtro, None, False,
            "nenhuma entrada tem data legível — o scanner não sabe se são recentes",
        )

    recente = min(idades)
    if recente > IDADE_MAXIMA_DIAS:
        return Resultado(
            url, nome, titulo, "feed", len(entradas), pos_filtro, recente, False,
            f"congelado: item mais recente com {recente} dias (máx {IDADE_MAXIMA_DIAS})",
        )

    return Resultado(
        url, nome, titulo, "feed", len(entradas), pos_filtro, recente, True, ""
    )


async def sondar_site(client, url: str, nomes: Dict[str, str]) -> Resultado:
    """
    Sonda uma página do HTML Monitor pelo caminho real dela.

    Critério DIFERENTE do de feed, de propósito: página institucional não tem
    entradas nem datas. Saudável = responde 200 e rende texto para o hash.
    """
    nome = nomes.get(url) or url
    _, titulo, page_hash = await fetch_page_hash(client, url)

    if not page_hash:
        return Resultado(
            url, nome, titulo, "site", 0, 0, None, False,
            "o monitor do próprio bot não conseguiu hash (status != 200, rede, DNS ou SSRF)",
        )
    return Resultado(url, nome, titulo, "site", 0, 0, None, True, "")


async def _sondar_feeds(fontes: List[Dict[str, Any]], nomes) -> List[Resultado]:
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    sem = asyncio.Semaphore(CONCORRENCIA)
    conn = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=conn) as session:
        async def _uma(f):
            async with sem:
                r = await sondar_feed(session, f, nomes)
                await asyncio.sleep(PAUSA_ENTRE_PEDIDOS_SEG)
                return r
        return list(await asyncio.gather(*[_uma(f) for f in fontes]))


async def _sondar_sites(urls: List[str], nomes) -> List[Resultado]:
    from core.html_monitor import MAX_CONCURRENT_FEEDS

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    sem = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)
    async with httpx.AsyncClient(
        headers=headers, timeout=30.0, verify=certifi.where()
    ) as client:
        async def _uma(u):
            async with sem:
                return await sondar_site(client, u, nomes)
        return list(await asyncio.gather(*[_uma(u) for u in urls]))


async def calibrar(modo_sites: bool) -> tuple[bool, str]:
    """
    Prova que a sonda sabe dizer SIM e sabe dizer NÃO, antes de qualquer veredito.

    Sem isto, um "todas saudáveis" é indistinguível de um instrumento cego. Foi
    assim que uma guarda de um bot irmão passou meses verde varrendo um
    diretório inexistente.
    """
    nomes = _nome_por_url()

    fontes = [
        {"url": CONTROLE_POSITIVO, "metadata": {}},
        {"url": CONTROLE_NEGATIVO, "metadata": {}},
    ]
    positivo, negativo = await _sondar_feeds(fontes, nomes)

    if not positivo.saudavel:
        return False, (
            f"controle POSITIVO reprovou ({CONTROLE_POSITIVO}: {positivo.motivo}). "
            "A sonda, a rede ou o caminho de fetch do bot está quebrado — o "
            "veredito sobre as outras fontes não vale."
        )
    if negativo.saudavel:
        return False, (
            f"controle NEGATIVO passou ({CONTROLE_NEGATIVO}). A sonda não sabe "
            "dizer NÃO; qualquer 'OK' abaixo seria indistinguível de cegueira."
        )

    explicacao = (
        f"feed: positivo OK ({positivo.entradas} entradas, {positivo.pos_filtro} "
        f"pós-filtro, mais recente {positivo.idade_dias}d) | negativo reprovou "
        f"como esperado"
    )

    if modo_sites:
        s_pos, s_neg = await _sondar_sites(
            [CONTROLE_POSITIVO_SITE, CONTROLE_NEGATIVO_SITE], nomes
        )
        if not s_pos.saudavel:
            return False, (
                f"{explicacao}\n             site: controle POSITIVO reprovou "
                f"({CONTROLE_POSITIVO_SITE}: {s_pos.motivo})"
            )
        if s_neg.saudavel:
            return False, (
                f"{explicacao}\n             site: controle NEGATIVO passou "
                f"({CONTROLE_NEGATIVO_SITE}) — a sonda de sites não sabe dizer NÃO"
            )
        explicacao += "\n             site: positivo OK | negativo reprovou como esperado"

    return True, explicacao


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sonda de saúde das fontes do Gundam News Bot"
    )
    ap.add_argument("urls", nargs="*", help="URLs de feed a sondar avulso")
    ap.add_argument("--feeds", action="store_true", help="sonda os feeds do catálogo")
    ap.add_argument("--sites", action="store_true", help="sonda os official_sites (HTML Monitor)")
    ap.add_argument("--catalogo", action="store_true", help="feeds + sites")
    ap.add_argument("--json", help="grava o resultado bruto neste caminho")
    args = ap.parse_args()

    quer_feeds = args.feeds or args.catalogo or bool(args.urls)
    quer_sites = args.sites or args.catalogo

    nomes = _nome_por_url()

    fontes: List[Dict[str, Any]] = []
    if args.feeds or args.catalogo:
        fontes.extend(load_sources())
    fontes.extend({"url": u, "metadata": {}} for u in args.urls)

    sites: List[str] = urls_de_sites() if quer_sites else []

    if not fontes and not sites:
        print(
            "NÃO VERIFICOU: nenhum alvo. Use --feeds, --sites, --catalogo ou passe URLs.",
            file=sys.stderr,
        )
        return 2

    # Catálogo vazio é ANOMALIA, nunca OK: é exatamente a falha que esta sonda
    # existe para apanhar. Um detector que reporta catálogo vazio como saudável
    # tem um buraco no sítio onde devia enxergar.
    if (args.feeds or args.catalogo) and not fontes:
        print("NÃO VERIFICOU: o catálogo de feeds veio VAZIO.", file=sys.stderr)
        return 2
    if quer_sites and not sites and not quer_feeds:
        print("NÃO VERIFICOU: a lista de sites veio VAZIA.", file=sys.stderr)
        return 2

    calibrada, explicacao = asyncio.run(calibrar(modo_sites=quer_sites))
    print(f"[calibração] {explicacao}\n")
    if not calibrada:
        print("NÃO VERIFICOU: instrumento não calibrado.", file=sys.stderr)
        return 2

    resultados: List[Resultado] = []
    if fontes:
        print(f"===== FEEDS ({len(fontes)}) =====")
        r = asyncio.run(_sondar_feeds(fontes, nomes))
        for x in r:
            print(x.linha())
        resultados.extend(r)

    if sites:
        print(f"\n===== SITES DO HTML MONITOR ({len(sites)}) =====")
        r = asyncio.run(_sondar_sites(sites, nomes))
        for x in r:
            print(x.linha())
        resultados.extend(r)

    doentes = [x for x in resultados if not x.saudavel]
    divergentes = [x for x in resultados if x.saudavel and x.diverge()]

    print(f"\nresumo: {len(resultados) - len(doentes)}/{len(resultados)} saudáveis")
    if divergentes:
        print(f"        {len(divergentes)} com título divergente do nome configurado")
    feeds = [x for x in resultados if x.tipo == "feed" and x.saudavel]
    if feeds:
        print(
            f"        volume pós-filtro: {sum(x.pos_filtro for x in feeds)} itens "
            f"relevantes de {sum(x.entradas for x in feeds)} recolhidos"
        )

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([asdict(x) for x in resultados], f, indent=2, ensure_ascii=False)
        print(f"json: {args.json}")

    return 1 if doentes else 0


if __name__ == "__main__":
    sys.exit(main())
