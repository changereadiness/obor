## V15 — Repair synthesis fetch dependency

V15 gives the synthesis layer its own source fetch implementation. Earlier versions called `fetch()` from `synthesis.py` without defining it, causing re-synthesis to fail silently and preserve stale records. V15 also reports the reprocessing status for each recovered signal and restores the current GitHub Actions runtime versions.

## V13 — Self-healing signal ledger

V13 makes the published signal pages a recovery ledger. If `data/signals.json` is stale or reverted but real published signal pages remain under `signals/<slug>/`, the runtime pipeline reconstructs those records, re-fetches their source URLs, re-synthesizes them, and rewrites the canonical `data/signals.json`. The normal architecture remains `data/signals.json` → generated pages; page recovery exists only to survive deployment/package replacement. Demo pages are never recovered as real signals.

## V12 — Runtime re-synthesis of existing signals

V12 reprocesses previously published signals when the synthesis engine version changes. Existing valid signals are replaced by improved evidence-backed versions; failed re-fetches preserve the prior signal. Each published signal records `synthesis_version`.

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


### V18 — Intelligence Semantics
- Article-body extraction prioritizes content after the main H1 and strips site chrome.
- Dataset-level statistics are treated as primary evidence ahead of individual table rows.
- Production-input price releases use the 50-product movement distribution for interpretation rather than the extracted sample.
- Synthesized sectors are based on the economic subject rather than generic supply-chain keywords.
- Canadian relevance distinguishes observed facts from conditional business implications.
