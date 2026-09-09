#!/usr/bin/env python3
import json
from pathlib import Path
from .semantic_tables import extract_observations
from .evidence import extract_dataset_observations
from .editorial import build_draft, validate_draft

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

cases = [
    (
        "Market Prices of Important Means of Production in Circulation, August 1-10, 2026",
        "production_inputs.html",
        "August 1-10 2026",
        "According to monitoring of market prices of 50 kinds of important means of production, the prices of 12 products increased, 31 kinds decreased, and 7 kinds remained flat.",
    ),
    ("Total Retail Sales of Consumer Goods from January to July 2026", "retail_sales.html", None, None),
    ("Industrial Production Operation in July 2026", "industrial_production.html", None, None),
]

for title, fixture, period, summary_text in cases:
    observations = extract_observations((FIX / fixture).read_text(), default_period=period)
    datasets = extract_dataset_observations(summary_text, period) if summary_text else []
    draft = build_draft(title, observations, datasets)
    errors = validate_draft(draft, observations, datasets)
    print("=" * 78)
    print(title)
    print(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2))
    print("VALIDATION:", "PASS" if not errors else errors)
