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
from core.stats import stats

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


# Assinaturas de página de erro do Google. O deep_translator NÃO levanta quando o
# serviço responde com uma página de erro: devolve o corpo dela como se fosse a
# tradução. Nenhum try/except apanha isto — o adaptador mente DENTRO do contrato,
# não falha fora dele. O que apanha é validar a saída.
#
# Medido noutro bot irmão em 2026-08-30: a página de erro chegou ao canal do
# Discord como título E resumo da notícia. O elo caro é o terceiro: o envio
# "teve sucesso", o link entrou no dedup, e a notícia verdadeira nunca mais sairia.
_ASSINATURAS_PAGINA_DE_ERRO = (
    "that's an error",
    "that’s an error",
    "that's all we know",
    "that’s all we know",
    "our systems have detected unusual traffic",
    "sorry/index",
    "the requested url was not found on this server",
    "error 404 (not found)",
    "error 429",
    "detected unusual traffic from your computer network",
)

# `!!1` é o marcador literal das páginas de erro do Google ("That's an error.!!1").
# Fica separado porque é curto e só vale como sinal junto do resto da assinatura.
_MARCADOR_ERRO_GOOGLE = "!!1"


def _parece_pagina_de_erro(saida: str, original: str) -> bool:
    """
    Decide se a "tradução" devolvida é, na verdade, uma página de erro do serviço.

    PROPÓSITO DE NEGÓCIO:
        É a fronteira entre o adaptador de tradução e o que vai para o Discord.
        Sem ela, uma indisponibilidade do Google vira o texto da notícia em todos
        os canais configurados, é gravada no cache persistente e queima o link no
        dedup — a notícia real deixa de existir para o bot.

    INVARIANTES DO DOMÍNIO:
        - Só acusa quando a assinatura aparece na SAÍDA e NÃO no original: uma
          notícia que legitimamente fala de "error 404" tem de passar. Este é o
          controle negativo que impede alarme falso.
        - Saída vazia ou None conta como inválida: não há tradução para publicar.
        - Comparação case-insensitive; o Google varia a capitalização.

    COMPORTAMENTO EM CASO DE FALHA:
        Não levanta. Entrada de tipo inesperado é tratada como inválida (True),
        porque publicar algo que não é str é pior que republicar o original.
    """
    if not isinstance(saida, str) or not saida.strip():
        return True

    baixa = saida.lower()
    orig = (original or "").lower()

    for marca in _ASSINATURAS_PAGINA_DE_ERRO:
        # A marca tem de ser NOVA: se já estava no original, é assunto da notícia.
        if marca in baixa and marca not in orig:
            return True

    if _MARCADOR_ERRO_GOOGLE in saida and _MARCADOR_ERRO_GOOGLE not in (original or ""):
        return True

    return False


async def translate_to_target(text: str, target_lang: str) -> str:
    """
    Traduz texto para o idioma alvo, validando a fronteira com o serviço externo.

    PROPÓSITO DE NEGÓCIO:
        Entrega ao Discord o título e o resumo da notícia no idioma que cada
        servidor escolheu. É o último ponto antes de o texto virar mensagem.

    INVARIANTES DO DOMÍNIO:
        - INV-TRAD-001: o retorno é uma tradução real OU o texto ORIGINAL.
          Nunca o corpo de uma página de erro do serviço, nunca None.
        - Só entra no cache o que passou na validação. Cachear lixo é o que torna
          o defeito permanente: o cache é persistido em disco e sobrevive ao
          restart.
        - target_lang desconhecido cai em inglês, nunca falha a entrega.

    COMPORTAMENTO EM CASO DE FALHA:
        Nunca levanta e nunca devolve None. Exceção do adaptador, resposta vazia
        ou página de erro resultam no texto original devolvido intacto, com
        WARNING no log (degradação visível, não silenciosa) e o contador
        `traducoes_rejeitadas` incrementado para a telemetria.
    """
    if not text:
        return ""

    # Verifica cache — VALIDANDO o que sai dele.
    #
    # A validação no caminho de rede não bastava: entradas contaminadas de antes
    # da correção continuavam a ser servidas daqui, sem sequer tocar a rede.
    # Medido em produção em 2026-08-30, logo após a primeira correção: 741 das
    # 2000 entradas do cache persistido eram páginas de erro do Google. A cada
    # varredura, essas notícias voltavam a sair com lixo — e o dedup já as tinha
    # marcado como entregues.
    #
    # Entrada suja é DESCARTADA aqui, não só ignorada: assim o cache limpa-se
    # sozinho à medida que as notícias reaparecem, sem precisar de intervenção.
    cache_key = f"{target_lang}:{text}"
    if cache_key in _translation_cache:
        em_cache = _translation_cache[cache_key]
        if _parece_pagina_de_erro(em_cache, text):
            del _translation_cache[cache_key]
            stats.traducoes_rejeitadas += 1
            log.warning(
                "🈯 Entrada de cache contaminada descartada (era página de erro); "
                f"publicando o ORIGINAL. alvo={target_lang}"
            )
            return text
        _translation_cache.move_to_end(cache_key)
        return em_cache

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

        # FRONTEIRA: a resposta do adaptador é válida no contrato (é str, não
        # levantou) mas pode ser inválida no conteúdo. Validar ANTES de cachear.
        if _parece_pagina_de_erro(trad, text):
            stats.traducoes_rejeitadas += 1
            amostra = (trad or "")[:120].replace(chr(10), " ")
            log.warning(
                "🈯 Tradução rejeitada (resposta parece página de erro do serviço); "
                f"publicando o ORIGINAL. alvo={target_lang} amostra={amostra!r}"
            )
            return text

        _translation_cache[cache_key] = trad
        _translation_cache.move_to_end(cache_key)
        if len(_translation_cache) > _TRANSLATION_CACHE_MAX:
            _translation_cache.popitem(last=False)

        return trad
    except Exception as e:
        stats.traducoes_rejeitadas += 1
        # WARNING, não debug: degradação silenciosa é o que faz a falha existir e
        # ser invisível. O bot segue publicando o original, mas o motivo fica no log.
        log.warning(
            f"🈯 Falha na tradução (publicando o original): {type(e).__name__}: {e}"
        )
        return text
