# OBOR M6 — PRE-LAUNCH Freshness & Source Health Patch

## Scope

Read-only production observability. No new source, editorial profile, threshold, taxonomy, or AI capability is introduced.

## What changes

1. Ingestion preserves stable first-seen and last-seen timestamps.
2. Workflow collection telemetry now distinguishes fetched items from genuinely new discoveries.
3. Per-source health records track consecutive failures and last successful collection where known.
4. The deterministic publication gate emits reason codes for every candidate.
5. `scripts/prelaunch_health.py` writes a cross-stage health report and concise workflow summary.
6. Statistical title reference periods may be used for freshness context only and are explicitly labeled as reference periods, never publication dates.

## New diagnostic files

- `data/raw/publication_gate.json`
- `data/raw/prelaunch_health.json`

## Expected workflow output

Conceptually:

```text
Collection state: degraded; fetched=34 discovered_new=0 cached=37
publication_gate={...}
source_health=4/7 ok degraded=3
degraded_sources=WTO — News[streak=1], IMF — News[streak=1], OECD — News[streak=1]
collection_freshness=fetched=34 discovered_new=0 cached=37
source_reference_freshness=...
candidate_synthesis={...}
```

Failure streaks increase only on consecutive failed runs. A successful run resets a source's streak to zero.

## Acceptance

- full regression suite passes;
- production workflow still publishes exactly according to the existing M6 gate;
- no source-health metric changes publication eligibility;
- first patched production run produces both diagnostic JSON files;
- subsequent run proves first-seen timestamps persist and degraded-source streaks increment/reset correctly.

This is M6 PRE-LAUNCH hardening, not M7.
