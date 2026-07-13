"""
Translator utilities - Localization and Google Translate wrapper.
"""
import logging
import asyncio
import random
from collections import OrderedDict
from typing import Dict, Any, Optional
from deep_translator import GoogleTranslator

from utils.storage import p, load_json_safe, save_json_safe, load_config_cached

log = logging.getLogger("MaftyIntel")


class Translator:
    """Gerencia traduções e localizações."""
    
    def __init__(self):
        self.translations: Dict[str, dict] = {}
        self.default_lang = 'en_US'
        self.supported_langs = ['en_US', 'pt_BR', 'es_ES', 'it_IT', 'ja_JP']
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

    def detect_lang(
        self,
        guild_id: str,
        guild_locale: str = None,
        guild_lang_map: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Detecta idioma do servidor.
        Prioridade: 
        1. Config manual (config.json)
        2. Locale do servidor Discord
        3. Padrão (en_US)
        """
        # 1. Config manual (mapa já pré-carregado no hot path, quando disponível)
        if guild_lang_map and guild_id in guild_lang_map:
            return guild_lang_map[guild_id]

        # Fallback legacy: leitura pontual de config.json quando mapa não for informado
        config = load_config_cached({})
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


_TRANSLATION_CACHE_MAX = 2000
_translation_cache: "OrderedDict[str, str]" = OrderedDict()

# Persistência do cache em disco: evita reiniciar do zero e disparar rajadas de
# tradução (scraping do Google) a cada restart — principal vetor de bloqueio de IP.
_CACHE_FILE = p("translation_cache.json")

# Throttle: serializa/limita as chamadas ao Google e adiciona jitter, para não
# martelar o serviço em rajada (cold start com muitas notícias novas).
_translate_semaphore = asyncio.Semaphore(2)
_TRANSLATE_JITTER_MIN = 0.2
_TRANSLATE_JITTER_MAX = 0.7


def _load_translation_cache() -> None:
    """Carrega o cache de tradução do disco (best-effort)."""
    data = load_json_safe(_CACHE_FILE, {})
    if isinstance(data, dict):
        for k, v in list(data.items())[-_TRANSLATION_CACHE_MAX:]:
            if isinstance(k, str) and isinstance(v, str):
                _translation_cache[k] = v
        if _translation_cache:
            log.info(f"🗂️ Cache de tradução carregado: {len(_translation_cache)} entradas.")


def save_translation_cache() -> None:
    """Persiste o cache de tradução em disco (chamar ao fim da varredura)."""
    try:
        save_json_safe(_CACHE_FILE, dict(_translation_cache))
    except Exception as e:
        log.debug(f"Falha ao salvar cache de tradução: {type(e).__name__}: {e}")


_load_translation_cache()


async def translate_to_target(text: str, target_lang: str) -> str:
    """
    Traduz texto para idioma alvo usando Google Translate.
    target_lang: 'en_US', 'pt_BR', 'es_ES', 'it_IT', 'ja_JP'
    """
    if not text:
        return ""

    # Verifica cache
    cache_key = f"{target_lang}:{text}"
    if cache_key in _translation_cache:
        _translation_cache.move_to_end(cache_key)
        return _translation_cache[cache_key]

    try:
        # Mapeia códigos internos (pt_BR) para códigos Google (pt)
        google_map = {
            'pt_BR': 'pt',
            'en_US': 'en',
            'es_ES': 'es',
            'it_IT': 'it',
            'ja_JP': 'ja'
        }
        target = google_map.get(target_lang, 'en')

        loop = asyncio.get_running_loop()
        async with _translate_semaphore:
            await asyncio.sleep(random.uniform(_TRANSLATE_JITTER_MIN, _TRANSLATE_JITTER_MAX))
            trad = await loop.run_in_executor(
                None,
                lambda: GoogleTranslator(source="auto", target=target).translate(text)
            )

        if trad:
            _translation_cache[cache_key] = trad
            _translation_cache.move_to_end(cache_key)
            if len(_translation_cache) > _TRANSLATION_CACHE_MAX:
                _translation_cache.popitem(last=False)

        return trad
    except Exception as e:
        log.debug(f"Falha na tradução de texto (retornando original): {type(e).__name__}: {e}")
        return text
