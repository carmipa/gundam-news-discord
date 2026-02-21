
import re
import sys

# Simulation of what we defined in core/filters.py
from core.filters import SPECIAL_SOURCE_RULES, _contains_any, GUNDAM_CORE, CAT_MAP, BLACKLIST

TEST_CASES = [
    # Should PASS (Original tests)
    ("Mobile Suit Gundam U.C. ENGAGE - Story 01", True),
    ("Gundam UCE Cutscene", True),
    ("【UCE】Engagement Start", True),
    ("機動戦士ガンダム U.C. ENGAGE アニメ", True),
    ("Gundam U.C. Engage - New Event Story", True),
    
    # NEW CASES from user feedback (videos that were failing)
    ("Episódio 13 | Mobile SuitGundam [Gunchan]", True), # "SuitGundam" fusion, and "Episódio"
    ("第13話 | 機動戦士ガンダム 【ガンチャン】", True), # Japanese characters
    ("Episódio 49 | Força SD Gundam [Gunchan]", True), # "Episódio" with accent
    ("第49話 | SDガンダムフォース 【ガンチャン】", True), # Japanese characters


    # Should FAIL
    ("Gunpla Build Tutorial", False),
    ("Gundam SEED Freedom Trailer", False),
    ("Gundam Breaker 4 Gameplay", False),
    ("Live Stream: Gunderrium Edition", False),
    ("New Product Announcement", False),
]

def run_tests():
    print("🔎 Testing Gundam U.C. Engage Regex Filters...")
    
    # We test with the ID we are adding
    target_id = "UC7wu64jGxCwSuxOR7XfS88g"
    regex = SPECIAL_SOURCE_RULES[target_id]
    
    failures = 0
    
    for title, expected in TEST_CASES:
        match = bool(re.search(regex, title))
        status = "✅ PASS" if match == expected else "❌ FAIL"
        
        if match != expected:
            failures += 1
            
        print(f"{status} | Expected: {expected} | Got: {match} | Title: {title}")
        
    print("\n🔎 Testing Filter Logic (`_contains_any`) with edge cases...")
    filter_tests = [
        ("Mobile SuitGundam", GUNDAM_CORE, True), # Word boundary fix test
        ("機動戦士ガンダム", GUNDAM_CORE, True), # Japanese CJK test
        ("Wing", ["wing"], True), # Normal boundary test
        ("Drawing", ["wing"], False), # Enforce boundary for non-core words
        ("Episódio 13", CAT_MAP["filmes"], True), # Accent handling
        ("Força SD Gundam", GUNDAM_CORE, True), 
        ("Dragon ball trailer", BLACKLIST, True), # Blacklist test
    ]
    
    for text, keywords, expected in filter_tests:
        match = _contains_any(text.lower(), keywords)
        status = "✅ PASS" if match == expected else "❌ FAIL"
        
        if match != expected:
            failures += 1
            
        print(f"{status} | Expected: {expected} | Got: {match} | Text: '{text}' | Keys: {keywords[:2]}")
        
    if failures == 0:
        print("\n✨ All tests passed!")
        sys.exit(0)
    else:
        print(f"\n💀 {failures} tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
