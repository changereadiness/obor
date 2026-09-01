# OBOR.ca

China Economic Intelligence for Canadian Business.

## MVP architecture

Static HTML/CSS/JS + structured JSON + GitHub Pages. The current records are explicitly demo records and should be replaced before production publication.

## Intended autonomous pipeline

`source adapters → normalize → deduplicate → deterministic filter → AI candidate analysis → classify/score → quality gate → JSON store → static build → GitHub Pages`

## Next implementation steps

1. Add RSS/public-source adapters in `scripts/`.
2. Normalize all incoming items into a raw-item schema.
3. Add deterministic filtering and URL/title similarity deduplication.
4. Add AI analysis only after candidates pass the deterministic gate.
5. Generate validated signal JSON and individual signal pages.
6. Add a quality gate that rejects missing sources, unsupported claims, low confidence and thin signals.
7. Generate sitemap and sector/category pages from the same signal store.
8. Add GitHub Actions schedule for daily collection/build/deploy.
9. Add an override file for suppression, verification and score/classification corrections.
