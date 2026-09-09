import unittest
from pathlib import Path

from obor_intelligence.source_analysis import analyze_source
from obor_intelligence.records import make_signal_record, validate_signal_record
from obor_intelligence.publisher import render_signal

FIX = Path(__file__).parent / "fixtures"

CASES = [
    (
        "Market Prices of Important Means of Production in Circulation, August 1-10, 2026",
        "production_inputs.html",
        "https://example.test/nbs/market-prices",
        "China production-input prices mostly declined",
    ),
    (
        "Total Retail Sales of Consumer Goods from January to July 2026",
        "retail_sales.html",
        "https://example.test/nbs/retail-sales",
        "China retail sales grew 0.6%",
    ),
    (
        "Industrial Production Operation in July 2026",
        "industrial_production.html",
        "https://example.test/nbs/industrial-production",
        "China industrial output grew 4.5%",
    ),
]


class EndToEndTests(unittest.TestCase):
    def test_all_three_source_families_reach_rendered_html(self):
        for title, fixture, url, expected in CASES:
            with self.subTest(fixture=fixture):
                body = (FIX / fixture).read_text()
                analysis = analyze_source(title, body)
                self.assertEqual(analysis.status, "ready", analysis.errors)
                signal = make_signal_record(analysis, url, "National Bureau of Statistics of China", "2026-08-18")
                self.assertEqual(validate_signal_record(signal), [])
                page = render_signal(signal)
                self.assertIn(expected, page)
                self.assertIn("<p class=\"eyebrow\">WHAT HAPPENED</p><ul><li>", page)
                self.assertIn("<p class=\"eyebrow\">KEY DATA</p><ul class=\"key-data\">", page)

    def test_historical_bogus_outputs_are_absent(self):
        industrial = analyze_source(
            CASES[2][0], (FIX / "industrial_production.html").read_text()
        )
        signal = make_signal_record(industrial, CASES[2][2], "NBS", "2026-08-18")
        page = render_signal(signal)
        for bad in ["1685797%", "98677%", "economic price movement", "factory demand"]:
            self.assertNotIn(bad, page)

        retail = analyze_source(CASES[1][0], (FIX / "retail_sales.html").read_text())
        signal = make_signal_record(retail, CASES[1][2], "NBS", "2026-08-18")
        page = render_signal(signal)
        for bad in ["39022%", "287744%", "economic price movement"]:
            self.assertNotIn(bad, page)


if __name__ == "__main__":
    unittest.main()
