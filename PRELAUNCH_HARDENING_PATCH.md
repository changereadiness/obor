# OBOR M6 Pre-Launch Hardening Patch

Apply these files over the current M6 repository, then run **OBOR Daily Intelligence** once.

Changed files:

- `scripts/pipeline.py`
- `scripts/clean_adapter.py`
- `scripts/build.py`
- `scripts/validate.py`
- `obor_intelligence/source_analysis.py`
- `tests/test_v17_integration.py`
- `M6_STATUS.md`
- `README.md`

Expected first patched workflow behavior:

- source attribution is restored from the configured source registry;
- the recovered July 21–31 production-input signal is reprocessed because its M6 Key Data lacks a reporting period;
- stale signal directories are removed during `build.py`;
- `sitemap.xml` is regenerated from `data/signals.json`;
- `validate.py` checks source attribution, market-price periods, signal-directory hygiene, and sitemap coverage.

Regression result before packaging: **24/24 tests passed**.

The local live-source rehearsal was not used as evidence because source fetching exceeded the execution window in this environment. GitHub Actions remains the authoritative live verification run.
