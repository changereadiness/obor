# OBOR

**China Economic Intelligence for Canadian Business**

OBOR is an automated, static economic-intelligence publishing system. It monitors selected Canadian, Chinese and international institutional sources, identifies China-related economic developments, converts structured source evidence into typed observations, synthesizes concise business intelligence for a Canadian audience, validates the output, and publishes static pages through GitHub Pages.

The product question is:

> **What is happening in China that Canadian business should know about?**

The system is intentionally conservative. It is designed to prefer **no signal** over a signal whose meaning cannot be established from source evidence.

---

## 1. Current release

**Release:** M6 Production Candidate  
**Intelligence engine:** `clean-m6`  
**Signal schema:** `clean-1`  
**Runtime:** Python 3.12 in GitHub Actions  
**External Python dependencies:** none; standard library only  
**Hosting:** GitHub Pages  
**Scheduled execution:** daily at 00:15 UTC

M6 is built on the clean reconstruction introduced in M1–M5. The V17 operational shell was retained where it had proven useful; the statistical extraction and synthesis path was replaced with a header-aware, test-first semantic intelligence engine.

### M6 scope

M6 deliberately changes only the **Key Data presentation contract**.

M5 produced numerically correct Key Data. M6 makes each number self-describing so that the reader does not need to infer the metric from the surrounding article.

Example:

```text
+4.5%
Industrial value added — year-over-year growth
July
```

instead of:

```text
+4.5%
Industrial value added
July
```

For production-input basket statistics:

```text
31 of 50
Monitored production inputs with price decreases
62% of monitored basket · August 1–10 2026
```

No other editorial field is intentionally changed in M6.

See `M6_STATUS.md` for the release-specific acceptance notes.

---

## 2. Product model

OBOR is not intended to be a general news scraper. Its transformation is:

```text
source information
    -> screened economic candidate
    -> structured source evidence
    -> semantic observations
    -> validated intelligence
    -> Canadian business relevance
    -> static signal record
    -> published page
```

A signal contains separate editorial layers with separate responsibilities:

| Field | Responsibility |
|---|---|
| Headline | State what happened, using the measured variable |
| Summary | Explain why the development matters |
| Canadian Relevance | Explain why a Canadian business should care |
| What Happened | Present source-grounded factual bullets |
| Key Data | Surface the few numbers that explain the signal, with explicit metric meaning |
| What the Data Shows | Provide a short analytical interpretation |
| Sectors | Identify business sectors potentially affected |
| Source | Preserve provenance and the original source URL |

A core editorial invariant is:

> **No field should silently substitute inference for the source's measured variable.**

For example, an industrial-production release may support a headline about industrial output. It must not be rewritten as a headline about "factory demand" unless demand itself is measured.

---

## 3. Architecture

### 3.1 Production data flow

```text
data/sources.json
       |
       v
scripts/ingest.py
       |
       | normalized/cached source items
       v
data/raw/items.json
       |
       v
scripts/pipeline.py
       |
       | candidate screening / scoring / recovery
       v
scripts/clean_adapter.py
       |
       v
scripts/source_fetch.py
       |
       v
obor_intelligence/source_analysis.py
       |
       +------------------------------+
       |                              |
       v                              v
semantic_tables.py                evidence.py
       |                              |
       +--------------+---------------+
                      |
                      v
                 editorial.py
                      |
                      v
              clean signal draft
                      |
                      v
              data/signals.json
                      |
             +--------+---------+
             |                  |
             v                  v
       scripts/build.py    scripts/validate.py
             |                  |
             v                  v
        static HTML         quality gate
             |
             v
        GitHub Pages
```

### 3.2 Architectural boundary

The active pipeline deliberately separates:

1. **Collection** — retrieve candidate source items.
2. **Screening** — determine whether an item merits deeper analysis.
3. **Extraction** — reconstruct structured tables and preserve their semantics.
4. **Evidence validation** — reject inconsistent or unsupported observations.
5. **Editorial synthesis** — convert validated observations into a human-readable signal.
6. **Persistence** — store the canonical structured signal.
7. **Rendering** — render persisted data without reinterpreting it.
8. **Validation** — enforce schema and known semantic invariants before commit/deployment.

Rendering is intentionally dumb. `scripts/build.py` must never become an intelligence layer.

---

## 4. Repository layout

