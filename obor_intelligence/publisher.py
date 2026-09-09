#!/usr/bin/env python3
"""Small safe HTML renderer for clean-reconstruction candidate signals."""
from __future__ import annotations

import html


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def render_signal(signal: dict) -> str:
    what_html = "".join(f"<li>{esc(item)}</li>" for item in signal.get("what_happened", []))
    key_parts = []
    for card in signal.get("key_data", []):
        meta = []
        if card.get("metric") == "dataset_distribution" and card.get("context"):
            meta.append(str(card["context"]))
        if card.get("period"):
            meta.append(str(card["period"]).replace("-", "–"))
        key_parts.append(
            "<li class=\"key-data-card\">"
            f"<strong>{esc(card.get('value', ''))}</strong>"
            f"<span>{esc(card.get('label', ''))}</span>"
            f"<small>{esc(' · '.join(meta))}</small>"
            "</li>"
        )
    key_html = "".join(key_parts)
    sectors = " · ".join(signal.get("sectors", []))
    categories = " · ".join(signal.get("categories", []))
    return f'''<!doctype html>
<html lang="en-CA">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(signal['title'])} — OBOR</title>
<meta name="description" content="{esc(signal['summary'])}">
</head>
<body>
<main>
<p class="eyebrow">{esc(signal['opportunity_or_risk'])} · {esc(signal['published_at'])}</p>
<h1>{esc(signal['title'])}</h1>
<p>{esc(categories)}</p>
<section><p class="eyebrow">SUMMARY</p><p>{esc(signal['summary'])}</p></section>
<section><p class="eyebrow">CANADIAN RELEVANCE</p><p>{esc(signal['canadian_relevance'])}</p></section>
<section><p class="eyebrow">WHAT HAPPENED</p><ul>{what_html}</ul></section>
<section><p class="eyebrow">KEY DATA</p><ul class="key-data">{key_html}</ul></section>
<section><p class="eyebrow">WHAT THE DATA SHOWS</p><p>{esc(signal['interpretation'])}</p></section>
<section><p class="eyebrow">SECTORS</p><p>{esc(sectors)}</p></section>
<section><p class="eyebrow">SOURCE</p><p>{esc(signal['source'])} · <a href="{esc(signal['source_url'])}">View source →</a></p></section>
</main>
</body>
</html>'''
