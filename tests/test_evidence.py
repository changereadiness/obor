import unittest
from pathlib import Path

from obor_intelligence.semantic_tables import extract_observations
from obor_intelligence.evidence import (
    extract_dataset_observations,
    select_key_evidence,
    validate_evidence,
)

FIX = Path(__file__).parent / "fixtures"


def observations(name, period=None):
    return extract_observations((FIX / name).read_text(), default_period=period)


class DatasetObservationTests(unittest.TestCase):
    def test_explicit_distribution_is_validated(self):
        text = (
            "According to the monitoring of market prices of 50 kinds of important means of production, "
            "the prices of 12 products increased, 31 kinds decreased, and 7 kinds remained flat compared "
            "with those in the previous period."
        )
        ds = extract_dataset_observations(text, "August 1-10 2026")
        self.assertEqual(len(ds), 1)
        self.assertEqual(ds[0].population, 50)
        self.assertEqual(ds[0].increased, 12)
        self.assertEqual(ds[0].decreased, 31)
        self.assertEqual(ds[0].unchanged, 7)
        self.assertEqual(ds[0].validate(), [])

    def test_incomplete_distribution_is_not_invented(self):
        text = "Of 50 monitored products, 31 decreased in price."
        self.assertEqual(extract_dataset_observations(text), [])


class EvidenceSelectionTests(unittest.TestCase):
    def test_production_input_distribution_precedes_product_movements(self):
        obs = observations("production_inputs.html", "August 1-10 2026")
        ds = extract_dataset_observations(
            "According to monitoring of 50 products, prices of 12 products increased, 31 products decreased, and 7 products remained flat.",
            "August 1-10 2026",
        )
        points = select_key_evidence(obs, ds, limit=5)
        self.assertEqual([p.label for p in points[:3]], ["Decreased", "Increased", "Unchanged"])
        self.assertEqual(points[0].value, "31 of 50")
        self.assertEqual(points[0].context, "62%")
        self.assertEqual(validate_evidence(points), [])

    def test_retail_primary_subject_preserves_value_and_growth(self):
        obs = observations("retail_sales.html")
        points = select_key_evidence(obs, primary_subject="Total retail sales of consumer goods", limit=5)
        self.assertTrue(any(p.value == "+0.6%" and p.period == "July" for p in points))
        self.assertTrue(any(p.value == "+1.2%" and p.period == "January - July" for p in points))
        self.assertFalse(any(p.value == "39022%" for p in points))
        self.assertEqual(validate_evidence(points), [])

    def test_industrial_robot_quantity_never_becomes_percentage(self):
        obs = observations("industrial_production.html")
        points = select_key_evidence(
            obs,
            primary_subject="Value Added of Industrial Enterprises Above the Designated Size",
            limit=8,
        )
        self.assertFalse(any("1685797%" in p.value for p in points))
        self.assertTrue(any(p.subject == "High-technology Manufacturing" and p.value == "+16.9%" for p in points))
        self.assertEqual(validate_evidence(points), [])


if __name__ == "__main__":
    unittest.main()
