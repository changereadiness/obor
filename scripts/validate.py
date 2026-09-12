#!/usr/bin/env python3
"""OBOR M6 quality gate.

This gate checks schema *and* semantic regressions. It is intentionally stricter
for real clean-engine signals than for retained illustrative demo records.
"""
from __future__ import annotations
import json, os, re, sys
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(os.environ.get('OBOR_ROOT', Path(__file__).resolve().parents[1])).resolve()
path=ROOT/'data/signals.json'
data=json.loads(path.read_text()) if path.exists() else []
errors=[]; seen=set()
allowed={'OPPORTUNITY','RISK','WATCH','NEUTRAL'}
FORBIDDEN=('1685797%','98677%','39022%','287744%')


def text_blob(s):
    parts=[s.get('title',''),s.get('summary',''),s.get('canadian_relevance',''),s.get('interpretation','')]
    wh=s.get('what_happened',[])
    parts.extend(wh if isinstance(wh,list) else [wh])
    for card in s.get('key_data',[]) or []:
        if isinstance(card,dict): parts.extend(str(v) for v in card.values())
    return ' '.join(str(x) for x in parts if x)

for s in data:
    sid=s.get('id')
    if not sid or sid in seen: errors.append(f'duplicate/missing id: {sid}')
    seen.add(sid)
    for k in ('title','slug','published_at','source','source_url','summary','what_happened','canadian_relevance','source_type','direction'):
        if not s.get(k): errors.append(f'{sid}: missing {k}')
    if s.get('opportunity_or_risk') not in allowed: errors.append(f'{sid}: invalid classification')
    try:
        if not 0<=int(s.get('relevance_score',-1))<=100: errors.append(f'{sid}: invalid relevance')
        if not 0<=int(s.get('confidence_score',-1))<=100: errors.append(f'{sid}: invalid confidence')
    except (TypeError,ValueError): errors.append(f'{sid}: non-numeric score')
    u=urlparse(s.get('source_url',''))
    if u.scheme not in {'http','https'} or not u.netloc: errors.append(f'{sid}: invalid source URL')
    if len(s.get('summary',''))<40: errors.append(f'{sid}: thin summary')

    if s.get('status') in ('demo','suppressed'):
        continue

    if s.get('synthesis_version') != 'clean-m6': errors.append(f'{sid}: not produced by clean-m6')
    if s.get('source') == 'Recovered from published signal page': errors.append(f'{sid}: recovery placeholder leaked into public source attribution')
    if not isinstance(s.get('what_happened'), list) or not (1<=len(s.get('what_happened',[]))<=6):
        errors.append(f'{sid}: what_happened must be 1-6 bullets')
    if not isinstance(s.get('key_data'), list) or not (1<=len(s.get('key_data',[]))<=5):
        errors.append(f'{sid}: key_data must be 1-5 cards')
    analysis=s.get('clean_analysis') or {}
    if analysis.get('status')!='ready': errors.append(f'{sid}: clean analysis not ready')
    profile=(analysis.get('draft') or {}).get('profile') or s.get('profile')
    blob=text_blob(s)
    for bad in FORBIDDEN:
        if bad in blob: errors.append(f'{sid}: historical parser artifact returned: {bad}')
    if profile in {'retail_sales','industrial_output'} and re.search(r'economic price movement|production-input price', blob, re.I):
        errors.append(f'{sid}: price-table semantics leaked into {profile}')
    if profile=='industrial_output' and re.search(r'factory demand', s.get('title',''), re.I):
        errors.append(f'{sid}: headline substitutes demand for measured output')
    for card in s.get('key_data',[]):
        if not isinstance(card,dict):
            errors.append(f'{sid}: malformed key_data card'); continue
        metric=card.get('metric'); value=str(card.get('value',''))
        if metric=='absolute_value' and value.endswith('%'):
            errors.append(f'{sid}: absolute value rendered as percentage')
        if metric in {'growth_rate_yoy','growth_rate_mom','price_change_rate'} and '%' not in value:
            errors.append(f'{sid}: rate lost percentage unit')
        label=str(card.get('label','')).lower()
        if metric=='growth_rate_yoy' and 'year-over-year growth' not in label:
            errors.append(f'{sid}: YoY key-data card does not explain its metric')
        if metric=='growth_rate_mom' and 'month-over-month growth' not in label:
            errors.append(f'{sid}: MoM key-data card does not explain its metric')
        if metric=='price_change_rate' and 'price change' not in label:
            errors.append(f'{sid}: price-change key-data card does not explain its metric')
        if metric=='dataset_distribution' and not any(term in label for term in ('price decreases','price increases','unchanged prices')):
            errors.append(f'{sid}: distribution key-data card does not explain what the count represents')
        if profile=='market_prices' and not card.get('period'):
            errors.append(f'{sid}: market-price key-data card missing reporting period')


# Build hygiene: after build.py, the generated signal tree and sitemap must be
# exact projections of the canonical published ledger.
publishable = [s for s in data if s.get('status') not in ('demo','suppressed')]
expected_slugs = {s.get('slug') for s in publishable if s.get('slug')}
signals_dir = ROOT/'signals'
if signals_dir.exists():
    actual_slugs = {p.name for p in signals_dir.iterdir() if p.is_dir() and (p/'index.html').exists()}
    stale = actual_slugs - expected_slugs
    missing = expected_slugs - actual_slugs
    if stale: errors.append('stale generated signal pages: ' + ', '.join(sorted(stale)))
    if missing: errors.append('missing generated signal pages: ' + ', '.join(sorted(missing)))

sitemap_path = ROOT/'sitemap.xml'
if sitemap_path.exists():
    sitemap = sitemap_path.read_text(errors='ignore')
    for slug in expected_slugs:
        if f'https://obor.ca/signals/{slug}/' not in sitemap:
            errors.append(f'sitemap missing current signal: {slug}')
    for slug in actual_slugs - expected_slugs if signals_dir.exists() else []:
        if f'https://obor.ca/signals/{slug}/' in sitemap:
            errors.append(f'sitemap contains stale signal: {slug}')
else:
    errors.append('missing sitemap.xml')

if errors:
    print('\n'.join(errors)); sys.exit(1)
print(f'Quality gate passed: {len(data)} signals')