```text
.github/workflows/
  daily.yml                 scheduled intelligence pipeline
  deploy.yml                GitHub Pages deployment

assets/
  app.js
  style.css

data/
  sources.json              source registry
  overrides.json            human overrides / suppression hooks
  signals.json              canonical persisted signal ledger
  raw/
    items.json              normalized collected items
    candidates.json         screened candidates
    rejections.json         rejected items and reasons
    ingest_log.json         source health and collection diagnostics

obor_intelligence/
  semantic_tables.py        header-aware table reconstruction + observations
  evidence.py               validated evidence primitives and selection
  editorial.py              deterministic editorial synthesis
  source_analysis.py        source-page -> analysis orchestration
  records.py                stable signal-record contract
  publisher.py              isolated test/sandbox renderer
  parse_table.py            supporting table parsing utilities
  demo.py                   development/demo utilities

scripts/
  ingest.py                 production collector
  pipeline.py               screening, scoring, recovery, persistence
  clean_adapter.py          bridge from operational shell to clean engine
  source_fetch.py           source-page retrieval
  build.py                  production static page renderer
  validate.py               production quality gate
  run.py                    stage orchestrator
  legacy_synthesis_v17.py   forensic reference only; not active
  ai_adapter.py             reserved boundary; deliberately unused

tests/
  fixtures/
    production_inputs.html
    retail_sales.html
    industrial_production.html
  test_semantic_tables.py
  test_evidence.py
  test_editorial.py
  test_clean_end_to_end.py
  test_v17_integration.py
```

`legacy_synthesis_v17.py` is retained only to preserve development history and facilitate forensic comparison. No active production module should import it.

---

## 5. Source collection

Sources are defined declaratively in `data/sources.json`.

Current enabled source families:

- Government of Canada — News
- Global Affairs Canada — News
- National Bureau of Statistics of China — Latest Releases
- WTO — News
- IMF — News
- OECD — News
- World Bank — News

### 5.1 Collection strategy

Collection is **page-first**:

1. Fetch configured HTML page(s).
2. Extract matching article links.
3. If page extraction fails, try configured RSS/Atom fallback(s).
4. If a source fails completely, log the failure and continue.
5. Merge new items with the cached item ledger.

One failing source must not crash the daily pipeline.

### 5.2 Degraded collection

A run may legitimately report:

```text
Collection state: degraded
```

when one or more sources fail while others succeed.

At the M6 checkpoint, WTO page parsing and the WTO feed are unreliable in the current configuration, while IMF and OECD commonly return HTTP 403 from GitHub-hosted execution. These conditions are known and non-fatal. They should be treated as source-adapter maintenance work, not as evidence that the intelligence pipeline failed.

The important operational distinction is:

```text
source unavailable != pipeline unavailable
```

---

## 6. Candidate screening and scoring

`scripts/pipeline.py` retains the deterministic screening layer inherited from the V17 operational shell.

It uses source provenance plus lexical evidence for:

- China relevance
- Canadian relevance
- commercial/economic relevance
- category cues
- sector cues
- opportunity/risk language
- factual/action verbs
- recency

The screening layer is intentionally coarse. It decides whether an item is worth deeper analysis; it is **not** the final semantic authority for statistical content.

### 6.1 Publication gate

A candidate must meet minimum relevance/confidence conditions and obtain usable evidence before publication.

A strong primary Chinese economic signal may qualify even when the source does not explicitly mention Canada. In that case the Canadian implication is generated as analysis and must remain cautious rather than being misrepresented as a source fact.

### 6.2 Known limitation

The scoring system remains heuristic. Scores are editorial ranking aids, not calibrated probabilities or objective measurements.

---

## 7. Semantic table engine

The principal architectural correction in the clean reconstruction is the removal of flattened-table inference.

The unsafe historical pattern was approximately:

```text
HTML
 -> flattened text
 -> regex
 -> number
 -> guess what the number means
```

That produced errors such as:

- retail absolute values interpreted as percentages;
- industrial robot output interpreted as a percentage;
- industrial-production growth interpreted as price movement;
- product-specification percentages interpreted as economic movements;
- sign/direction loss.

The clean engine uses:

```text
HTML table
 -> rowspan/colspan expansion
 -> header paths
 -> row/column relationship
 -> metric classification from header context
 -> typed Observation
 -> validation
```

### 7.1 Observation contract

The central semantic primitive is `Observation` in `semantic_tables.py`.

Conceptually:

