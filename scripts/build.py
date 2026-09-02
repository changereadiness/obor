#!/usr/bin/env python3
"""Minimal deterministic static generator for OBOR signal pages."""
import json, html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
nav='''<header class="site-header"><div class="wrap nav"><a class="brand" href="/">OBOR</a><span class="descriptor">China Economic Intelligence for Canadian Business</span><nav><a href="/signals/">Signals</a><a href="/opportunities/">Opportunities</a><a href="/risks/">Risks</a><a href="/sectors/">Sectors</a><a href="/about/">About</a></nav></div></header>'''
data=json.loads((ROOT/'data/signals.json').read_text())
for s in data:
    if s.get('status')=='suppressed': continue
    out=ROOT/'signals'/s['slug']/'index.html'; out.parent.mkdir(parents=True,exist_ok=True)
    cats=' · '.join(s['categories']); sectors=' · '.join(s['sectors'])
    key_data = s.get('key_data', [])
    data_html = ''.join(f"<li><strong>{html.escape(str(d.get('value','')))} {html.escape(str(d.get('unit','')))}</strong><span>{html.escape(str(d.get('context','')))}</span></li>" for d in key_data[:8])
    title=html.escape(s['title']); summary=html.escape(s['summary'])
    wh=s.get('what_happened',[])
    if isinstance(wh,list): what_html='<ul>'+''.join(f'<li>{html.escape(str(x))}</li>' for x in wh[:6])+'</ul>'
    else: what_html=f'<p>{html.escape(str(wh))}</p>'
    body=f'''<!doctype html><html lang="en-CA"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} — OBOR</title><meta name="description" content="{summary}"><link rel="canonical" href="https://obor.ca/signals/{s['slug']}/"><link rel="stylesheet" href="/assets/style.css"></head><body>{nav}<main class="wrap" style="max-width:900px;padding:70px 0"><p class="eyebrow">{s['opportunity_or_risk']} · {s['published_at']}</p><h1 style="font-family:Georgia,serif;font-size:clamp(40px,6vw,64px);font-weight:500;line-height:1.05">{title}</h1><div style="display:flex;gap:20px;flex-wrap:wrap;margin:26px 0;color:var(--muted);font-size:13px"><span><strong>OBOR relevance</strong> {s['relevance_score']}/100</span><span><strong>Confidence</strong> {s['confidence_score']}/100</span><span>{html.escape(cats)}</span></div><div class="brief" style="margin-top:35px"><div><p class="eyebrow">SUMMARY</p><p>{summary}</p></div><div><p class="eyebrow">CANADIAN RELEVANCE</p><p>{html.escape(s['canadian_relevance'])}</p></div></div><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">WHAT HAPPENED</p>{what_html}</section><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">KEY DATA</p><ul class="key-data">{data_html or '<li>No structured economic data extracted.</li>'}</ul></section><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">WHAT THE DATA SHOWS</p><p>{html.escape(s.get('interpretation',''))}</p></section><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">SECTORS</p><p>{html.escape(sectors)}</p></section><section style="padding:45px 0;border-bottom:1px solid var(--line)"><p class="eyebrow">SOURCE</p><p>{html.escape(s['source'])} · <a href="{html.escape(s['source_url'])}">View source →</a></p></section><p style="color:var(--muted);font-size:12px;margin-top:28px">OBOR analysis based on the cited source. Classification and relevance are editorial assessments, not objective measures.</p></main></body></html>'''
    out.write_text(body)
