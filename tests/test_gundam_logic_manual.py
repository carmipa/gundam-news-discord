
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

print("Starting Gundam Logic Tests (Manual Runner)...")

# CASO 1: Hathaway / Kirke's Witch
run_test("[PV] Hathaway's Flash: Kirke's Witch", "New movie", True)
run_test("『機動戦士ガンダム 閃光のハサウェイ キルケーの魔女』", "Trailer", True)

# CASO 2: Blacklist
run_test("One Piece Live Action News", "Gundam style", False)
run_test("Naruto vs Boruto", "Gundam theme", False)

# CASO 3: Gunpla 
run_test("New HG 1/144 Zaku II Release", "Model kit", True)

# CASO 4: Falsos Positivos
run_test("News at 12:00", "No gundam terms", False)
run_test("Gundam 00 Movie", "The world is changing", True)

# CASO 5: Termos CJK
run_test("ガンダムの最新ニュース", "Japanese news", True)

print("\n✨ All tests passed successfully!")
