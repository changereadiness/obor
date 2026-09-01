# OBOR.ca

**China Economic Intelligence for Canadian Business**

OBOR is a static intelligence site backed by a structured signal store and an automated collection/classification pipeline.

## Current architecture

```text
RSS / public feeds
      ↓
normalize
      ↓
deduplicate
      ↓
deterministic China + business filter
      ↓
category / sector / direction classification
      ↓
Canadian relevance scoring
      ↓
opportunity / risk / watch classification
      ↓
quality gate
      ↓
structured signals.json
      ↓
static HTML generation
      ↓
GitHub Pages
```

The AI boundary lives in `scripts/ai_adapter.py`. It is intentionally optional. The site does not require a paid model to collect, filter, score or publish.

## Run locally

From the repository root:

```bash
python scripts/run.py
python scripts/validate.py
```

`run.py` executes ingestion, processing and static generation.

## Source configuration

Edit `data/sources.json` to enable/disable feeds. `data/overrides.json` supports source suppression and per-signal overrides.

Raw collection artifacts are written to `data/raw/` and are not treated as published intelligence until they pass the deterministic gate.

## Publication rules

The MVP will not manufacture a signal when no meaningful candidate is found. If collection fails, the last valid signal store is preserved. If no signals exist at all, the site can display a no-major-signals state rather than inventing content.

## Cost model

Default infrastructure uses Python standard library + RSS/Atom + GitHub Actions + GitHub Pages. No paid API is required.

## Next layer

The next upgrade is an optional AI analysis stage between deterministic candidate selection and publication. It should only receive the top candidates, return structured fields, and remain subject to the same validation gate.
