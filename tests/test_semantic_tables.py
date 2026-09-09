import unittest
from pathlib import Path

from obor_intelligence.semantic_tables import extract_observations, validate_observations

FIX = Path(__file__).parent / "fixtures"


def load(name, period=None):
    body = (FIX / name).read_text(encoding="utf-8")
    obs = extract_observations(body, default_period=period)
    errors = validate_observations(obs)
    if errors:
        raise AssertionError("semantic validation failed: " + "; ".join(errors))
    return obs


def one(obs, subject, metric, period=None):
    hits = [o for o in obs if o.subject == subject and o.metric == metric and (period is None or o.period == period)]
    if len(hits) != 1:
        raise AssertionError(f"expected one observation for {subject!r} {metric!r} {period!r}; got {len(hits)}")
    return hits[0]


class ProductionInputTests(unittest.TestCase):
    def test_price_semantics_and_signs(self):
        obs = load("production_inputs.html", "August 1-10 2026")
        benzene = one(obs, "Pure Benzene (Petroleum Benzene, Industrial Grade)", "price_change_rate")
        self.assertEqual(benzene.value, -7.3)
        self.assertEqual(benzene.unit, "%")
        self.assertEqual(benzene.direction, "decrease")
        self.assertEqual(benzene.comparison, "previous_period")
        price = one(obs, "Pure Benzene (Petroleum Benzene, Industrial Grade)", "price")
        self.assertEqual(price.value, 7487.0)
        self.assertEqual(price.unit, "yuan/ton")

    def test_product_spec_percentage_is_not_movement(self):
        obs = load("production_inputs.html", "August 1-10 2026")
        sulfur = [o for o in obs if o.subject == "Sulfuric Acid (98%)"]
        self.assertEqual({o.value for o in sulfur if o.metric == "price_change_rate"}, {-2.7})
        self.assertNotIn(98.0, {o.value for o in sulfur})

    def test_positive_price_direction(self):
        obs = load("production_inputs.html", "August 1-10 2026")
        zinc = one(obs, "Zinc Ingot (0#)", "price_change_rate")
        self.assertEqual(zinc.value, 2.9)
        self.assertEqual(zinc.direction, "increase")


class RetailTests(unittest.TestCase):
    def test_multi_level_headers_preserve_period_and_metric(self):
        obs = load("retail_sales.html")
        july_value = one(obs, "Total retail sales of consumer goods", "absolute_value", "July")
        july_growth = one(obs, "Total retail sales of consumer goods", "growth_rate_yoy", "July")
        ytd_value = one(obs, "Total retail sales of consumer goods", "absolute_value", "January - July")
        ytd_growth = one(obs, "Total retail sales of consumer goods", "growth_rate_yoy", "January - July")
        self.assertEqual(july_value.value, 39022)
        self.assertEqual(july_value.unit, "100 million yuan")
        self.assertEqual(july_growth.value, 0.6)
        self.assertEqual(july_growth.unit, "%")
        self.assertEqual(ytd_value.value, 287744)
        self.assertEqual(ytd_growth.value, 1.2)

    def test_absolute_value_is_never_percentage(self):
        obs = load("retail_sales.html")
        value = one(obs, "Retail sales excluding automobiles", "absolute_value", "July")
        self.assertEqual(value.value, 35892)
        self.assertNotEqual(value.unit, "%")
        self.assertNotEqual(value.metric, "price_change_rate")

    def test_missing_cells_do_not_generate_fake_observations(self):
        obs = load("retail_sales.html")
        online = [o for o in obs if o.subject == "Online retail sales of goods"]
        self.assertEqual(len(online), 2)
        self.assertEqual({o.period for o in online}, {"January - July"})


class IndustrialProductionTests(unittest.TestCase):
    def test_growth_is_output_growth_not_price(self):
        obs = load("industrial_production.html")
        manufacturing = one(obs, "Manufacturing", "growth_rate_yoy", "July")
        mining = one(obs, "Mining", "growth_rate_yoy", "July")
        hightech = one(obs, "High-technology Manufacturing", "growth_rate_yoy", "July")
        self.assertEqual(manufacturing.value, 5.5)
        self.assertEqual(manufacturing.direction, "increase")
        self.assertEqual(mining.value, -4.2)
        self.assertEqual(mining.direction, "decrease")
        self.assertEqual(hightech.value, 16.9)
        self.assertFalse(any(o.metric.startswith("price") for o in obs))

    def test_large_output_values_are_not_rates(self):
        obs = load("industrial_production.html")
        robots = one(obs, "Service Robots (set)", "absolute_value", "July")
        growth = one(obs, "Service Robots (set)", "growth_rate_yoy", "July")
        self.assertEqual(robots.value, 1685797)
        self.assertEqual(growth.value, 5.7)
        self.assertNotEqual(robots.unit, "%")

    def test_rowspan_colspan_expansion(self):
        obs = load("industrial_production.html")
        july = one(obs, "Manufacturing", "growth_rate_yoy", "July")
        ytd = one(obs, "Manufacturing", "growth_rate_yoy", "January-July")
        self.assertEqual(july.value, 5.5)
        self.assertEqual(ytd.value, 5.6)


if __name__ == "__main__":
    unittest.main()
