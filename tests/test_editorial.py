import unittest
from pathlib import Path

from obor_intelligence.semantic_tables import extract_observations
from obor_intelligence.evidence import extract_dataset_observations
from obor_intelligence.editorial import build_draft, validate_draft

FIX = Path(__file__).parent / "fixtures"


def obs(name, period=None):
    return extract_observations((FIX / name).read_text(), default_period=period)


class MarketPriceEditorialTests(unittest.TestCase):
    def test_distribution_drives_headline_and_key_data(self):
        observations = obs("production_inputs.html", "August 1-10 2026")
        datasets = extract_dataset_observations(
            "According to monitoring of market prices of 50 kinds of important means of production, the prices of 12 products increased, 31 kinds decreased, and 7 kinds remained flat.",
            "August 1-10 2026",
        )
        draft = build_draft("Market Prices of Important Means of Production in Circulation, August 1-10, 2026", observations, datasets)
        self.assertEqual(draft.profile, "market_prices")
        self.assertIn("mostly declined", draft.headline)
        self.assertIn("31 of 50", draft.summary)
        self.assertTrue(any(c["value"] == "31 of 50" for c in draft.key_data))
        self.assertEqual(validate_draft(draft, observations, datasets), [])


class RetailEditorialTests(unittest.TestCase):
    def test_retail_draft_uses_sales_not_prices(self):
        observations = obs("retail_sales.html")
        draft = build_draft("Total Retail Sales of Consumer Goods from January to July 2026", observations)
        self.assertEqual(draft.profile, "retail_sales")
        self.assertEqual(draft.headline, "China retail sales grew 0.6% year over year in July")
        self.assertNotIn("price", draft.headline.lower())
        self.assertTrue(any("excluding automobiles" in b.lower() for b in draft.what_happened))
        self.assertFalse(any(c["value"] == "39022%" for c in draft.key_data))
        self.assertEqual([c["value"] for c in draft.key_data], ["+0.6%", "+1.2%", "+2.5%", "+4.6%"] )
        self.assertEqual(validate_draft(draft, observations), [])


class IndustrialEditorialTests(unittest.TestCase):
    def test_industrial_headline_describes_output_not_demand(self):
        observations = obs("industrial_production.html")
        draft = build_draft("Industrial Production Operation in July 2026", observations)
        self.assertEqual(draft.profile, "industrial_output")
        self.assertEqual(draft.headline, "China industrial output grew 4.5% year over year in July")
        self.assertNotIn("demand", draft.headline.lower())
        self.assertTrue(any("High-tech manufacturing" in b for b in draft.what_happened))
        self.assertIn("not itself a measure", draft.canadian_relevance)
        self.assertFalse(any("1685797%" in c["value"] for c in draft.key_data))
        self.assertEqual([c["label"] for c in draft.key_data], [
            "Industrial value added", "Industrial value added", "Manufacturing", "High-tech manufacturing", "Mining"
        ])
        self.assertEqual(validate_draft(draft, observations), [])


if __name__ == "__main__":
    unittest.main()
