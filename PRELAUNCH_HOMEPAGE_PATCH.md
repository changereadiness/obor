# OBOR M6 Pre-Launch Homepage Truthfulness Patch

Apply these files over the already-hardened M6 repository, then run **OBOR Daily Intelligence** once.

Changed files:

- `index.html`
- `assets/app.js`
- `assets/style.css`
- `scripts/validate.py`
- `tests/test_homepage_state.py`
- `tests/test_v17_integration.py`
- `M6_STATUS.md`
- `README.md`

## Purpose

The live homepage previously presented an archived date as `TODAY`. This patch separates the current calendar state from the latest archived intelligence.

Expected behavior:

- `TODAY` displays the visitor's current calendar date.
- If no published signal has that date, the homepage states: `No major signals detected today.`
- If same-day signals exist, only those signals appear in the TODAY block.
- Older signals appear under a separate `LATEST SIGNALS` block with the actual latest publication date.
- `demo` and `suppressed` records cannot appear on the homepage.
- If `data/signals.json` cannot be loaded, the page reports temporary unavailability rather than claiming a quiet day.
- `validate.py` enforces the dynamic TODAY/LATEST structure and quiet-day contract.

## Verification

Regression suite before packaging: **27/27 tests passed**.

A browser-logic rehearsal with the clock fixed at September 12, 2026 and the latest real archived signal dated September 9, 2026 produced:

```text
TODAY: September 12, 2026
No major signals detected today.
LATEST SIGNALS: September 9, 2026
```

A same-day `demo` fixture was excluded from the homepage feed.

This is **M6 pre-launch hardening**, not M7.
