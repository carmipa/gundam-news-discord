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
    except:
        return None
