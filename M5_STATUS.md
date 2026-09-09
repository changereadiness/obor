# OBOR Clean Reconstruction — M5 Integration Checkpoint

## Status

**INTEGRATION CHECKPOINT — DO NOT DEPLOY TO PRODUCTION YET**

M5 integrates the clean semantic intelligence engine with the proven V17 operational shell.

### Retained from V17

- page-first source ingestion and degraded-source handling
- candidate screening and deterministic relevance/confidence scoring
- source persistence under `data/raw/`
- published-signal recovery concept
- static GitHub Pages structure
- `run.py` orchestration

### Replaced / bypassed

- the active V17 synthesis path
- flattened-text table semantics
- generic `Rate (%)` => price-movement assumptions
- the previous weak quality gate
- the previous rendering assumption that `what_happened` is always a string

The V17 synthesis implementation is retained only as `scripts/legacy_synthesis_v17.py` for forensic reference. Nothing in the active M5 pipeline imports it.

## Active intelligence path

```text
ingest.py
  -> pipeline.py screening/recovery
  -> clean_adapter.py
  -> source_fetch.py
  -> obor_intelligence/source_analysis.py
  -> semantic_tables.py
  -> evidence.py
  -> editorial.py
  -> persisted signal JSON
  -> build.py
  -> validate.py
```

## Fixture integration coverage

Three NBS statistical structures are mandatory regression fixtures:

1. production-input market prices
2. retail sales
3. industrial production

The suite explicitly prevents historical failures including:

- retail absolute values becoming percentages (`39022%`, `287744%`)
- industrial output quantities becoming percentages (`1685797%`, `98677%`)
- retail / industrial data being labelled `economic price movement`
- industrial output headlines substituting `factory demand` for measured production
- loss of positive/negative rate direction
- demo pages being recovered as real signals
- loss of canonical signal JSON followed by failed page recovery

## Test result

`22 tests` pass at M5 freeze.

This includes:

- semantic extraction tests
- evidence validation tests
- editorial synthesis tests
- clean end-to-end source -> HTML tests
- V17-style pipeline reprocessing
- signal page rendering
- strengthened quality gate
- recovery after deleting `signals.json`
- full `run.py` fixture orchestration

## Deployment rule

M5 is not yet a deployable production release. The next gate is controlled testing against real NBS source pages. Production packaging occurs only after real-source output is inspected for semantic correctness.
