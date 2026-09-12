# OBOR PRE-LAUNCH — Discovery Identity Hardening

## Purpose

Correct PRE-LAUNCH freshness telemetry so an official publisher editing an existing article title does not create a false `discovered_new` event.

## Root cause

Historical raw item IDs hash `URL + title`, while OBOR's deduplication treats URL as the canonical source-item locator. A title change could therefore produce a new raw ID even though the underlying source URL was already known.

## Change

- Canonical discovery identity is now based on normalized source URL.
- Raw ID remains backward compatible and is preserved from the prior observation when the URL is unchanged.
- `first_seen_at` is preserved across title edits.
- New discovery counts now use canonical identity rather than title-derived raw IDs.

## Non-goals

No changes to screening, semantic extraction, editorial synthesis, publication thresholds, source coverage, or site rendering.

## Regression protection

Added a test proving that a changed title on the same URL:

- reports `items_discovered = 0`;
- preserves the original raw ID;
- preserves `first_seen_at`.

Full suite: **31 / 31 tests passed**.
