
import os
import sys

# Garante que o diretório raiz está no path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.filters import match_intel

MOCK_CONFIG = {
    "123": {
        "filters": ["todos", "gunpla", "filmes", "games", "musica"]
    }
}

def run_test(title, summary, expected):
    result = match_intel("123", title, summary, MOCK_CONFIG)
    if result == expected:
        print(f"✅ PASS: '{title[:30]}...' -> {result}")
    else:
        print(f"❌ FAIL: '{title[:30]}...' -> Got {result}, expected {expected}")
        sys.exit(1)


def main():
    print("Starting Gundam Logic Tests (Manual Runner)...")

    # CASO 1: Hathaway / Kirke's Witch
    run_test("[PV] Hathaway's Flash: Kirke's Witch", "New movie", True)
    run_test("『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』", "Trailer", True)

    # CASO 2: Blacklist
    run_test("One Piece Live Action News", "Gundam style", False)
    run_test("Naruto vs Boruto", "Gundam theme", False)

    # CASO 3: Gunpla
    run_test("New HG 1/144 Zaku II Release", "Model kit", True)

    # CASO 4: Falsos Positivos — o resumo não pode citar "gundam", senão passa
    # no portão de relevância pela própria palavra que diz não existir.
    run_test("News at 12:00", "No mecha terms", False)
    run_test("Gundam 00 Movie", "The world is changing", True)

    # CASO 5: Termos CJK
    run_test("ガンダムの最新ニュース", "Japanese news", True)

    print("\n✨ All tests passed successfully!")


# Runner manual: `python tests/test_gundam_logic_manual.py`.
# A guarda é obrigatória — o pytest coleta este ficheiro pelo padrão `test_*.py`
# e, sem ela, o `sys.exit(1)` do primeiro caso falho corria durante o IMPORT e
# derrubava a sessão inteira com INTERNALERROR, sem executar mais nenhum teste.
# A cobertura equivalente, em formato pytest, vive em test_gundam_logic.py.
if __name__ == "__main__":
    main()
