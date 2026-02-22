import subprocess
import logging

log = logging.getLogger("MaftyIntel")

def get_git_changes():
    """
    Retrieves the last commit hash (short) and message.
    Returns a string formatted as 'hash - message', or a fallback message on failure.
    """
    try:
        # Puxa o Ãºltimo comentÃ¡rio de commit e o hash curto
        cmd = "git log -1 --pretty=format:'%h - %s'"
        # stderr=subprocess.DEVNULL hides git errors if .git is missing
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
        # Remove as aspas simples extras que o format pode trazer dependendo do shell
        return output.replace("'", "")
    except Exception as e:
        log.debug(f"Git info fetch failed: {e}")
        return "Maintenance Update (No Git Info)"

def get_current_hash():
    """
    Returns just the short hash for comparison state.
    """
    try:
        cmd = "git log -1 --pretty=format:'%h'"
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip().replace("'", "")
    except Exception as e:
        log.debug(f"Falha ao obter hash do Git: {e}")
        return None


def get_commits_since(last_announced_hash: str | None, max_commits: int = 15) -> list[str]:
    """
    Retorna os commits desde o último anúncio (ou os últimos N commits).
    Cada item é "hash - mensagem" para exibir no anúncio de atualização.
    """
    fmt = "%h - %s"
    try:
        if last_announced_hash and last_announced_hash.strip():
            out = subprocess.check_output(
                ["git", "log", f"{last_announced_hash}..HEAD", f"--pretty=format:{fmt}"],
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace"
            ).strip()
        else:
            out = subprocess.check_output(
                ["git", "log", f"-{max_commits}", f"--pretty=format:{fmt}"],
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace"
            ).strip()
        if not out:
            out = subprocess.check_output(
                ["git", "log", "-1", f"--pretty=format:{fmt}"],
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace"
            ).strip()
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        return lines if lines else [get_git_changes()]
    except Exception as e:
        log.debug(f"get_commits_since failed: {e}")
        return [get_git_changes()]
