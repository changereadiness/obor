# OBOR Clean Reconstruction — M6 Production Candidate

## Status

**PRODUCTION CANDIDATE**

M6 is a deliberately narrow release on top of the live-tested M5 reconstruction. It does not alter ingestion, semantic extraction, evidence selection, editorial hierarchy, screening, recovery, persistence, or deployment architecture.

The only product-facing change is **Key Data semantic clarity**.

## Change from M5

M5 made Key Data numerically correct. M6 makes each card explicit about what the number represents.

Examples:

```text
M5
+4.5%
Industrial value added
July

M6
+4.5%
Industrial value added — year-over-year growth
July
```

```text
M5
31 of 50
Decreased
August 1–10 2026

M6
31 of 50
Monitored production inputs with price decreases
62% of monitored basket · August 1–10 2026
```

This removes the need for a reader to infer the metric from surrounding context.

## Engine version

`clean-m6`

The version bump is intentional. Existing real signals with `synthesis_version=clean-m5` will be reprocessed by the next pipeline run so the new Key Data labels propagate to published pages.

## Architectural changes

None.

The active path remains:

```text
ingest.py
  -> pipeline.py
  -> clean_adapter.py
  -> source_fetch.py
  -> obor_intelligence/source_analysis.py
  -> semantic_tables.py
  -> evidence.py
  -> editorial.py
  -> data/signals.json
  -> build.py
  -> validate.py
```

## Regression requirements

M6 adds tests and validation rules requiring Key Data cards to explain their metric:

- YoY rates must say `year-over-year growth`.
- MoM rates must say `month-over-month growth`.
- production-input movements must say `price change`.
- dataset distribution counts must state whether they represent price decreases, increases, or unchanged prices.

Historical parser artifacts remain blocked.

## Deployment expectation

A successful M6 production run should show existing real signals as reprocessed/updated because the synthesis version changed from `clean-m5` to `clean-m6`. Source degradation for WTO, IMF and OECD remains a known non-fatal ingestion condition.
