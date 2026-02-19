
import logging
import sys
from colorama import init, Fore, Style

# Inicializa colorama para funcionar no Windows
# Inicializa colorama para funcionar no Windows e forçar cores
init(autoreset=True, strip=False)

class SecurityFilter(logging.Filter):
    """
    Filtro de segurança que sanitiza mensagens de log para remover informações sensíveis.
    """
    def filter(self, record):
        # Importação local para evitar circular
        try:
            from utils.security import sanitize_log_message
            
            # Sanitiza a mensagem antes de ser logada
            if hasattr(record, 'msg') and isinstance(record.msg, str):
                record.msg = sanitize_log_message(record.msg)
            elif hasattr(record, 'getMessage'):
                # Para mensagens formatadas
                original_msg = record.getMessage()
                record.msg = sanitize_log_message(original_msg)
        except ImportError:
            # Se não conseguir importar, apenas passa adiante sem sanitizar
            pass
        return True


class ColorfulFormatter(logging.Formatter):
    """
    Formatador de logs customizado com cores, ícones e traceback colorido.
    """

    # Ícones e cores para cada nível
    FORMATS = {
        logging.DEBUG:    (Fore.CYAN, "🐛"),
        logging.INFO:     (Fore.GREEN, "ℹ️"),
        logging.WARNING:  (Fore.YELLOW, "⚠️"),
        logging.ERROR:    (Fore.RED, "❌"),
        logging.CRITICAL: (Fore.RED + Style.BRIGHT, "🔥")
    }

    def format(self, record):
        color, icon = self.FORMATS.get(record.levelno, (Fore.WHITE, ""))
        
        # Formato: DATA - [NIVEL] ICON MENSAGEM
        # Agora a mensagem inteira segue a cor do nível
        log_fmt = f"{Fore.LIGHTBLACK_EX}%(asctime)s{Style.RESET_ALL} - [{color}%(levelname)s{Style.RESET_ALL}] {icon} {color}%(message)s{Style.RESET_ALL}"
        
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        message = formatter.format(record)
        
        # Adiciona traceback colorido se existir
        if record.exc_info:
            # Formata o traceback com cores
            exc_text = self.formatException(record.exc_info)
            # Colore o traceback em vermelho claro para erros
            if record.levelno >= logging.ERROR:
                exc_text = f"{Fore.RED}{exc_text}{Style.RESET_ALL}"
            else:
                exc_text = f"{Fore.YELLOW}{exc_text}{Style.RESET_ALL}"
            message += "\n" + exc_text
        
        return message
    
    def formatException(self, exc_info):
        """Formata exception com cores melhoradas."""
        import traceback
        lines = traceback.format_exception(*exc_info)
        
        # Colore diferentes partes do traceback
        colored_lines = []
        for line in lines:
            if "File" in line and "line" in line:
                # Linhas de arquivo em ciano
                colored_lines.append(f"{Fore.CYAN}{line.rstrip()}{Style.RESET_ALL}")
            elif "Error" in line or "Exception" in line:
                # Mensagens de erro em vermelho brilhante
                colored_lines.append(f"{Fore.RED + Style.BRIGHT}{line.rstrip()}{Style.RESET_ALL}")
            else:
                # Código em amarelo claro
                colored_lines.append(f"{Fore.LIGHTYELLOW_EX}{line.rstrip()}{Style.RESET_ALL}")
        
        return "\n".join(colored_lines)

def setup_logger(name="MaftyIntel", log_file="logs/bot.log", level=logging.INFO):
    """
    Configura e retorna um logger com handlers de arquivo (rotativo) e console (colorido).
    """
    
    # Cria o logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evita duplicação de handlers se chamar setup mais de uma vez
    if logger.hasHandlers():
        logger.handlers.clear()

    # --- File Handler (Sem cores ANSI, formato padrão) ---
    from logging.handlers import RotatingFileHandler
    import os
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=5*1024*1024, # 5MB
        backupCount=3, 
        encoding="utf-8"
    )
    # Formato limpo para arquivo
    file_fmt = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_fmt)
    # Adiciona filtro de segurança para sanitizar logs
    file_handler.addFilter(SecurityFilter())
    logger.addHandler(file_handler)

    # --- Console Handler (Com cores) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorfulFormatter())
    # Adiciona filtro de segurança também no console
    console_handler.addFilter(SecurityFilter())
    logger.addHandler(console_handler)

    return logger
