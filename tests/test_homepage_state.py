import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class HomepageStateTests(unittest.TestCase):
    def setUp(self):
        self.index = (REPO / 'index.html').read_text()
        self.app = (REPO / 'assets' / 'app.js').read_text()

    def test_today_heading_is_dynamic_not_archival(self):
        self.assertNotIn('September 1, 2026', self.index)
        match = re.search(r'<p class="eyebrow">TODAY</p>\s*<h2([^>]*)>(.*?)</h2>', self.index, re.I | re.S)
        self.assertIsNotNone(match)
        self.assertIn('id="today-date"', match.group(1))
        self.assertIn('id="today-state"', self.index)
        self.assertIn('id="today-signal-grid"', self.index)

    def test_quiet_day_and_archive_are_separate_states(self):
        self.assertIn('No major signals detected today.', self.app)
        self.assertIn("slice(0,10)===todayKey", self.app)
        self.assertIn('LATEST SIGNALS', self.index)
        self.assertIn('id="latest-date"', self.index)
        self.assertIn('id="latest-signal-grid"', self.index)

    def test_non_public_records_cannot_reach_homepage(self):
        self.assertIn("s.status!=='suppressed'", self.app)
        self.assertIn("s.status!=='demo'", self.app)


if __name__ == '__main__':
    unittest.main()