```text
Observation
  subject
  metric
  value
  unit
  period
  comparison
  direction
  source_table
  row_index
  column_index
  raw_value
  header_path
```

Supported metric types currently include:

```text
growth_rate_yoy
growth_rate_mom
price
price_change
price_change_rate
absolute_value
rate
```

The key invariant is:

> **A number receives economic meaning from its header and row context, not from its visual format.**

`39022` is not inherently a price. `0.6%` is not inherently a price movement.

### 7.2 Header reconstruction

Multi-row and merged headers are normalized before interpretation.

For a source table such as:

```text
                    July                  January–July
               Absolute  Growth Y/Y    Absolute  Growth Y/Y
```

the parser preserves column paths equivalent to:

```text
July -> Absolute Value
July -> Growth Rate Y/Y
January–July -> Absolute Value
January–July -> Growth Rate Y/Y
```

That relationship is the basis for typed observations.

---

## 8. Evidence layer

`obor_intelligence/evidence.py` sits between extraction and editorial synthesis.

Its responsibilities are deliberately narrow:

- preserve typed observations;
- validate dataset-level distribution statements;
- select concise evidence;
- format values without changing their type;
- keep population distributions separate from row-level observations.

### 8.1 Dataset observations

For production-input releases, source prose may state an explicit distribution such as:

```text
50 monitored products
12 increased
31 decreased
7 unchanged
```

This becomes a separate `DatasetObservation` and is validated with:

```text
increased + decreased + unchanged == population
```

The engine does not infer a missing count merely because it could be derived arithmetically. The source must establish the necessary values.

### 8.2 Evidence ordering

For market-basket releases, an explicit distribution can take precedence over individual product moves because it better describes the breadth of the signal.

For retail and industrial-production tables, evidence selection prioritizes the main measured series and relevant comparison series.

---

## 9. Editorial synthesis

`obor_intelligence/editorial.py` consumes validated structured evidence only. It does not fetch source pages and does not parse raw HTML.

Current deterministic profiles:

- `market_prices`
- `retail_sales`
- `industrial_output`
- `generic_statistical` fallback

Each profile provides:

- measured-variable constraints;
- headline construction;
- summary logic;
- Canadian relevance language;
- factual bullet construction;
- Key Data selection;
- interpretation;
- sector mapping.

### 9.1 Key Data contract — M6

Each Key Data card contains:

```text
value
label
period
metric
context
```

The `label` is now required to explain the economic meaning of the value.

Examples:

```json
{
  "value": "+0.6%",
  "label": "Total retail sales — year-over-year growth",
  "period": "July",
  "metric": "growth_rate_yoy"
}
```

```json
{
  "value": "-7.3%",
  "label": "Pure Benzene (Petroleum Benzene, Industrial Grade) — price change vs previous period",
  "period": "August 1-10 2026",
  "metric": "price_change_rate"
}
```

Dataset distribution example:

```json
{
  "value": "31 of 50",
  "label": "Monitored production inputs with price decreases",
  "context": "62% of monitored basket",
  "period": "August 1-10 2026",
  "metric": "dataset_distribution"
}
```

The production renderer displays the dataset percentage alongside the period.

---

## 10. Signal persistence

`data/signals.json` is the canonical signal ledger.

Generated pages are derived artifacts. They are not supposed to become the primary database.

The clean record contract is defined in `obor_intelligence/records.py`; the production pipeline adds operational fields required by the existing shell.

Important fields include:

```text
id
slug
title
published_at
source
source_url
source_type
summary
canadian_relevance
what_happened[]
key_data[]
interpretation
sectors[]
categories[]
opportunity_or_risk
relevance_score
confidence_score
profile
status
clean_analysis
synthesis_version
```

### 10.1 Versioning

The intelligence engine writes:

```text
synthesis_version = clean-m6
```

The version is used by the reprocessing path. Existing real signals synthesized by an older engine version are candidates for re-fetch and re-synthesis.

M6 intentionally bumps the version from `clean-m5` so live signals receive the explicit Key Data labels.

---

## 11. Recovery behavior

The operational shell retains a self-healing recovery mechanism.

Normal state:

```text
data/signals.json -> generated signal pages
```

Recovery state:

```text
published signal pages
 -> recover minimum signal metadata
 -> restore ledger candidates
 -> re-fetch source
 -> re-synthesize through clean engine
 -> rewrite canonical signal record
```

This exists to survive accidental ledger/package replacement. It is not intended as the normal persistence mechanism.

