#!/usr/bin/env python3
"""Header-aware statistical table extraction for OBOR.

Milestone 1 purpose:
    HTML table -> normalized grid -> typed semantic observations

This module deliberately does *not* perform economic synthesis, scoring,
Canadian relevance analysis, or publishing. Its only job is to preserve the
meaning supplied by table headers and row labels.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from html.parser import HTMLParser
import json
import re
from typing import Iterable, Optional


EMPTY_MARKERS = {"", "-", "—", "–", "…", "...", "..", " ", " ", "na", "n/a"}


def clean(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\u2002", " ").replace("\u2003", " ")
    return re.sub(r"\s+", " ", value).strip()


def number(value: str) -> Optional[float]:
    value = clean(value).replace(",", "").replace("%", "")
    if value.lower() in EMPTY_MARKERS:
        return None
    # Remove annotations such as "-0.6 (percentage points)" while retaining sign.
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)", value)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


@dataclass(frozen=True)
class RawCell:
    text: str
    tag: str
    rowspan: int = 1
    colspan: int = 1


@dataclass
class RawTable:
    rows: list[list[RawCell]]


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[RawTable] = []
        self._depth = 0
        self._rows: list[list[RawCell]] = []
        self._row: Optional[list[RawCell]] = None
        self._cell: Optional[dict] = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attrs = dict(attrs)
        if tag == "table":
            if self._depth == 0:
                self._rows = []
            self._depth += 1
            return
        if self._depth != 1:
            return
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            def span(name: str) -> int:
                try:
                    return max(1, int(attrs.get(name, "1")))
                except (TypeError, ValueError):
                    return 1
            self._cell = {
                "tag": tag,
                "rowspan": span("rowspan"),
                "colspan": span("colspan"),
                "parts": [],
            }
        elif tag == "br" and self._cell is not None:
            self._cell["parts"].append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._depth == 1:
                if self._rows:
                    self.tables.append(RawTable(self._rows))
                self._rows = []
            self._depth = max(0, self._depth - 1)
            return
        if self._depth != 1:
            return
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(RawCell(
                text=clean(" ".join(self._cell["parts"])),
                tag=self._cell["tag"],
                rowspan=self._cell["rowspan"],
                colspan=self._cell["colspan"],
            ))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self._rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._depth == 1 and self._cell is not None:
            value = clean(data)
            if value:
                self._cell["parts"].append(value)


def parse_html_tables(html: str | bytes) -> list[RawTable]:
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    parser = _HTMLTableParser()
    parser.feed(html)
    parser.close()
    return parser.tables


@dataclass(frozen=True)
class GridCell:
    text: str
    tag: str
    origin_row: int
    origin_col: int


def expand_table(table: RawTable) -> list[list[Optional[GridCell]]]:
    """Expand rowspan/colspan cells into a rectangular logical grid."""
    grid: list[list[Optional[GridCell]]] = []
    occupied: dict[tuple[int, int], GridCell] = {}
    max_col = 0

    for r, raw_row in enumerate(table.rows):
        row: list[Optional[GridCell]] = []
        c = 0
        for raw in raw_row:
            while (r, c) in occupied:
                while len(row) <= c:
                    row.append(None)
                row[c] = occupied[(r, c)]
                c += 1
            cell = GridCell(raw.text, raw.tag, r, c)
            for rr in range(r, r + raw.rowspan):
                for cc in range(c, c + raw.colspan):
                    occupied[(rr, cc)] = cell
            while len(row) < c + raw.colspan:
                row.append(None)
            for cc in range(c, c + raw.colspan):
                row[cc] = cell
            c += raw.colspan
        # Fill any carried rowspans to the right of the explicit cells.
        while any(rr == r and cc >= c for (rr, cc) in occupied):
            if (r, c) in occupied:
                while len(row) <= c:
                    row.append(None)
                row[c] = occupied[(r, c)]
            c += 1
        max_col = max(max_col, len(row))
        grid.append(row)

    for r, row in enumerate(grid):
        if len(row) < max_col:
            row.extend([None] * (max_col - len(row)))
        for c in range(max_col):
            if row[c] is None and (r, c) in occupied:
                row[c] = occupied[(r, c)]
    return grid


HEADER_CUES = re.compile(
    r"\b(indicator|products?|units?|absolute value|growth rate|current price|price change|"
    r"rate\s*\(%\)|change rate|y/y|m/m|year[- ]on[- ]year|month[- ]on[- ]month|"
    r"january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.I,
)


def _unique_texts(cells: Iterable[Optional[GridCell]]) -> list[str]:
    out: list[str] = []
    for cell in cells:
        if not cell:
            continue
        text = clean(cell.text)
        if text and (not out or out[-1] != text):
            out.append(text)
    return out


def detect_header_rows(grid: list[list[Optional[GridCell]]]) -> int:
    """Return number of leading rows treated as headers.

    Uses explicit TH markup when present and lexical header cues otherwise.
    Stops at the first row with a numeric-looking data cell after at least one
    header row has been established.
    """
    count = 0
    for i, row in enumerate(grid[:6]):
        texts = _unique_texts(row)
        joined = " | ".join(texts)
        has_th = any(cell and cell.tag == "th" and cell.origin_row == i for cell in row)
        numeric_cells = sum(number(t) is not None for t in texts[1:])
        cue = bool(HEADER_CUES.search(joined))
        if has_th or cue or (i == 0 and numeric_cells == 0):
            count += 1
            continue
        break
    return max(1, count)


def header_paths(grid: list[list[Optional[GridCell]]], header_rows: int) -> list[list[str]]:
    if not grid:
        return []
    width = len(grid[0])
    paths: list[list[str]] = []
    for c in range(width):
        parts: list[str] = []
        last_origin = None
        for r in range(header_rows):
            cell = grid[r][c]
            if not cell:
                continue
            origin = (cell.origin_row, cell.origin_col)
            text = clean(cell.text)
            if not text or origin == last_origin:
                continue
            if not parts or parts[-1].lower() != text.lower():
                parts.append(text)
            last_origin = origin
        paths.append(parts)
    return paths


MONTHS = "January February March April May June July August September October November December".split()
PERIOD_RE = re.compile(
    r"\b(?:" + "|".join(MONTHS) + r")(?:\s*[-–]\s*(?:" + "|".join(MONTHS) + r"))?(?:\s+\d{4})?\b",
    re.I,
)


def period_from_path(path: list[str], default_period: Optional[str] = None) -> Optional[str]:
    for part in path:
        m = PERIOD_RE.search(part)
        if m:
            return clean(m.group(0).replace("–", "-"))
    return default_period


def metric_from_path(path: list[str]) -> Optional[str]:
    text = " | ".join(path).lower()
    if re.search(r"growth rate.*(?:y/y|year[- ]on[- ]year)|(?:y/y|year[- ]on[- ]year).*growth rate", text):
        return "growth_rate_yoy"
    if re.search(r"growth rate.*(?:m/m|month[- ]on[- ]month)|(?:m/m|month[- ]on[- ]month).*growth rate", text):
        return "growth_rate_mom"
    if "price change over previous period" in text or "price change" in text:
        return "price_change"
    if "±rate" in text or "+/-rate" in text or "change rate" in text:
        return "price_change_rate"
    if "current price" in text:
        return "price"
    if "absolute value" in text:
        return "absolute_value"
    if re.search(r"\brate\s*\(%\)", text):
        # A bare Rate (%) is not given price semantics without explicit price context.
        return "rate"
    return None


def unit_from_path(path: list[str], metric: str, row_unit: Optional[str]) -> Optional[str]:
    text = " | ".join(path)
    if metric in {"growth_rate_yoy", "growth_rate_mom", "price_change_rate", "rate"}:
        return "%"
    m = re.search(r"\(([^()]+)\)", text)
    header_unit = clean(m.group(1)) if m else None
    if metric in {"price", "price_change"}:
        currency = None
        if header_unit and re.search(r"yuan|rmb|cny", header_unit, re.I):
            currency = "yuan"
        if currency and row_unit:
            return f"{currency}/{row_unit}"
        return currency or row_unit
    return header_unit or row_unit


@dataclass(frozen=True)
class Observation:
    subject: str
    metric: str
    value: float
    unit: Optional[str]
    period: Optional[str]
    comparison: Optional[str]
    direction: Optional[str]
    source_table: int
    row_index: int
    column_index: int
    raw_value: str
    header_path: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _direction(metric: str, value: float) -> Optional[str]:
    if metric not in {"growth_rate_yoy", "growth_rate_mom", "price_change", "price_change_rate", "rate"}:
        return None
    if value > 0:
        return "increase"
    if value < 0:
        return "decrease"
    return "unchanged"


def _comparison(metric: str) -> Optional[str]:
    return {
        "growth_rate_yoy": "year_on_year",
        "growth_rate_mom": "month_on_month",
        "price_change": "previous_period",
        "price_change_rate": "previous_period",
    }.get(metric)


def _row_unit(subject: str, row: list[Optional[GridCell]], paths: list[list[str]]) -> Optional[str]:
    for c, path in enumerate(paths):
        if any(re.search(r"\bunits?\b", p, re.I) for p in path):
            cell = row[c] if c < len(row) else None
            if cell and clean(cell.text).lower() not in EMPTY_MARKERS:
                return clean(cell.text)
    # Industrial output embeds units in row labels, e.g. "Cement (10,000 tons)".
    m = re.search(r"\(([^()]+)\)\s*$", subject)
    return clean(m.group(1)) if m else None


def _subject_column(paths: list[list[str]]) -> int:
    for i, path in enumerate(paths):
        text = " | ".join(path).lower()
        if "indicator" in text or re.search(r"\bproducts?\b", text):
            return i
    return 0


def extract_observations(html: str | bytes, default_period: Optional[str] = None) -> list[Observation]:
    observations: list[Observation] = []
    tables = parse_html_tables(html)
    for table_i, table in enumerate(tables):
        grid = expand_table(table)
        if not grid:
            continue
        h = detect_header_rows(grid)
        paths = header_paths(grid, h)
        subject_col = _subject_column(paths)
        for r in range(h, len(grid)):
            row = grid[r]
            if subject_col >= len(row) or not row[subject_col]:
                continue
            subject = clean(row[subject_col].text)
            if not subject or subject.lower() in EMPTY_MARKERS:
                continue
            row_unit = _row_unit(subject, row, paths)
            emitted = 0
            for c, path in enumerate(paths):
                metric = metric_from_path(path)
                if not metric or c == subject_col or c >= len(row) or not row[c]:
                    continue
                raw = clean(row[c].text)
                value = number(raw)
                if value is None:
                    continue
                obs = Observation(
                    subject=subject,
                    metric=metric,
                    value=value,
                    unit=unit_from_path(path, metric, row_unit),
                    period=period_from_path(path, default_period),
                    comparison=_comparison(metric),
                    direction=_direction(metric, value),
                    source_table=table_i,
                    row_index=r,
                    column_index=c,
                    raw_value=raw,
                    header_path=tuple(path),
                )
                observations.append(obs)
                emitted += 1
            # Rows such as "By Sector" contain no numeric facts and simply emit nothing.
    return observations


def validate_observations(observations: list[Observation]) -> list[str]:
    """Return semantic-integrity errors; empty list means validation passed."""
    errors: list[str] = []
    by_key: dict[tuple[str, Optional[str]], dict[str, Observation]] = {}
    for obs in observations:
        if obs.metric in {"growth_rate_yoy", "growth_rate_mom", "price_change_rate", "rate"} and obs.unit != "%":
            errors.append(f"{obs.subject}: percentage metric {obs.metric} has unit {obs.unit!r}")
        if obs.metric in {"price", "price_change"} and obs.unit == "%":
            errors.append(f"{obs.subject}: price metric incorrectly has percentage unit")
        by_key.setdefault((obs.subject, obs.period), {})[obs.metric] = obs

    for (subject, period), metrics in by_key.items():
        change = metrics.get("price_change")
        rate = metrics.get("price_change_rate")
        if change and rate and change.value != 0 and rate.value != 0:
            if (change.value > 0) != (rate.value > 0):
                errors.append(
                    f"{subject} {period or ''}: price-change sign {change.value:g} conflicts with rate {rate.value:g}"
                )
    return errors


def observations_to_json(observations: list[Observation]) -> str:
    return json.dumps([o.to_dict() for o in observations], ensure_ascii=False, indent=2)
