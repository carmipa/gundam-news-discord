"""
Storage utilities - JSON load/save functions.

Erros de I/O são tratados internamente (log + retorno de valor padrão).
Apenas clean_state() pode levantar exceção: InvalidCleanTypeError quando
clean_type não é 'dedup', 'http_cache', 'html_hashes' ou 'tudo'.
"""
import os
import json
import logging
import shutil
import tempfile
from datetime import datetime
from typing import Any, Dict, Tuple, Optional

from utils.exceptions import InvalidCleanTypeError

log = logging.getLogger("MaftyIntel")

_json_cache: Dict[str, Tuple[float, int, Any]] = {}


def p(filename: str) -> str:
    """
    Retorna o caminho absoluto para um arquivo no diretório raiz do bot.
    
    Args:
        filename: Nome do arquivo (ex: 'config.json')
    
    Returns:
        Caminho absoluto do arquivo
    """
    return os.path.abspath(filename)


def _recuperar_ultimo_bom(filepath: str, motivo: str, default: Any) -> Any:
    """Lê a última cópia íntegra de `filepath`; sem ela, devolve `default`."""
    copia = caminho_ultimo_bom(filepath)
    try:
        if os.path.exists(copia) and os.path.getsize(copia) > 0:
            with open(copia, "r", encoding="utf-8") as f:
                dados = json.load(f)
            log.error(
                f"🩹 '{filepath}' {motivo}: RECUPERADO da última cópia íntegra ({copia}). "
                "Verifique disco e o motivo da interrupção."
            )
            return dados
    except (OSError, json.JSONDecodeError) as e:
        log.error(f"Cópia de segurança '{copia}' também ilegível: {type(e).__name__}: {e}")
    log.error(f"'{filepath}' {motivo} e não há cópia íntegra. Usando padrão.")
    return default


def load_json_safe(filepath: str, default: Any) -> Any:
    """
    Carrega JSON sem derrubar o bot se faltar / vazio / corrompido.

    PROPÓSITO DE NEGÓCIO:
        Um config.json truncado por queda no meio da gravação deixava o bot mudo
        em todas as guilds, com um único aviso no log; um state.json truncado
        fazia repostar tudo. Arquivo danificado é recuperado da última cópia
        íntegra antes de cair no padrão.

    INVARIANTES DO DOMÍNIO:
        - Arquivo AUSENTE devolve o padrão (instalação nova é legítima) e não
          ressuscita cópia antiga.
        - Arquivo VAZIO ou com JSON inválido tenta `caminho_ultimo_bom` primeiro.

    COMPORTAMENTO EM CASO DE FALHA:
        Nunca levanta. Devolve os dados, a cópia recuperada (com log ERROR) ou
        `default` (com log do motivo).
    """
    try:
        if not os.path.exists(filepath):
            log.warning(f"Arquivo '{filepath}' não existe. Usando padrão.")
            return default
        if os.path.getsize(filepath) == 0:
            return _recuperar_ultimo_bom(filepath, "está vazio", default)
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        return _recuperar_ultimo_bom(
            filepath, f"tem JSON inválido (linha {e.lineno}, coluna {e.colno})", default
        )
    except PermissionError as e:
        log.error(f"Sem permissão para ler '{filepath}': {e}. Usando padrão.")
        return default
    except Exception as e:
        log.error(f"Falha ao carregar '{filepath}': {type(e).__name__}: {e}. Usando padrão.", exc_info=True)
        return default


def load_json_cached(filepath: str, default: Any) -> Any:
    """
    Carrega JSON com cache baseado em (mtime, size).
    Se o arquivo não mudou desde a última leitura, retorna valor em memória.
    """
    try:
        if not os.path.exists(filepath):
            _json_cache.pop(filepath, None)
            log.warning(f"Arquivo '{filepath}' não existe. Usando padrão.")
            return default
        if os.path.getsize(filepath) == 0:
            _json_cache.pop(filepath, None)
            log.warning(f"Arquivo '{filepath}' está vazio. Usando padrão.")
            return default

        stat = os.stat(filepath)
        cache = _json_cache.get(filepath)
        if cache and cache[0] == stat.st_mtime and cache[1] == stat.st_size:
            return cache[2]

        data = load_json_safe(filepath, default)
        _json_cache[filepath] = (stat.st_mtime, stat.st_size, data)
        return data
    except Exception as e:
        log.error(f"Falha no cache de '{filepath}': {type(e).__name__}: {e}. Usando leitura sem cache.")
        return load_json_safe(filepath, default)


def invalidate_json_cache(filepath: str) -> None:
    """Invalida o cache em memória de um arquivo JSON."""
    _json_cache.pop(filepath, None)


def load_config_cached(default: Any = None) -> Any:
    """Atalho para carregar config.json com cache."""
    if default is None:
        default = {}
    return load_json_cached(p("config.json"), default)


