#!/usr/bin/env python3
"""Offline end-to-end source analysis contract for OBOR clean reconstruction."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from html.parser import HTMLParser
import re
from typing import Optional

from .semantic_tables import extract_observations, validate_observations, Observation
from .evidence import extract_dataset_observations, DatasetObservation
from .editorial import build_draft, validate_draft, SignalDraft


class VisibleTextParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside"}
    BLOCK = {"p", "div", "article", "section", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP:
            self.skip += 1

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK and not self.skip:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            value = re.sub(r"\s+", " ", data).strip()
            if value:
                self.parts.append(value)


def visible_text(html: str | bytes) -> str:
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    parser = VisibleTextParser()
    parser.feed(html)
    parser.close()
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def reporting_period(title: str) -> Optional[str]:
    # Market-price releases use date ranges in the title; statistical tables
    # with period columns override this fallback at observation level.
    month = r"January|February|March|April|May|June|July|August|September|October|November|December"
    m = re.search(rf"\b({month})\s+(\d{{1,2}})\s*[-–]\s*(\d{{1,2}}),?\s+(\d{{4}})\b", title, re.I)
    if m:
        return f"{m.group(1).title()} {m.group(2)}-{m.group(3)} {m.group(4)}"
    m = re.search(rf"\b({month})\s+(\d{{4}})\b", title, re.I)
    if m:
        return f"{m.group(1).title()} {m.group(2)}"
    return None


@dataclass
class AnalysisResult:
    status: str
    title: str
    extraction_mode: str
    observations: list[Observation]
    dataset_observations: list[DatasetObservation]
    draft: Optional[SignalDraft]
    errors: list[str]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "title": self.title,
            "extraction_mode": self.extraction_mode,
            "observations": [o.to_dict() for o in self.observations],
            "dataset_observations": [d.to_dict() for d in self.dataset_observations],
            "draft": self.draft.to_dict() if self.draft else None,
            "errors": list(self.errors),
        }


def analyze_source(title: str, html: str | bytes) -> AnalysisResult:
    fallback_period = reporting_period(title)
    observations = extract_observations(html, default_period=fallback_period)
    datasets = extract_dataset_observations(visible_text(html), fallback_period)
    errors = validate_observations(observations)
    if not observations:
        errors.append("no structured observations extracted")
        return AnalysisResult("insufficient_structured_evidence", title, "none", observations, datasets, None, errors)

    draft = build_draft(title, observations, datasets)
    errors.extend(validate_draft(draft, observations, datasets))
    status = "ready" if not errors else "invalid"
    return AnalysisResult(status, title, "structured_table", observations, datasets, draft, errors)
