import sys
import re

GUNDAM_CORE = [
    'gundam', 'gunpla', 'zeon', 'zaku', 'mobile suit', 'haropla', 'sdcs',
    'amuro ray', 'char aznable', 'mafty', 'minovsky', 'newtype', 'cyber newtype',
    'rx-78', '08th ms team', '0080', 'war in the pocket', '0083', 'stardust memory',
    'zeta gundam', 'zz gundam', 'char\'s counterattack', 'cca', 'hathaway\'s flash',
    'hathaway noa', 'xi gundam', 'penelope', 'unicorn gundam', 'rx-0', 'banshee',
    'narrative', 'gundam f91', 'victory gundam', 'cucuruz doan', 'cucuruz doan\'s island',
    'thunderbolt', 'requiem for vengeance', 'gundam the origin', 'u.c. engage', 'engage', 'uce',
    'g gundam', 'gundam wing', 'endless waltz', 'gundam x', 'turn a gundam',
    'gundam seed', 'seed destiny', 'seed freedom', 'astray', 'stargazer',
    'gundam 00', 'double 00', 'gundam age', 'g reconguista', 'iron-blooded orphans',
    'ibo', 'barbatos', 'witch from mercury', 'suletta', 'miorine', 'aerial',
    'build fighters', 'build divers', 'build metaverse', 'sd gundam', 'gundam breakers',
    'ガンダム', '機動戦士', 'ハサウェイ', 'マフティー', '閃光のハサウェイ', 'エンゲージ', 'ガンプラ'
]

text = '''Previsões finais do vencedor do ator: a última parada do circuito pode trazer potencial de reviravolta para Michael B. Jordan, Benicio Del Toro e mais
O trem da temporada de premiações está chegando à sua penúltima parada antes de seguir para o Dolby Theatre. A última parada antes do encerramento da votação do Oscar é muitas vezes onde as narrativas se fortalecem, o ímpeto se cristaliza e os atores – o maior bloco eleitoral da Academia – dão a conhecer suas preferências coletivas. O Actor Awards (anteriormente SAG Awards), que é votado por []'''.lower()

core_agglutinable = ['gundam', 'gunpla', 'zaku', 'zeon']

for k in GUNDAM_CORE:
    escaped = re.escape(k)
    is_cjk = re.search(r'[^\x00-\x7F]', k)
    if k in core_agglutinable:
        pattern_str = escaped + r's?'
    elif is_cjk:
        pattern_str = escaped
    else:
        pattern_str = r'(?<!:)\b' + escaped + r's?\b'
        
    if re.search(pattern_str, text):
        print(f'MATCHED: {k}')