def save_config_safe(data: Any) -> None:
    """Atalho para salvar config.json e invalidar/atualizar cache."""
    cfg_path = p("config.json")
    save_json_safe(cfg_path, data)
    try:
        if os.path.exists(cfg_path):
            stat = os.stat(cfg_path)
            _json_cache[cfg_path] = (stat.st_mtime, stat.st_size, data)
        else:
            invalidate_json_cache(cfg_path)
    except Exception:
        invalidate_json_cache(cfg_path)


ULTIMO_BOM_SUBDIR = os.path.join("data", "ultimo-bom")


def caminho_ultimo_bom(filepath: str) -> str:
    """
    Onde fica a última cópia íntegra de `filepath`: `<dir>/data/ultimo-bom/<nome>`.

    No container, `/app/data` é um diretório montado do host (docker-compose),
    então a cópia sobrevive a restart e a recriação do container. Fica ao lado do
    arquivo, e não relativa ao diretório de trabalho, para testes com diretório
    temporário nunca escreverem na árvore do projeto.
    """
    pasta = os.path.dirname(os.path.abspath(filepath))
    return os.path.join(pasta, ULTIMO_BOM_SUBDIR, os.path.basename(filepath))


def _gravar_atomico(destino: str, texto: str) -> None:
    """
    Grava `texto` em `destino` sem nunca deixá-lo truncado por falta de disco.

    O conteúdo vai inteiro para um temporário no MESMO diretório, com fsync, e só
    então substitui o destino por `os.replace` (atômico). Se a substituição for
    recusada — o caso real é o arquivo montado individualmente pelo Docker
    (`./state.json:/app/state.json`), onde renomear sobre o ponto de montagem dá
    EBUSY —, o conteúdo já validado é copiado por cima, preservando o inode que a
    montagem exige. Nesse caminho ainda existe uma janela de milissegundos em que
    um SIGKILL deixa o destino incompleto; é para ela que existe a cópia em
    `caminho_ultimo_bom`, que `load_json_safe` usa na leitura.

    Levanta OSError se não conseguir gravar; o temporário nunca fica para trás.
    """
    pasta = os.path.dirname(os.path.abspath(destino)) or "."
    fd, tmp = tempfile.mkstemp(dir=pasta, prefix=f".{os.path.basename(destino)}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.replace(tmp, destino)
            return
        except OSError as e:
            log.debug(f"os.replace recusado para '{destino}' ({e}); gravando no lugar.")
        with open(destino, "w", encoding="utf-8") as f:
            f.write(texto)
            f.flush()
            os.fsync(f.fileno())
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError as e:
                log.warning(f"Temporário '{tmp}' não removido: {e}")


def save_json_safe(filepath: str, data: Any) -> bool:
    """
    Salva JSON de estado (config, state, history, cache de tradução).

    PROPÓSITO DE NEGÓCIO:
        Estes arquivos são a memória do bot: canais de cada guild, o que já foi
        publicado e onde. Perdê-los deixa o bot mudo (config vazio) ou provoca
        repostagem em massa (dedup vazio).

    INVARIANTES DO DOMÍNIO:
        - Serializa ANTES de tocar em disco: dado não serializável nunca trunca
          o arquivo existente.
        - Falta de disco na gravação do temporário não altera o destino.
        - Toda gravação bem-sucedida deixa também a última cópia íntegra em
          `caminho_ultimo_bom`, gravada primeiro e de forma atômica.

    COMPORTAMENTO EM CASO DE FALHA:
        Nunca levanta. Devolve False e registra em log o motivo (dado não
        serializável, permissão, disco). Devolve True quando o destino foi
        gravado — mesmo que a cópia de segurança tenha falhado (isso é avisado).
    """
    try:
        texto = json.dumps(data, indent=2, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        log.error(f"Dados não serializáveis em JSON ao salvar '{filepath}': {e}")
        return False

    copia = caminho_ultimo_bom(filepath)
    try:
        os.makedirs(os.path.dirname(copia), exist_ok=True)
        _gravar_atomico(copia, texto)
    except OSError as e:
        log.warning(f"Cópia de segurança de '{filepath}' não gravada ({type(e).__name__}: {e}).")

    try:
        _gravar_atomico(filepath, texto)
        return True
    except PermissionError as e:
        log.error(f"Sem permissão para escrever '{filepath}': {e}")
    except OSError as e:
        log.error(f"Erro de sistema ao salvar '{filepath}': {e}")
    except Exception as e:
        log.error(f"Falha inesperada ao salvar '{filepath}': {type(e).__name__}: {e}", exc_info=True)
    return False


def create_backup(filepath: str, backup_dir: str = os.path.join("data", "backups")) -> Optional[str]:
    """
    Cria um backup do arquivo antes de modificações críticas.
    
    Args:
        filepath: Caminho do arquivo a fazer backup
        backup_dir: Diretório onde salvar backups (padrão data/backups: no
            container é o diretório montado do host, sobrevive à recriação)
    
    Returns:
        Caminho do arquivo de backup criado ou None se falhar
    """
    try:
        if not os.path.exists(filepath):
            log.warning(f"Arquivo '{filepath}' não existe para backup.")
            return None
        
        # Cria diretório de backups se não existir
        os.makedirs(backup_dir, exist_ok=True)
        
        # Nome do backup com timestamp
        filename = os.path.basename(filepath)
        name, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{name}_backup_{timestamp}{ext}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copia arquivo
        shutil.copy2(filepath, backup_path)
        
        log.info(f"✅ Backup criado: {backup_path}")
        return backup_path
        
    except Exception as e:
        log.error(f"Falha ao criar backup de '{filepath}': {type(e).__name__}: {e}", exc_info=True)
        return None


def get_state_stats(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Obtém estatísticas do state.json.
    
    Args:
        state: Dicionário do state.json
    
    Returns:
        Dicionário com estatísticas
    """
    stats = {
        "dedup_feeds": 0,
        "dedup_total_links": 0,
        "http_cache_urls": 0,
        "html_hashes_sites": 0,
        "html_cooldown_sites": 0,
        "last_cleanup": None,
        "last_announced_hash": state.get("last_announced_hash"),
        "file_size_kb": 0
    }
    
    # Estatísticas de dedup
    dedup = state.get("dedup", {})
    if isinstance(dedup, dict):
        stats["dedup_feeds"] = len(dedup)
        stats["dedup_total_links"] = sum(
            len(links) if isinstance(links, (list, dict)) else 0
            for links in dedup.values()
        )
    
    # Estatísticas de http_cache
    http_cache = state.get("http_cache", {})
    if isinstance(http_cache, dict):
        stats["http_cache_urls"] = len(http_cache)
    
    # Estatísticas do monitor de sites HTML.
    # O engine grava em "html_monitor"; "html_hashes" é a chave legada. Contamos a real.
    html_data = state.get("html_monitor")
    if not isinstance(html_data, dict) or not html_data:
        html_data = state.get("html_hashes", {})
    if isinstance(html_data, dict):
        stats["html_hashes_sites"] = len(html_data)

    # Cooldown de aviso por site (html_monitor_posted): entra nas estatísticas
    # para o preview do /clean_state não esconder estado que a limpeza vai apagar.
    html_cooldown = state.get("html_monitor_posted", {})
    if isinstance(html_cooldown, dict):
        stats["html_cooldown_sites"] = len(html_cooldown)

    # Última limpeza
    last_cleanup = state.get("last_cleanup", 0)
    if last_cleanup:
        try:
            cleanup_dt = datetime.fromtimestamp(last_cleanup)
            stats["last_cleanup"] = cleanup_dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            pass
    
    return stats


def clean_state(state: Dict[str, Any], clean_type: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Limpa partes específicas do state.json.
    
    Args:
        state: Estado atual do state.json
        clean_type: Tipo de limpeza ('dedup', 'http_cache', 'html_hashes', 'tudo')
    
    Returns:
        Tupla (novo_state, stats_antes)
    """
    stats_before = get_state_stats(state)
    new_state = state.copy()
    if clean_type == "dedup":
        new_state["dedup"] = {}
        log.info("🧹 Limpeza: dedup removido")
        # Também zera o histórico global legado (history.json)
        save_json_safe(p("history.json"), [])
        log.info("🧹 Limpeza: history.json zerado")
    
    elif clean_type == "http_cache":
        new_state["http_cache"] = {}
        log.info("🧹 Limpeza: http_cache removido")
    
    elif clean_type == "html_hashes":
        # Limpa a chave real (html_monitor) e a legada (html_hashes) por segurança.
        # html_monitor_posted (cooldown de aviso por site) TEM de ir junto: sem os
        # hashes, o próximo ciclo re-inicializa cada site e a deteção seguinte é
        # legítima — mas um cooldown sobrevivente suprimiria esse aviso por 24h.
        new_state["html_monitor"] = {}
        new_state["html_hashes"] = {}
        new_state["html_monitor_posted"] = {}
        log.info("🧹 Limpeza: html_monitor/html_hashes/cooldown removido")

    elif clean_type == "tudo":
        # Limpa tudo exceto last_cleanup e last_announced_hash
        new_state["dedup"] = {}
        new_state["http_cache"] = {}
        new_state["html_monitor"] = {}
        new_state["html_hashes"] = {}
        new_state["html_monitor_posted"] = {}
        save_json_safe(p("history.json"), [])
        # Mantém last_cleanup e last_announced_hash
        log.info("🧹 Limpeza: tudo removido (exceto metadados), incluindo history.json")
    
    else:
        raise InvalidCleanTypeError(f"Tipo de limpeza inválido: {clean_type}. Use: dedup, http_cache, html_hashes, tudo.")
    
    log.info(
        f"🧹 Limpeza concluída: tipo={clean_type} | antes: dedup={stats_before['dedup_total_links']} links, "
        f"http_cache={stats_before['http_cache_urls']} URLs, html_hashes={stats_before['html_hashes_sites']} sites"
    )
    return new_state, stats_before