Demo pages are excluded from recovery as real published signals.

If a source is temporarily unavailable during reprocessing, the existing valid signal is preserved rather than destroyed.

---

## 12. Rendering

`scripts/build.py` renders the persisted signal contract into static HTML.

It must not:

- infer metrics;
- parse source data;
- change signs;
- generate editorial conclusions;
- repair malformed intelligence.

If intelligence is malformed, validation should fail upstream.

This boundary exists specifically to prevent presentation code from becoming another hidden semantic engine.

---

## 13. Validation and regression protection

There are two complementary mechanisms:

1. unit/integration tests under `tests/`;
2. the production quality gate in `scripts/validate.py`.

### 13.1 Current test result

M6 freeze result:

```text
23 tests passed
```

Run with:

```bash
python -m unittest discover -s tests -v
```

### 13.2 Mandatory regression fixtures

The three statistical structures that historically exposed semantic failures are permanent fixtures:

1. production-input market prices;
2. retail sales;
3. industrial production.

They are intentionally different even though their source HTML can look superficially similar.

### 13.3 Historical failures explicitly blocked

The suite prevents regression to known bogus outputs including:

```text
39022%
287744%
1685797%
98677%
```

It also rejects:

- retail or industrial data described as `economic price movement`;
- industrial-output headlines that substitute `factory demand` for measured output;
- positive/negative sign loss;
- absolute values rendered as percentages;
- percentage metrics rendered without `%`;
- Key Data rate cards that fail to explain the metric;
- demo pages recovered as real signals.

### 13.4 Quality-gate philosophy

Compilation is not acceptance.

Static page generation is not acceptance.

A successful GitHub Action is not by itself acceptance.

A change to the intelligence engine should be considered acceptable only when the relevant semantic fixtures and integration path pass and the resulting signal output remains source-faithful.

---

## 14. Test layers

### `test_semantic_tables.py`

Tests table reconstruction and typed observations:

- `rowspan` / `colspan` expansion;
- period preservation;
- metric identification;
- signs and direction;
- product specification exclusion;
- absolute values remaining absolute values;
- industrial quantities remaining quantities/values rather than rates.

### `test_evidence.py`

Tests:

- dataset arithmetic integrity;
- refusal to invent incomplete distributions;
- evidence ordering;
- value formatting;
- dataset context.

### `test_editorial.py`

Tests:

- profile selection;
- measured-variable-safe headlines;
- editorial field construction;
- Key Data selection;
- explicit M6 Key Data labels.

### `test_clean_end_to_end.py`

Tests:

```text
source fixture
 -> analysis
 -> signal record
 -> HTML
```

for all three statistical families.

### `test_v17_integration.py`

Tests the clean engine inside the retained operational shell, including:

- V17-style screening/reprocessing;
- persistence;
- page generation;
- quality gate;
- recovery after deleting `signals.json`;
- full `run.py` fixture orchestration.

---

## 15. Local development

From the repository root:

### Compile

```bash
python -m compileall -q obor_intelligence scripts tests
```

### Run tests

```bash
python -m unittest discover -s tests -v
```

### Run the production-style pipeline

```bash
python scripts/run.py
```

This invokes:

```text
ingest.py
pipeline.py
build.py
```

### Run the quality gate

```bash
python scripts/validate.py
```

### Build only

```bash
python scripts/build.py
```

---

## 16. Fixture-mode integration testing

The ingestion and source-fetch layers support environment-driven fixtures so the pipeline can be exercised without network access.

This is important: semantic correctness must not depend on GitHub Actions being used as a debugging environment.

The test suite uses fixtures to verify the complete path before live-source execution.

When adding a new source/table family, create a representative fixture and expected observations before connecting it to the production pipeline.

---

## 17. CI / GitHub Actions

### Daily intelligence workflow

`.github/workflows/daily.yml`

Runs daily at:

```text
00:15 UTC
```

Stages:

```text
checkout
 -> Python 3.12
 -> scripts/run.py
 -> scripts/validate.py
 -> commit generated intelligence if changed
 -> push
```

The workflow has `contents: write` permission because successful runs may update generated intelligence and persisted data.

### Pages workflow

`.github/workflows/deploy.yml`

On `main` push:

```text
checkout
 -> build static signal pages
 -> upload Pages artifact
 -> deploy GitHub Pages
```

---

## 18. Operational state and acceptance evidence

