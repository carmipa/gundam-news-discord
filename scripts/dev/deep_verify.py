import unittest
from datetime import datetime, timezone
import dateutil.parser as dtparser
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.filters import match_intel
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
        title = "ネタバレありの座談会#2｜『機動戦士ガンダム 閃光のハサウェイ』"
        self.assertTrue(match_intel("1", title, "", self.config_all, "url"))

    def test_match_intel_filmes_japanese(self):
        title = "ネタバレありの座談会#2｜『機動戦士ガンダム 閃光のハサウェイ』"
        self.assertTrue(match_intel("1", title, "", self.config_filmes, "url"))

    def test_match_intel_games_japanese(self):
        title = "機動戦士ガンダム バトルオペレーション２"
        self.assertTrue(match_intel("1", title, "", self.config_games, "url"))

    def test_match_intel_filmes_english(self):
        title = "Mobile Suit Gundam Hathaway's Flash - Episode 1"
        self.assertTrue(match_intel("1", title, "", self.config_filmes, "url"))

    def test_date_parsing_iso(self):
        entry = DummyEntry(published="2026-03-19T10:00:00Z")
        dt = parse_entry_dt(entry)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertIsNotNone(dt.tzinfo)

    def test_date_parsing_struct(self):
        import time

        t = time.gmtime(1679220000)
        entry = DummyEntry(published_parsed=t)
        dt = parse_entry_dt(entry)
        self.assertIsNotNone(dt)

    def test_date_parsing_invalid(self):
        entry = DummyEntry(published="Not a real date lol")
        dt = parse_entry_dt(entry)
        self.assertIsNone(dt)

    def test_date_parsing_none(self):
        entry = DummyEntry(title="No date provided")
        dt = parse_entry_dt(entry)
        self.assertIsNone(dt)

    def test_missing_fields(self):
        self.assertFalse(match_intel("1", "", "", self.config_all, "url"))
        self.assertFalse(match_intel("1", None, None, self.config_all, "url"))

    def test_blacklist_overrides(self):
        title = "Gundam vs Pokemon Crossover Battle"
        self.assertFalse(match_intel("1", title, "", self.config_all, "url"))


if __name__ == "__main__":
    unittest.main()
