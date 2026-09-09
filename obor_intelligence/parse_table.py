#!/usr/bin/env python3
import argparse
from pathlib import Path
from .semantic_tables import extract_observations, observations_to_json, validate_observations


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract typed economic observations from an HTML table")
    ap.add_argument("html")
    ap.add_argument("--period", default=None, help="Fallback period when the table header does not carry one")
    args = ap.parse_args()
    body = Path(args.html).read_text(encoding="utf-8")
    observations = extract_observations(body, default_period=args.period)
    errors = validate_observations(observations)
    print(observations_to_json(observations))
    if errors:
        print("\nVALIDATION ERRORS:")
        for error in errors:
            print("-", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
