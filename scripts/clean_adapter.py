#!/usr/bin/env python3
"""Adapter between the V17 candidate pipeline and the clean intelligence engine."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from obor_intelligence.source_analysis import analyze_source
from obor_intelligence.records import category_for
from source_fetch import fetch_source

ENGINE_VERSION = "clean-m6"


def synthesize_item(item: dict) -> dict:
    result = dict(item)
    url = item.get("url") or item.get("source_url")
    try:
        body, content_type, status = fetch_source(url)
        analysis = analyze_source(item.get("title", ""), body)
        result["clean_analysis"] = analysis.to_dict()
        result["source_content"] = {
            "status": "fetched",
            "http_status": status,
            "content_type": content_type,
            "extraction_mode": analysis.extraction_mode,
            "analysis_status": analysis.status,
            "errors": analysis.errors,
            "observations": [o.to_dict() for o in analysis.observations],
            "dataset_observations": [d.to_dict() for d in analysis.dataset_observations],
        }
        if analysis.status != "ready" or not analysis.draft:
            result["synthesis_status"] = "insufficient_evidence"
            return result
        draft = analysis.draft.to_dict()
        result["clean_draft"] = draft
        result["sectors"] = list(draft["sectors"])
        result["categories"] = [category_for(draft["profile"])]
        result["synthesis_status"] = "evidence_available"
        return result
    except Exception as exc:
        result["source_content"] = {"status": "error", "error": str(exc)}
        result["clean_analysis"] = {"status": "source_unavailable", "errors": [str(exc)]}
        result["synthesis_status"] = "source_unavailable"
        return result


def draft_fields(item: dict):
    draft = item.get("clean_draft")
    if not draft:
        raise ValueError("clean draft unavailable")
    return {
        "title": draft["headline"],
        "summary": draft["summary"],
        "canadian_relevance": draft["canadian_relevance"],
        "what_happened": list(draft["what_happened"]),
        "key_data": list(draft["key_data"]),
        "interpretation": draft["interpretation"],
        "sectors": list(draft["sectors"]),
        "categories": list(item.get("categories") or [category_for(draft["profile"])]),
        "profile": draft["profile"],
    }
