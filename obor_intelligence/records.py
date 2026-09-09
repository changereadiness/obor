#!/usr/bin/env python3
"""Stable signal-record contract for the clean reconstruction sandbox."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from urllib.parse import urlparse

from .source_analysis import AnalysisResult

SCHEMA_VERSION = "clean-1"


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:100] or "signal"


def category_for(profile: str) -> str:
    return {
        "market_prices": "Markets",
        "retail_sales": "Macroeconomics",
        "industrial_output": "Industry",
    }.get(profile, "Macroeconomics")


def make_signal_record(
    analysis: AnalysisResult,
    source_url: str,
    source_name: str,
    published_at: str,
) -> dict:
    if analysis.status != "ready" or not analysis.draft:
        raise ValueError("analysis is not ready for signal-record creation")
    draft = analysis.draft
    sid = "sig-" + hashlib.sha1(source_url.encode()).hexdigest()[:12]
    return {
        "schema_version": SCHEMA_VERSION,
        "id": sid,
        "title": draft.headline,
        "slug": slugify(analysis.title),
        "published_at": published_at[:10],
        "source": source_name,
        "source_url": source_url,
        "source_type": "Primary source",
        "summary": draft.summary,
        "canadian_relevance": draft.canadian_relevance,
        "what_happened": draft.what_happened,
        "key_data": draft.key_data,
        "interpretation": draft.interpretation,
        "sectors": draft.sectors,
        "categories": [category_for(draft.profile)],
        "opportunity_or_risk": "WATCH",
        "status": "candidate",
        "analysis": analysis.to_dict(),
    }


def validate_signal_record(signal: dict) -> list[str]:
    errors = []
    required = [
        "schema_version", "id", "title", "slug", "published_at", "source", "source_url",
        "summary", "canadian_relevance", "what_happened", "key_data", "interpretation",
        "sectors", "categories", "status", "analysis",
    ]
    for key in required:
        if signal.get(key) in (None, "", [], {}):
            errors.append(f"missing {key}")
    if signal.get("schema_version") != SCHEMA_VERSION:
        errors.append("unexpected schema version")
    u = urlparse(signal.get("source_url", ""))
    if u.scheme not in {"http", "https"} or not u.netloc:
        errors.append("invalid source URL")
    if not isinstance(signal.get("what_happened"), list):
        errors.append("what_happened must be a list")
    if not isinstance(signal.get("key_data"), list):
        errors.append("key_data must be a list")
    if signal.get("analysis", {}).get("status") != "ready":
        errors.append("embedded analysis is not ready")
    return errors