The M5 clean reconstruction was exercised through the real GitHub Actions environment before M6.

A representative accepted run collected:

```text
Government of Canada: 2 items
Global Affairs Canada: 1 item
NBS China: 15 items
World Bank: 16 items
```

while WTO, IMF and OECD degraded independently without terminating the run.

The pipeline completed:

```text
raw=34
screened=14
candidates=14
rejected=20
published_new=0
updated_existing=0
unchanged=6
total=6
```

and successfully reached `build.py` with no traceback.

The published intelligence was manually inspected and found materially more readable and semantically correct than the pre-reconstruction output.

M6 preserves that architecture and only makes Key Data labels explicit.

---

## 19. Adding a source

Do not begin by editing ingestion code.

Preferred sequence:

1. Add a declarative source entry to `data/sources.json`.
2. Verify HTML-page collection rules.
3. Configure RSS/Atom fallback if available.
4. Confirm that source failure remains non-fatal.
5. Add source-specific code only if the generic page-first adapter cannot safely support the source.

Any source adapter should preserve:

```text
failure isolation
cached previous items
provenance
publication date when available
original URL
```

---

## 20. Adding a new statistical table family

This is the highest-risk extension point.

Do **not** add a source-specific regex directly to editorial synthesis.

Required process:

1. Save a representative source HTML table as a test fixture.
2. Determine the real header hierarchy.
3. Extend `metric_from_path()` only if the header introduces a genuinely new semantic metric.
4. Assert the expected `Observation` objects.
5. Add validation for units/signs/comparisons.
6. Add evidence-selection tests.
7. Add or extend an editorial profile only after extraction is correct.
8. Add source-to-HTML end-to-end regression coverage.
9. Run the operational-shell integration suite.
10. Only then enable live-source use.

Core rule:

> **Never derive economic meaning from flattened page text when a structured table supplies that meaning explicitly.**

---

## 21. Adding an editorial profile

A new editorial profile belongs in `editorial.py` only when the source evidence has already been typed and validated.

A profile must define:

- the measured variable;
- primary subject detection;
- valid headline semantics;
- factual bullet construction;
- Key Data selection;
- interpretation boundaries;
- affected sectors.

A profile must not compensate for broken extraction.

If editorial code needs to guess column meaning, fix extraction instead.

---

## 22. Human overrides

`data/overrides.json` provides a lightweight control surface without an admin application.

The current design supports source suppression and per-signal overrides.

The intended philosophy is:

```text
automation by default
human override when necessary
no manual CMS dependency
```

Any future override mechanism should remain auditable and should not silently mutate source evidence.

---

## 23. AI boundary

The current production intelligence engine is deterministic.

`ai_adapter.py` exists as a reserved boundary but is not part of the active pipeline.

This is deliberate.

If an AI layer is introduced later, the recommended boundary is:

```text
validated evidence
 -> optional AI interpretation
 -> deterministic schema validation
 -> deterministic publication gate
```

AI should not be responsible for reconstructing malformed tables when deterministic source structure is available.

The publication gate and semantic invariants should remain deterministic even if AI-assisted synthesis is introduced.

---

## 24. Reliability principles

The system currently follows these rules:

### Fail closed on intelligence

If structured evidence cannot be established, do not publish a newly synthesized signal.

### Fail open on source collection

If one source is unavailable, continue processing healthy sources.

### Preserve last known valid state

If re-fetch/re-synthesis fails for an existing valid signal, preserve the existing record rather than replacing it with incomplete output.

### Keep provenance

Every published signal must retain a valid source URL.

### Separate fact from analysis

Source observations and Canadian business implications are not interchangeable.

### Test known failures permanently

Every material parser failure should become a regression fixture or assertion.

---

## 25. Known limitations

A senior reviewer should assume the following areas remain intentionally incomplete or heuristic:

1. **Source breadth** — only a small set of institutional sources is configured.
2. **Source adapters** — WTO, IMF and OECD currently degrade in production collection.
3. **Statistical table coverage** — the semantic engine has strong coverage for the three NBS structures in the regression suite, not every statistical presentation used by NBS or other agencies.
4. **Non-tabular releases** — the clean engine is currently optimized for structured statistical evidence. Text-only economic releases may require additional evidence primitives.
5. **Screening/scoring** — relevance and confidence scores remain rule-based heuristics.
6. **Classification** — opportunity/risk/watch classification is intentionally conservative and not a forecasting model.
7. **Recovery parsing** — published-page recovery is a resilience mechanism and is inherently more brittle than canonical JSON persistence.
8. **Observability** — console logs and JSON artifacts are adequate for the current scale but are not a full telemetry/alerting system.
9. **No database** — persistence is Git-backed JSON by design; this is appropriate for current volume but establishes an eventual scale ceiling.
10. **No concurrency controls inside the pipeline** — GitHub workflow concurrency and repository writes should be reviewed if execution frequency or source count grows materially.

