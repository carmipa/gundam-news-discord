"""
Stats module - Bot statistics tracking.
"""
from datetime import datetime, timedelta


class BotStats:
    """Estatísticas do bot em memória."""
    
    def __init__(self):
        """Inicializa contadores de estatísticas."""
        self.start_time = datetime.now()
        self.scans_completed = 0
        self.news_posted = 0
        self.feeds_failed = 0
        self.last_scan_time = None
        self.cache_hits_total = 0
    
    @property
    def uptime(self) -> timedelta:
        """
        Retorna tempo de atividade do bot.
        
        Returns:
            timedelta desde o início
        """
        return datetime.now() - self.start_time
    
    def format_uptime(self) -> str:
        """
        Formata uptime de forma legível.
        
        Returns:
            String formatada (ex: "2d 4h 30m")
        """
        total_seconds = int(self.uptime.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


# Instância global de estatísticas
stats = BotStats()
