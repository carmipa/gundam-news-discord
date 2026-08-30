"""
Processor module - Handles link sanitization, date parsing, and deduplication.
"""
import logging
import time
from datetime import datetime, timezone
from dateutil import parser as dtparser
from typing import List, Set, Tuple, Dict, Any, Optional
from urllib.parse import urlparse, urlunparse

from utils.storage import p, load_json_safe, save_json_safe
from settings import HISTORY_LIMIT

log = logging.getLogger("MaftyIntel.scanner")

def load_history() -> Tuple[List[str], Set[str]]:
    h = load_json_safe(p("history.json"), [])
    if not isinstance(h, list): h = []
    h = [x for x in h if isinstance(x, str)]
    return h, set(h)

def save_history(history_list: List[str], limit: int = HISTORY_LIMIT) -> None:
    save_json_safe(p("history.json"), history_list[-limit:])


def prune_dedup(dedup: Dict[str, Any], keep_links: Set[str]) -> Tuple[int, int]:
    """
    Auto-poda do dedup do state.json para não crescer indefinidamente.

    Mantém apenas os links ainda presentes em `keep_links` (a janela dos últimos
    HISTORY_LIMIT links enviados, definida pelo history). Assim o dedup acompanha
    o teto do history.json: links de fato postados continuam protegidos contra
    repostagem, enquanto o lixo (links vistos mas filtrados, que nunca entram no
    history) é descartado. Feeds que ficarem sem links são removidos.

    Modifica `dedup` in-place e retorna (total_antes, total_depois).
    """
    if not isinstance(dedup, dict):
        return 0, 0

    before = sum(len(v) for v in dedup.values() if isinstance(v, dict))

    for url in list(dedup.keys()):
        links = dedup.get(url)
        if not isinstance(links, dict):
            del dedup[url]
            continue
        for link in list(links.keys()):
            if link not in keep_links:
                del links[link]
        if not links:
            del dedup[url]

    after = sum(len(v) for v in dedup.values() if isinstance(v, dict))
    return before, after

def sanitize_link(link: str) -> str:
    """Removes tracking params while keeping essential ones."""
    try:
        parsed = urlparse(link)
        if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
            return link
            
        q_pairs = parsed.query.split('&')
        cleaned_pairs = [
            pair for pair in q_pairs 
            if not pair.startswith(('utm_', 'ref', 'source', 'fbclid', 'timestamp'))
            and pair 
        ]
        new_query = '&'.join(cleaned_pairs)
        
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    except Exception as e:
        # Link não parseável volta intacto: melhor publicar com parâmetros de
        # rastreio do que perder a notícia. O motivo fica no log.
        log.debug(f"Falha ao sanitizar link {link!r}: {type(e).__name__}: {e}")
        return link

def parse_entry_dt(entry: Any) -> Optional[datetime]:
    """
    Extrai a data de publicação de uma entrada de feed.

    PROPÓSITO DE NEGÓCIO:
        Alimenta `is_recent`, que impede o bot de publicar notícia velha como se
        fosse nova — quando um feed reordena, republica ou muda de servidor.

    INVARIANTES DO DOMÍNIO:
        - `published_parsed` vem PRIMEIRO. É o campo que o feedparser já
          normalizou a partir de qualquer formato (RFC 822, ISO 8601, RFC 3339),
          e é o mais confiável que existe na entrada.
        - O campo de texto é só reserva, e é lido com o parser TOLERANTE
          (`dtparser.parse`), não com `isoparse`.
        - Sempre devolve datetime com fuso (UTC quando a origem não diz), para o
          chamador nunca comparar aware com naive.

    COMPORTAMENTO EM CASO DE FALHA:
        Devolve None, e `is_recent(None)` deixa a notícia passar — deliberado:
        melhor publicar do que descartar por causa de um campo de data mal
        formado. O motivo fica em log de debug.

    Histórico do defeito (2026-08-30): a versão anterior tentava
    `dtparser.isoparse` no campo de TEXTO primeiro. `isoparse` aceita apenas ISO
    8601 e levanta em RFC 822 — que é o formato PADRÃO do RSS. A exceção era
    capturada e a função devolvia None **sem nunca chegar ao
    `published_parsed`**, que estava ali, correto, o tempo todo. Resultado: como
    `is_recent(None)` é True, a janela de 7 dias estava desligada para todos os
    feeds RSS clássicos, funcionando só nos Atom/YouTube. Foi o controle
    positivo da sonda de fontes que denunciou.
    """
    # 1. O campo já normalizado pelo feedparser.
    st = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if st:
        try:
            return datetime(*st[:6], tzinfo=timezone.utc)
        except Exception as e:
            log.debug(f"published_parsed inválido: {type(e).__name__}: {e}")

    # 2. Reserva: o texto cru, com parser tolerante a RFC 822 e ISO 8601.
    s = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if s:
        try:
            dt = dtparser.parse(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception as e:
            log.debug(f"Data da entrada ilegível ({s!r}): {type(e).__name__}: {e}")

    return None

def is_recent(entry_dt: Optional[datetime], days_limit: int = 7) -> bool:
    if not entry_dt: return True
    now = datetime.now(entry_dt.tzinfo) if entry_dt.tzinfo else datetime.now()
    return (now - entry_dt).days <= days_limit