---

## 26. Security and trust considerations

The current system does not accept public user input and does not execute source-provided scripts.

Relevant review areas include:

- network fetch timeouts and maximum payload sizes;
- HTML parsing behavior on malformed source pages;
- URL provenance and redirect handling;
- GitHub Actions permissions;
- generated HTML escaping;
- source-content size limits;
- denial-of-service resistance if source breadth increases;
- supply-chain risk if third-party dependencies are introduced later.

The current standard-library-only implementation materially reduces Python package supply-chain exposure.

---

## 27. Cost model

The current target is effectively **$0/month** for the base system:

- GitHub repository
- GitHub Actions within available quota
- GitHub Pages
- public HTML/RSS sources
- Python standard library
- deterministic analysis

No paid API is required for M6.

---

## 28. Engineering review priorities

For a senior engineer reviewing this codebase, the highest-value review questions are:

1. Are the module boundaries between ingestion, extraction, evidence, synthesis and rendering sufficiently hard?
2. Is `data/signals.json` being treated consistently as the canonical ledger?
3. Are recovery semantics safe under partial source failure?
4. Can the table parser tolerate realistic malformed/multi-level HTML without silently assigning the wrong metric?
5. Are metric types sufficiently explicit, or should the Observation model become a stricter enum/value-object model?
6. Should profile selection remain deterministic pattern matching or move toward a declarative registry?
7. Should publication schema validation migrate to a formal JSON Schema or typed model?
8. Are relevance/confidence scores useful enough to retain in their current heuristic form?
9. Should source fetching, ingestion and reprocessing expose structured health metrics rather than console-only diagnostics?
10. At what signal/source volume does Git-backed JSON cease to be the appropriate persistence layer?

The highest-risk code is not the HTML renderer. It is any code that can silently assign the wrong semantic meaning to source evidence.

---

## 29. Non-goals at the current stage

Do not expand the project into these areas until the intelligence core is stable:

- user accounts;
- subscriptions/payments;
- personalized dashboards;
- comments/social features;
- chatbot UI;
- mobile application;
- complex CMS/admin interface;
- large database migration;
- unnecessary client-side animation;
- AI added merely for branding.

The current engineering objective remains:

> **A small, dependable machine that produces readable, source-grounded economic intelligence with minimal human intervention.**

---

## 30. Release discipline

The project no longer treats successive ZIP patches as proof of progress.

The current release discipline is:

```text
known-good baseline
 -> isolated change
 -> fixture test
 -> semantic regression test
 -> integration test
 -> production candidate
 -> live run
 -> manual output inspection
 -> freeze/tag
```

Any future architectural change should preserve a known-good production checkpoint and should be rejected if it cannot be tested independently before deployment.

---

## 31. Quick reviewer checklist

Before approving a change to the intelligence path:

```text
[ ] python -m compileall -q obor_intelligence scripts tests
[ ] python -m unittest discover -s tests -v
[ ] all semantic fixtures pass
[ ] no historical parser artifact reappears
[ ] Key Data labels state the metric explicitly
[ ] source URL/provenance remains intact
[ ] build.py performs rendering only
[ ] validate.py passes
[ ] source failure does not destroy existing valid signals
[ ] synthesis_version intentionally reflects the engine release
[ ] live output is manually inspected after meaningful semantic changes
```

For M6 specifically, the expected engine version is:

```text
clean-m6
```

---

## M6 pre-launch hardening status

A post-activation production audit added a narrow hardening layer without changing the M6 intelligence architecture. Recovery now preserves canonical source identity and reporting-period provenance, static builds remove obsolete signal pages, the sitemap is generated from the canonical signal ledger, and the homepage distinguishes the current day from the latest archived signal date. Quiet days are rendered explicitly as `No major signals detected today.` rather than relabelling older intelligence as current. The quality gate checks these production invariants. The current regression suite contains **27 tests**.
