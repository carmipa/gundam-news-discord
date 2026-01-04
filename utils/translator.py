"""
Translator utilities - Localization and Google Translate wrapper.
"""
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from deep_translator import GoogleTranslator

from utils.storage import p, load_json_safe

log = logging.getLogger("MaftyIntel")


class Translator:
    """Gerencia traduções e localizações."""
    
    def __init__(self):
        self.translations: Dict[str, dict] = {}
        self.default_lang = 'en_US'
        self.supported_langs = ['en_US', 'pt_BR', 'es_ES', 'it_IT']
        self._load_all()
    
    def _load_all(self):
        """Carrega todos arquivos de tradução."""
        for lang in self.supported_langs:
            try:
                # Caminho: translations/en_US.json
                path = p(f"translations/{lang}.json")
                data = load_json_safe(path, {})
                if data:
                    self.translations[lang] = data
                    log.info(f"🌍 Tradução carregada: {lang}")
                else:
                    log.warning(f"⚠️ Tradução vazia ou não encontrada: {lang}")
            except Exception as e:
                log.error(f"Erro ao carregar tradução {lang}: {e}")

    def detect_lang(self, guild_id: str, guild_locale: str = None) -> str:
        """
        Detecta idioma do servidor.
        Prioridade: 
        1. Config manual (config.json)
        2. Locale do servidor Discord
        3. Padrão (en_US)
        """
        # 1. Config manual
        config = load_json_safe(p("config.json"), {})
        if guild_id in config and "language" in config[guild_id]:
            return config[guild_id]["language"]
        
        # 2. Locale do Discord (ex: 'pt-BR' -> 'pt_BR')
        if guild_locale:
            # Converte enum para string e normaliza
            locale_str = str(guild_locale)
            normalized = locale_str.replace('-', '_')
            
            if normalized in self.supported_langs:
                return normalized
            
            # Mapas específicos
            maps = {
                'en-GB': 'en_US',
                'es-419': 'es_ES',
                'pt-BR': 'pt_BR'
            }
            return maps.get(locale_str, self.default_lang)
            
        return self.default_lang

    def get(self, key: str, lang: str = 'en_US', **kwargs) -> str:
        """
        Obtém texto traduzido por chave (ex: 'commands.help.title').
        Suporta formatação com **kwargs.
        """
        if lang not in self.translations:
            lang = self.default_lang

        keys = key.split('.')
        value = self.translations.get(lang, {})
        
        try:
            for k in keys:
                value = value[k]
            
            if isinstance(value, str):
                return value.format(**kwargs)
            return str(value)
            
        except (KeyError, TypeError):
            # Tenta fallback para inglês
            if lang != self.default_lang:
                return self.get(key, lang=self.default_lang, **kwargs)
            return key

# Instância global
t = Translator()


async def translate_to_target(text: str, target_lang: str) -> str:
    """
    Traduz texto para idioma alvo usando Google Translate.
    target_lang: 'pt', 'en', 'es', 'it'
    """
    if not text:
        return ""
        
    try:
        # Mapeia códigos internos (pt_BR) para códigos Google (pt)
        google_map = {
            'pt_BR': 'pt',
            'en_US': 'en',
            'es_ES': 'es',
            'it_IT': 'it'
        }
        target = google_map.get(target_lang, 'en')
        
        loop = asyncio.get_running_loop()
        trad = await loop.run_in_executor(
            None,
            lambda: GoogleTranslator(source="auto", target=target).translate(text)
        )
        return trad
    except Exception as e:
        return text
