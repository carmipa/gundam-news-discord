
import logging
import sys
from colorama import init, Fore, Style

# Inicializa colorama para funcionar no Windows
init(autoreset=True)

class ColorfulFormatter(logging.Formatter):
    """
    Formatador de logs customizado com cores e ícones.
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
        # O %(levelname)s será colorido
        log_fmt = f"{Fore.LIGHTBLACK_EX}%(asctime)s{Style.RESET_ALL} - [{color}%(levelname)s{Style.RESET_ALL}] {icon} %(message)s"
        
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

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
    logger.addHandler(file_handler)

    # --- Console Handler (Com cores) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColorfulFormatter())
    logger.addHandler(console_handler)

    return logger
