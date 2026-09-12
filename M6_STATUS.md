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

---

## PRE-LAUNCH HARDENING ADDENDUM — recovery and publishing hygiene

The production-candidate audit identified three activation-adjacent defects that do not require a new milestone:

1. recovered signal pages could leak the internal label `Recovered from published signal page` into public source attribution;
2. a recovered market-price signal could lose its reporting period when its original source title was no longer present in the current ingestion window;
3. static generation did not remove obsolete signal directories or regenerate the sitemap from the canonical signal ledger.

The M6 pre-launch hardening patch addresses these within the existing architecture:

- source identity is restored from the configured source registry;
- `source_title` and `reporting_period` are persisted as provenance metadata;
- recovery can restore a reporting period from surviving generated source-title slugs before those stale pages are removed;
- already-M6 records are reprocessed when they still carry known recovery defects;
- `build.py` removes signal directories not present in `data/signals.json` and regenerates `sitemap.xml` from the same canonical ledger;
- `validate.py` rejects leaked recovery placeholders, missing market-price periods, stale generated signal pages, and sitemap omissions;
- the regression suite now contains 27 tests, including exact reproductions of the recovered-source/missing-period failure and the homepage stale-TODAY failure.

This remains **M6**. It is pre-launch hardening, not a new product milestone.


## PRE-LAUNCH HARDENING ADDENDUM — truthful daily homepage state

A subsequent live-site check found that the homepage could label an archived signal date as `TODAY`. That is not acceptable for a daily intelligence product, especially because OBOR explicitly treats a quiet day as valid intelligence.

The M6 homepage hardening patch now:

- derives the displayed TODAY date from the visitor's current calendar date rather than a hard-coded archive date;
- shows `No major signals detected today.` when no published signal matches that date;
- renders same-day signals separately when they do exist;
- presents the most recent older records under a distinct `LATEST SIGNALS` section and shows their actual latest publication date;
- excludes `demo` and `suppressed` records from both homepage states;
- fails gracefully if the canonical signal ledger cannot be loaded;
- extends `validate.py` so the dynamic TODAY/LATEST contract is part of the production quality gate;
- adds dedicated homepage regression coverage.

This remains **M6**. It changes presentation truthfulness only; the intelligence architecture, source coverage, publication gate, and signal schema are unchanged.


## PRE-LAUNCH OBSERVABILITY ADDENDUM — freshness and source health

The M6 production engine is frozen semantically. The next PRE-LAUNCH hardening step adds read-only observability so recurring production runs can distinguish source freshness from pipeline health.

This patch does **not** add sources, loosen publication thresholds, change sector taxonomy, or alter editorial synthesis.

It adds:

- stable `first_seen_at` and `last_seen_at` timestamps for normalized source items;
- corrected collection telemetry separating `fetched`, `discovered_new`, and `cached` counts;
- source failure streaks plus last-success timestamps where known;
- `publication_gate.json`, which explains why every synthesized candidate was published, already existed, or was held back;
- `prelaunch_health.json`, which consolidates source status, reference-date freshness, synthesis outcomes, and publication-gate counts;
- workflow output from `prelaunch_health.py` after each production pipeline run;
- explicit labeling of title-derived statistical reference dates so they cannot be confused with publication dates;
- regression coverage for discovery semantics, first-seen persistence, source-health reporting, and statistical reference-date inference.

Current regression suite: **30 / 30 passing**.

This remains **M6**. It is operational observability around the frozen engine, not a new intelligence milestone.

## PRE-LAUNCH discovery identity hardening

Freshness observability exposed that raw IDs historically hash URL + title, which could make an official headline edit appear as a new discovery. Discovery identity now uses the canonical URL while preserving prior raw IDs and first-seen timestamps across title edits. This changes telemetry only; publication behavior is unchanged.

Regression suite: **31 / 31 passed**.
