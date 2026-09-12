#!/usr/bin/env python3
"""PRE-LAUNCH observability for OBOR freshness and source health.

This script changes no editorial decision and publishes no signal. It summarizes
what the existing deterministic pipeline observed so source degradation,
collection freshness and publication-gate behavior are visible in every run.
"""
from __future__ import annotations

import calendar
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(os.environ.get('OBOR_ROOT', Path(__file__).resolve().parents[1])).resolve()
RAW = ROOT / 'data' / 'raw'
DATA = ROOT / 'data'
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTH_RE = '|'.join(name.title() for name in MONTHS)


def load(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def parse_dt(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def month_end(year, month):
    return datetime(year, month, calendar.monthrange(year, month)[1], tzinfo=timezone.utc)


def reference_date_from_title(title):
    """Infer the end of an explicitly named statistical reference period.

    This is *not* treated as the source publication date. It exists only so
    undated statistical listing pages can expose how old the underlying period is.
    """
    text = re.sub(r'\s+', ' ', title or '').strip()
    # August 21-31, 2026 / August 21–31 2026
    m = re.search(rf'\b({MONTH_RE})\s+(\d{{1,2}})\s*[-–]\s*(\d{{1,2}}),?\s+(20\d{{2}})\b', text, re.I)
    if m:
        return datetime(int(m.group(4)), MONTHS[m.group(1).lower()], int(m.group(3)), tzinfo=timezone.utc)
    # from January to July 2026
    m = re.search(rf'\bfrom\s+({MONTH_RE})\s+to\s+({MONTH_RE})\s+(20\d{{2}})\b', text, re.I)
    if m:
        return month_end(int(m.group(3)), MONTHS[m.group(2).lower()])
    # in July 2026 / July 2026
    matches = list(re.finditer(rf'\b({MONTH_RE})\s+(20\d{{2}})\b', text, re.I))
    if matches:
        m = matches[-1]
        return month_end(int(m.group(2)), MONTHS[m.group(1).lower()])
    return None


def item_reference_date(item):
    published = parse_dt(item.get('published_at'))
    if published:
        return published, 'published_at'
    inferred = reference_date_from_title(item.get('title', ''))
    if inferred:
        return inferred, 'title_reference_period'
    return None, None


def age_days(now, dt):
    if not dt:
        return None
    return round(max(0.0, (now - dt).total_seconds() / 86400), 1)


def source_freshness_state(status, age):
    if status != 'ok':
        return 'degraded'
    if age is None:
        return 'unknown'
    if age <= 3:
        return 'fresh'
    if age <= 14:
        return 'current'
    if age <= 45:
        return 'aging'
    return 'stale'


def main():
    ingest = load(RAW / 'ingest_log.json', {})
    items = load(RAW / 'items.json', [])
    candidates = load(RAW / 'candidates.json', [])
    screening = load(RAW / 'screening_summary.json', {})
    gate = load(RAW / 'publication_gate.json', {})
    signals = load(DATA / 'signals.json', [])
    configured = load(DATA / 'sources.json', [])

    now = parse_dt(ingest.get('collected_at')) or datetime.now(timezone.utc)
    health_by_source = {x.get('source'): x for x in ingest.get('health', []) if x.get('source')}
    items_by_source = {}
    for item in items:
        items_by_source.setdefault(item.get('source', 'Unknown'), []).append(item)

    sources = []
    for cfg in configured:
        if not cfg.get('enabled'):
            continue
        name = cfg.get('name')
        observed = health_by_source.get(name, {})
        source_items = items_by_source.get(name, [])
        refs = []
        published_dates = []
        detection_lags = []
        for item in source_items:
            ref_dt, ref_kind = item_reference_date(item)
            if ref_dt:
                refs.append((ref_dt, ref_kind))
            pub = parse_dt(item.get('published_at'))
            if pub:
                published_dates.append(pub)
                first = parse_dt(item.get('first_seen_at')) or parse_dt(item.get('collected_at'))
                if first:
                    detection_lags.append(max(0.0, (first - pub).total_seconds() / 86400))

        newest_ref_dt = max((x[0] for x in refs), default=None)
        newest_ref_kind = None
        if newest_ref_dt:
            newest_ref_kind = next((kind for dt, kind in refs if dt == newest_ref_dt), None)
        newest_published = max(published_dates, default=None)
        ref_age = age_days(now, newest_ref_dt)
        status = observed.get('status', 'unknown')
        sources.append({
            'source': name,
            'status': status,
            'freshness_state': source_freshness_state(status, ref_age),
            'method': observed.get('method'),
            'http_status': observed.get('http_status'),
            'items_fetched': observed.get('items', 0),
            'items_in_cache': len(source_items),
            'consecutive_failures': int(observed.get('consecutive_failures', 0) or 0),
            'last_success_at': observed.get('last_success_at'),
            'seconds': observed.get('seconds'),
            'newest_reference_date': newest_ref_dt.date().isoformat() if newest_ref_dt else None,
            'newest_reference_basis': newest_ref_kind,
            'newest_reference_age_days': ref_age,
            'newest_published_at': newest_published.date().isoformat() if newest_published else None,
            'median_observed_age_at_first_detection_days': round(median(detection_lags), 1) if detection_lags else None,
            'error': observed.get('error'),
        })

    status_counts = Counter(x['status'] for x in sources)
    freshness_counts = Counter(x['freshness_state'] for x in sources)
    synthesis_counts = Counter((x.get('synthesis_status') or 'unknown') for x in candidates)
    gate_counts = gate.get('counts') or {}
    public_signals = [s for s in signals if s.get('status') not in ('demo', 'suppressed')]
    signal_dates = [parse_dt(s.get('published_at')) for s in public_signals]
    signal_dates = [d for d in signal_dates if d]

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'observation_time': now.isoformat(),
        'collection_state': ingest.get('state'),
        'collection': {
            'sources_enabled': ingest.get('sources_enabled', len(sources)),
            'sources_succeeded': ingest.get('sources_succeeded', status_counts.get('ok', 0)),
            'items_fetched': ingest.get('items_fetched'),
            'items_discovered': ingest.get('items_discovered', ingest.get('items_new')),
            'items_cached': ingest.get('items_cached', len(items)),
        },
        'source_status_counts': dict(status_counts),
        'source_freshness_counts': dict(freshness_counts),
        'sources': sources,
        'screening': screening,
        'candidate_synthesis_counts': dict(synthesis_counts),
        'publication_gate_counts': gate_counts,
        'published_signal_count': len(public_signals),
        'latest_published_signal_date': max(signal_dates).date().isoformat() if signal_dates else None,
    }
    (RAW / 'prelaunch_health.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))

    degraded = [x for x in sources if x['status'] != 'ok']
    print(f"source_health={status_counts.get('ok', 0)}/{len(sources)} ok degraded={len(degraded)}")
    if degraded:
        print('degraded_sources=' + ', '.join(
            f"{x['source']}[streak={x['consecutive_failures']}]" for x in degraded
        ))
    print(
        'collection_freshness=' +
        f"fetched={report['collection']['items_fetched']} " +
        f"discovered_new={report['collection']['items_discovered']} " +
        f"cached={report['collection']['items_cached']}"
    )
    currentish = sorted(
        [x for x in sources if x.get('newest_reference_date')],
        key=lambda x: x.get('newest_reference_age_days') if x.get('newest_reference_age_days') is not None else 10**9,
    )
    if currentish:
        print('source_reference_freshness=' + '; '.join(
            f"{x['source']}:{x['newest_reference_date']}({x['newest_reference_age_days']}d,{x['newest_reference_basis']})"
            for x in currentish
        ))
    print('candidate_synthesis=' + json.dumps(dict(synthesis_counts), sort_keys=True))
    print('publication_gate=' + json.dumps(gate_counts, sort_keys=True))


if __name__ == '__main__':
    main()
