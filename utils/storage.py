"""
Storage utilities - JSON load/save functions.
"""
import os
import json
import logging
import shutil
from datetime import datetime
from typing import Any, Dict, Tuple, Optional

log = logging.getLogger("MaftyIntel")


def p(filename: str) -> str:
    """
    Retorna o caminho absoluto para um arquivo no diretório raiz do bot.
    
    Args:
        filename: Nome do arquivo (ex: 'config.json')
    
    Returns:
        Caminho absoluto do arquivo
    """
    return os.path.abspath(filename)


def load_json_safe(filepath: str, default: Any) -> Any:
    """
    Carrega JSON sem derrubar o bot se faltar / vazio / corrompido.
    
    Args:
        filepath: Caminho do arquivo JSON
        default: Valor padrão se falhar
    
    Returns:
        Dados do JSON ou valor padrão
    """
    try:
        if not os.path.exists(filepath):
            log.warning(f"Arquivo '{filepath}' não existe. Usando padrão.")
            return default
        if os.path.getsize(filepath) == 0:
            log.warning(f"Arquivo '{filepath}' está vazio. Usando padrão.")
            return default
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log.error(f"Erro de sintaxe JSON ao carregar '{filepath}': linha {e.lineno}, coluna {e.colno}. Usando padrão.")
        return default
    except PermissionError as e:
        log.error(f"Sem permissão para ler '{filepath}': {e}. Usando padrão.")
        return default
    except Exception as e:
        log.error(f"Falha ao carregar '{filepath}': {type(e).__name__}: {e}. Usando padrão.", exc_info=True)
        return default


def save_json_safe(filepath: str, data: Any) -> None:
    """
    Salva JSON com indentação; em erro, loga e segue.
    
    Args:
        filepath: Caminho do arquivo JSON
        data: Dados a salvar
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except PermissionError as e:
        log.error(f"Sem permissão para escrever '{filepath}': {e}")
    except OSError as e:
        log.error(f"Erro de sistema ao salvar '{filepath}': {e}")
    except TypeError as e:
        log.error(f"Dados não serializáveis em JSON ao salvar '{filepath}': {e}")
    except Exception as e:
        log.error(f"Falha inesperada ao salvar '{filepath}': {type(e).__name__}: {e}", exc_info=True)


def create_backup(filepath: str, backup_dir: str = "backups") -> Optional[str]:
    """
    Cria um backup do arquivo antes de modificações críticas.
    
    Args:
        filepath: Caminho do arquivo a fazer backup
        backup_dir: Diretório onde salvar backups
    
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
        "last_cleanup": None,
        "last_announced_hash": state.get("last_announced_hash"),
        "file_size_kb": 0
    }
    
    # Estatísticas de dedup
    dedup = state.get("dedup", {})
    if isinstance(dedup, dict):
        stats["dedup_feeds"] = len(dedup)
        stats["dedup_total_links"] = sum(
            len(links) if isinstance(links, list) else 0
            for links in dedup.values()
        )
    
    # Estatísticas de http_cache
    http_cache = state.get("http_cache", {})
    if isinstance(http_cache, dict):
        stats["http_cache_urls"] = len(http_cache)
    
    # Estatísticas de html_hashes
    html_hashes = state.get("html_hashes", {})
    if isinstance(html_hashes, dict):
        stats["html_hashes_sites"] = len(html_hashes)
    
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
    
    elif clean_type == "http_cache":
        new_state["http_cache"] = {}
        log.info("🧹 Limpeza: http_cache removido")
    
    elif clean_type == "html_hashes":
        new_state["html_hashes"] = {}
        log.info("🧹 Limpeza: html_hashes removido")
    
    elif clean_type == "tudo":
        # Limpa tudo exceto last_cleanup e last_announced_hash
        new_state["dedup"] = {}
        new_state["http_cache"] = {}
        new_state["html_hashes"] = {}
        # Mantém last_cleanup e last_announced_hash
        log.info("🧹 Limpeza: tudo removido (exceto metadados)")
    
    else:
        raise ValueError(f"Tipo de limpeza inválido: {clean_type}")
    
    return new_state, stats_before
