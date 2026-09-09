#!/usr/bin/env python3
"""Deterministic static generator for OBOR signal pages.

M6 contract: rendering consumes the persisted signal schema only. It never
re-interprets source data or performs synthesis.
"""
from __future__ import annotations
import html, json, os
from pathlib import Path

ROOT = Path(os.environ.get('OBOR_ROOT', Path(__file__).resolve().parents[1])).resolve()
NAV = '''<header class="site-header"><div class="wrap nav"><a class="brand" href="/">OBOR</a><span class="descriptor">China Economic Intelligence for Canadian Business</span><nav><a href="/signals/">Signals</a><a href="/opportunities/">Opportunities</a><a href="/risks/">Risks</a><a href="/sectors/">Sectors</a><a href="/about/">About</a></nav></div></header>'''


def esc(v):
    return html.escape(str(v if v is not None else ''), quote=True)


def what_happened_html(value):
    items = value if isinstance(value, list) else ([value] if value else [])
    return ''.join(f'<li>{esc(x)}</li>' for x in items)


def key_data_html(cards):
    out=[]
    for d in (cards or [])[:8]:
        if not isinstance(d, dict):
            continue
        value = d.get('value', '')
        label = d.get('label') or d.get('context') or ''
        period = d.get('period') or ''
        unit = d.get('unit') or ''
        context = d.get('context') or ''
        metric = d.get('metric') or ''
        shown = f'{value} {unit}'.strip()
        meta = []
        # Dataset-distribution cards carry a useful percentage in context.
        # Observation context generally duplicates the subject already present
        # in the explicit label, so it is intentionally not rendered twice.
        if metric == 'dataset_distribution' and context:
            meta.append(context)
        if period:
            meta.append(period.replace('-', '–'))
        out.append('<li class="key-data-card">'
                   f'<strong>{esc(shown)}</strong>'
                   f'<span>{esc(label)}</span>'
                   f'<small>{esc(" · ".join(meta))}</small>'
                   '</li>')
    return ''.join(out)


def render_signal(s):
    cats=' · '.join(s.get('categories', []))
    sectors=' · '.join(s.get('sectors', []))
    title=esc(s.get('title',''))
    summary=esc(s.get('summary',''))
    what_html=what_happened_html(s.get('what_happened'))
    data_html=key_data_html(s.get('key_data'))
    slug=esc(s.get('slug',''))
    return f'''<!doctype html><html lang="en-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} — OBOR</title><meta name="description" content="{summary}"><link rel="canonical" href="https://obor.ca/signals/{slug}/"><link rel="stylesheet" href="/assets/style.css"></head><body>{NAV}<main class="wrap" style="max-width:900px;padding:70px 0"><p class="eyebrow">{esc(s.get('opportunity_or_risk','WATCH'))} · {esc(s.get('published_at',''))}</p><h1 style="font-family:Georgia,serif;font-size:clamp(40px,6vw,64px);font-weight:500;line-height:1.05">{title}</h1><div style="display:flex;gap:20px;flex-wrap:wrap;margin:26px 0;color:var(--muted);font-size:13px"><span><strong>OBOR relevance</strong> {esc(s.get('relevance_score',''))}/100</span><span><strong>Confidence</strong> {esc(s.get('confidence_score',''))}/100</span><span>{esc(cats)}</span></div><div class="brief" style="margin-top:35px"><div><p class="eyebrow">SUMMARY</p><p>{summary}</p></div><div><p class="eyebrow">CANADIAN RELEVANCE</p><p>{esc(s.get('canadian_relevance',''))}</p></div></div><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">WHAT HAPPENED</p><ul>{what_html}</ul></section><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">KEY DATA</p><ul class="key-data">{data_html or '<li>No structured economic data extracted.</li>'}</ul></section><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">WHAT THE DATA SHOWS</p><p>{esc(s.get('interpretation',''))}</p></section><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">SECTORS</p><p>{esc(sectors)}</p></section><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">SOURCE</p><p>{esc(s.get('source',''))} · <a href="{esc(s.get('source_url',''))}">View source →</a></p></section><p style="color:var(--muted);font-size:12px;margin-top:28px">OBOR analysis based on the cited source. Classification and relevance are editorial assessments, not objective measures.</p></main></body></html>'''


def main():
    path=ROOT/'data/signals.json'
    data=json.loads(path.read_text()) if path.exists() else []
    for s in data:
        if s.get('status')=='suppressed':
            continue
        out=ROOT/'signals'/s['slug']/'index.html'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_signal(s))

if __name__=='__main__':
    main()
