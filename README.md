## V11 — Re-synthesis of existing signals

V11 reprocesses previously published signals when the synthesis engine version changes. Existing valid signals are replaced by improved evidence-backed versions; failed re-fetches preserve the prior signal. Each published signal records `synthesis_version`.

# OBOR.ca

**China Economic Intelligence for Canadian Business**

OBOR is a static intelligence site backed by a structured signal store and an automated, cost-free collection and analysis pipeline.

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
evidence extraction
      ↓
category / sector / direction classification
      ↓
Canadian relevance scoring
      ↓
opportunity / risk / watch / neutral classification
      ↓
conservative publication gate
      ↓
structured signals.json
      ↓
static HTML generation
      ↓
GitHub Pages
```

The AI boundary remains in `scripts/ai_adapter.py` but is deliberately unused. No paid model is required.

## Deterministic intelligence principles

The MVP is intentionally conservative. It should prefer missing a weak signal over publishing an unsupported one.

A candidate must:

- concern China;
- contain a business/economic relevance cue;
- have explicit Canadian relevance evidence;
- meet minimum OBOR relevance and confidence thresholds;
- pass the structured validation gate.

Every accepted signal retains evidence terms used by the deterministic analyst so later AI analysis can inspect the same structured input.

## Raw artifacts

- `data/raw/items.json` — normalized source items
- `data/raw/candidates.json` — highest-ranked candidates sent to the publication gate
- `data/raw/rejections.json` — rejected candidates and reasons
- `data/raw/ingest_log.json` — source collection results and errors

## Human overrides

`data/overrides.json` supports:

- source suppression;
- per-signal field overrides.

The schema can later be expanded for verification status and editorial corrections without introducing an admin application.

## Run locally

```bash
python scripts/run.py
python scripts/validate.py
```

## Cost model

The default system uses Python's standard library, RSS/Atom, GitHub Actions and GitHub Pages. There is no paid API dependency.

## Next upgrade

The deterministic analyst can later be replaced or augmented by an optional AI analyzer. The publication gate and validation layer should remain deterministic regardless of the intelligence provider.


## v9 — Evidence-backed synthesis

v9 adds a synthesis layer between screening and publication. Screened source pages are fetched, article text is extracted, numeric economic facts are parsed, and each published signal is generated from source evidence rather than the raw source title. Signals now carry `key_data`, `interpretation`, and `synthesis` evidence. A source fetch/extraction failure prevents publication of that candidate rather than allowing an unsupported signal through.
