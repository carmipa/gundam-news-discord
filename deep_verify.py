import unittest
from datetime import datetime, timezone
import dateutil.parser as dtparser

# Try importing the necessary units
from core.filters import match_intel, CAT_MAP, _contains_any, GUNDAM_CORE
from core.scanner import parse_entry_dt

class DummyEntry:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    def dict(self):
        return {k: v for k, v in self.__dict__.items()}

class TestDeepVerification(unittest.TestCase):

    def setUp(self):
        self.config_all = {"1": {"filters": ["todos"]}}
        self.config_filmes = {"1": {"filters": ["filmes"]}}
        self.config_games = {"1": {"filters": ["games"]}}
        self.config_gunpla = {"1": {"filters": ["gunpla"]}}

    def test_match_intel_todos(self):
        # Even with Japanese, 'todos' should pass everything containing "Gundam" core words.
        title = "ネタバレありの座談会#2｜『機動戦士ガンダム 閃光のハサウェイ』"
        self.assertTrue(match_intel("1", title, "", self.config_all, "url"))

    def test_match_intel_filmes_japanese(self):
        # Current behavior: this will fail because "閃光のハサウェイ" is not in mapped 'filmes'.
        title = "ネタバレありの座談会#2｜『機動戦士ガンダム 閃光のハサウェイ』"
        # Since I am writing deep test, I want to see if it *fails* exactly as I suspect.
        # This assert proves the limitation.
        self.assertFalse(match_intel("1", title, "", self.config_filmes, "url"), "Hathaway in JP shouldn't pass without JP keywords in CAT_MAP['filmes']")

    def test_match_intel_games_japanese(self):
        title = "機動戦士ガンダム バトルオペレーション２" # Only Japanese
        self.assertFalse(match_intel("1", title, "", self.config_games, "url"), "GBO2 in JP shouldn't pass without JP keywords in CAT_MAP['games']")

    def test_match_intel_filmes_english(self):
        title = "Mobile Suit Gundam Hathaway's Flash - Episode 1"
        self.assertTrue(match_intel("1", title, "", self.config_filmes, "url"))
        
    def test_date_parsing_iso(self):
        # ISO8601 from Youtube
        entry = DummyEntry(published="2026-03-19T10:00:00Z")
        dt = parse_entry_dt(entry)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertIsNotNone(dt.tzinfo)

    def test_date_parsing_struct(self):
        import time
        t = time.gmtime(1679220000) # Some valid timestamp
        entry = DummyEntry(published_parsed=t)
        dt = parse_entry_dt(entry)
        self.assertIsNotNone(dt)

    def test_date_parsing_invalid(self):
        # Should return None
        entry = DummyEntry(published="Not a real date lol")
        dt = parse_entry_dt(entry)
        self.assertIsNone(dt)

    def test_date_parsing_none(self):
        entry = DummyEntry(title="No date provided")
        dt = parse_entry_dt(entry)
        self.assertIsNone(dt)

    def test_missing_fields(self):
        # No title, no summary
        # Should be false safely without raising exceptions
        self.assertFalse(match_intel("1", "", "", self.config_all, "url"))
        self.assertFalse(match_intel("1", None, None, self.config_all, "url")) 

    def test_blacklist_overrides(self):
        # Even if it has Gundam, if it has "pokemon", it should be blocked
        title = "Gundam vs Pokemon Crossover Battle"
        self.assertFalse(match_intel("1", title, "", self.config_all, "url"))

if __name__ == '__main__':
    unittest.main()
