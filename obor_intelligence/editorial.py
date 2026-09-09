#!/usr/bin/env python3
"""Evidence-locked deterministic editorial synthesis for OBOR.

Milestone 3. This module receives typed observations and validated dataset
observations. It never parses raw HTML or flattened source text.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Optional

from .semantic_tables import Observation
from .evidence import DatasetObservation, EvidencePoint, select_key_evidence


@dataclass(frozen=True)
class SignalProfile:
    kind: str
    measured_variable: str
    primary_subject: Optional[str]
    sectors: tuple[str, ...]


@dataclass
class SignalDraft:
    headline: str
    summary: str
    canadian_relevance: str
    what_happened: list[str]
    key_data: list[dict]
    interpretation: str
    sectors: list[str]
    profile: str

    def to_dict(self) -> dict:
        return asdict(self)


def _find_subject(observations: list[Observation], pattern: str) -> Optional[str]:
    rx = re.compile(pattern, re.I)
    for obs in observations:
        if rx.search(obs.subject):
            return obs.subject
    return None


def infer_profile(title: str, observations: list[Observation]) -> SignalProfile:
    low = title.lower()
    metrics = {o.metric for o in observations}

    if {"price", "price_change_rate"}.issubset(metrics):
        return SignalProfile(
            kind="market_prices",
            measured_variable="market prices of production inputs",
            primary_subject=None,
            sectors=("Manufacturing", "Energy", "Mining & Critical Minerals", "Construction & Infrastructure"),
        )

    retail_subject = _find_subject(observations, r"total retail sales")
    if retail_subject or "retail sales" in low:
        return SignalProfile(
            kind="retail_sales",
            measured_variable="retail sales",
            primary_subject=retail_subject,
            sectors=("Consumer Goods", "Automotive", "Technology"),
        )

    industrial_subject = _find_subject(observations, r"value added of industrial enterprises")
    if industrial_subject or "industrial production" in low or "industrial output" in low:
        return SignalProfile(
            kind="industrial_output",
            measured_variable="industrial output",
            primary_subject=industrial_subject,
            sectors=("Manufacturing", "Technology", "Machinery & Equipment", "Energy", "Mining & Critical Minerals"),
        )

    return SignalProfile(
        kind="generic_statistical",
        measured_variable="reported economic indicator",
        primary_subject=observations[0].subject if observations else None,
        sectors=("Other",),
    )


def _obs(
    observations: list[Observation],
    subject_pattern: str,
    metric: str,
    period_pattern: Optional[str] = None,
) -> Optional[Observation]:
    sr = re.compile(subject_pattern, re.I)
    pr = re.compile(period_pattern, re.I) if period_pattern else None
    for o in observations:
        if o.metric != metric or not sr.search(o.subject):
            continue
        if pr and not pr.search(o.period or ""):
            continue
        return o
    return None


def _pct(o: Optional[Observation]) -> Optional[str]:
    if not o:
        return None
    sign = "+" if o.value > 0 else ""
    return f"{sign}{o.value:g}%"


def _movement_word(value: float) -> str:
    if value > 0:
        return "increased"
    if value < 0:
        return "decreased"
    return "was unchanged"


def _period_phrase(period: Optional[str]) -> str:
    if not period:
        return "the reported period"
    return period.replace("-", "–")


def _key_cards(points: list[EvidencePoint]) -> list[dict]:
    cards = []
    for p in points:
        cards.append({
            "value": p.value,
            "label": p.context if p.kind == "observation" else p.label,
            "period": p.period,
            "metric": p.metric or p.kind,
            "context": p.context,
        })
    return cards


def _observation_cards(items: list[tuple[Optional[Observation], str]]) -> list[dict]:
    cards = []
    for obs, label in items:
        if not obs:
            continue
        sign = "+" if obs.value > 0 and obs.unit == "%" else ""
        value = f"{sign}{obs.value:g}%" if obs.unit == "%" else f"{obs.value:g}{(' ' + obs.unit) if obs.unit else ''}"
        cards.append({
            "value": value,
            "label": label,
            "period": obs.period,
            "metric": obs.metric,
            "context": obs.subject,
        })
    return cards


def _market_price_draft(
    observations: list[Observation], datasets: list[DatasetObservation], profile: SignalProfile
) -> SignalDraft:
    ds = datasets[0] if datasets else None
    period = ds.period if ds else (observations[0].period if observations else None)
    rate_obs = [o for o in observations if o.metric == "price_change_rate"]
    declines = sorted((o for o in rate_obs if o.value < 0), key=lambda o: o.value)
    rises = sorted((o for o in rate_obs if o.value > 0), key=lambda o: o.value, reverse=True)

    if ds:
        if ds.decreased > ds.increased:
            direction = "mostly declined"
        elif ds.increased > ds.decreased:
            direction = "mostly increased"
        else:
            direction = "were mixed"
        headline = f"China production-input prices {direction} in {_period_phrase(period)}"
        summary = (
            f"Price movement was broad but not uniform across the monitored basket: "
            f"{ds.decreased} of {ds.population} products fell, {ds.increased} rose and {ds.unchanged} were unchanged. "
            "The distribution is a useful watchpoint for industrial input-cost conditions in China, not a direct measure of export or Canadian landed prices."
        )
        canadian = (
            "Canadian manufacturers and importers sourcing industrial materials or energy-linked inputs from China should watch whether supplier pricing follows the broader movement. "
            "The release itself does not establish any change in Canadian import prices or landed costs."
        )
        bullets = [
            f"{ds.decreased} of {ds.population} monitored products decreased in price.",
            f"{ds.increased} of {ds.population} increased in price.",
            f"{ds.unchanged} of {ds.population} were unchanged.",
        ]
    else:
        headline = f"China production-input prices show mixed movement in {_period_phrase(period)}"
        summary = "The monitored production-input prices moved in different directions across products, making the distribution more useful than any single commodity move."
        canadian = "Canadian businesses sourcing industrial inputs from China should treat the release as a supplier-cost watchpoint rather than evidence of Canadian landed-price changes."
        bullets = []

    for o in declines[:2]:
        bullets.append(f"{o.subject} decreased {abs(o.value):g}% from the previous period.")
    for o in rises[:1]:
        bullets.append(f"{o.subject} increased {o.value:g}% from the previous period.")
    bullets = bullets[:6]

    if ds:
        interpretation = (
            f"The balance of movements points to a {'downward' if ds.decreased > ds.increased else 'upward' if ds.increased > ds.decreased else 'mixed'} bias across the monitored basket, "
            "but dispersion between products means the signal should not be treated as a uniform change in Chinese industrial costs."
        )
    else:
        interpretation = "The extracted product movements are dispersed, so the table supports product-level monitoring more strongly than a single broad price-direction claim."

    points = select_key_evidence(observations, datasets, limit=5)
    return SignalDraft(headline, summary, canadian, bullets, _key_cards(points), interpretation, list(profile.sectors), profile.kind)


def _retail_draft(observations: list[Observation], profile: SignalProfile) -> SignalDraft:
    total_july = _obs(observations, r"^Total retail sales", "growth_rate_yoy", r"^July$")
    total_ytd = _obs(observations, r"^Total retail sales", "growth_rate_yoy", r"January.*July")
    ex_auto_july = _obs(observations, r"excluding automobiles", "growth_rate_yoy", r"^July$")
    online_ytd = _obs(observations, r"online retail sales of goods", "growth_rate_yoy", r"January.*July")

    if total_july:
        headline = f"China retail sales grew {total_july.value:g}% year over year in July"
    else:
        headline = "China retail sales provide a new read on consumer activity"

    comparisons = []
    if ex_auto_july:
        comparisons.append(f"sales excluding automobiles grew {_pct(ex_auto_july)} in July")
    if online_ytd:
        comparisons.append(f"online retail sales of goods grew {_pct(online_ytd)} over January–July")
    detail = "; ".join(comparisons)
    summary = (
        f"Overall retail growth remained modest{f', while {detail}' if detail else ''}. "
        "The divergence across categories is more useful for assessing consumer conditions than the aggregate rate alone."
    )
    canadian = (
        "Canadian exporters and consumer-facing businesses should watch which Chinese retail categories are expanding or contracting rather than treating the aggregate figure as a uniform demand signal. "
        "The release does not identify demand specifically for Canadian goods."
    )

    bullets = []
    for o, label, period_text in [
        (total_july, "Total retail sales", "in July"),
        (total_ytd, "Total retail sales", "over January–July"),
        (ex_auto_july, "Retail sales excluding automobiles", "in July"),
        (online_ytd, "Online retail sales of goods", "over January–July"),
    ]:
        if o:
            bullets.append(f"{label} {_movement_word(o.value)} {abs(o.value):g}% year over year {period_text}.")

    interpretation_bits = []
    if total_july and ex_auto_july and ex_auto_july.value > total_july.value:
        interpretation_bits.append("Growth excluding automobiles was stronger than the overall retail rate")
    if online_ytd and total_ytd and online_ytd.value > total_ytd.value:
        interpretation_bits.append("online goods sales outpaced aggregate retail growth over January–July")
    interpretation = (
        "; ".join(interpretation_bits) + ". This suggests uneven consumer momentum across categories rather than a uniform retail trend."
        if interpretation_bits else
        "The observations support a category-by-category reading of Chinese consumer activity rather than a uniform demand conclusion."
    )

    cards = _observation_cards([
        (total_july, "Total retail sales"),
        (total_ytd, "Total retail sales"),
        (ex_auto_july, "Retail sales excluding automobiles"),
        (online_ytd, "Online retail sales of goods"),
    ])
    return SignalDraft(headline, summary, canadian, bullets[:6], cards[:5], interpretation, list(profile.sectors), profile.kind)


def _industrial_draft(observations: list[Observation], profile: SignalProfile) -> SignalDraft:
    total_july = _obs(observations, r"value added of industrial enterprises", "growth_rate_yoy", r"^July$")
    total_ytd = _obs(observations, r"value added of industrial enterprises", "growth_rate_yoy", r"January.*July")
    manufacturing = _obs(observations, r"^Manufacturing$", "growth_rate_yoy", r"^July$")
    hightech = _obs(observations, r"high-technology manufacturing", "growth_rate_yoy", r"^July$")
    mining = _obs(observations, r"^Mining$", "growth_rate_yoy", r"^July$")

    headline = (
        f"China industrial output grew {total_july.value:g}% year over year in July"
        if total_july else "China industrial output shows uneven sector growth"
    )
    summary_parts = []
    if manufacturing:
        summary_parts.append(f"manufacturing at {_pct(manufacturing)}")
    if hightech:
        summary_parts.append(f"high-tech manufacturing at {_pct(hightech)}")
    if mining:
        summary_parts.append(f"mining at {_pct(mining)}")
    summary = (
        "China's industrial sector continued to expand, with " + ", ".join(summary_parts) + ". "
        "The sector divergence is more informative for supply, competition and input demand than the headline industrial rate alone."
        if summary_parts else
        "The release provides a direct measure of industrial output growth, with sector-level differences determining where momentum is concentrated."
    )
    canadian = (
        "Canadian exporters, suppliers and competitors should watch where Chinese industrial output is accelerating or contracting, particularly in manufacturing and technology-intensive segments. "
        "Production growth can affect input demand and competitive supply, but it is not itself a measure of Chinese demand for Canadian products."
    )

    bullets = []
    for o, label, period_text in [
        (total_july, "Industrial value added", "in July"),
        (total_ytd, "Industrial value added", "over January–July"),
        (manufacturing, "Manufacturing", "in July"),
        (hightech, "High-tech manufacturing", "in July"),
        (mining, "Mining", "in July"),
    ]:
        if o:
            bullets.append(f"{label} {_movement_word(o.value)} {abs(o.value):g}% year over year {period_text}.")

    interpretation_bits = []
    if hightech and total_july and hightech.value > total_july.value:
        interpretation_bits.append("High-tech manufacturing substantially outpaced overall industrial growth")
    if mining and mining.value < 0:
        interpretation_bits.append("mining contracted while the broader industrial sector expanded")
    interpretation = (
        "; ".join(interpretation_bits) + ". The release therefore points to uneven industrial momentum rather than a uniform expansion."
        if interpretation_bits else
        "The data should be read as a production signal with sector dispersion, not as a direct measure of factory demand."
    )

    cards = _observation_cards([
        (total_july, "Industrial value added"),
        (total_ytd, "Industrial value added"),
        (manufacturing, "Manufacturing"),
        (hightech, "High-tech manufacturing"),
        (mining, "Mining"),
    ])
    return SignalDraft(headline, summary, canadian, bullets[:6], cards[:5], interpretation, list(profile.sectors), profile.kind)


def build_draft(
    title: str,
    observations: list[Observation],
    dataset_observations: Optional[list[DatasetObservation]] = None,
) -> SignalDraft:
    datasets = dataset_observations or []
    profile = infer_profile(title, observations)
    if profile.kind == "market_prices":
        return _market_price_draft(observations, datasets, profile)
    if profile.kind == "retail_sales":
        return _retail_draft(observations, profile)
    if profile.kind == "industrial_output":
        return _industrial_draft(observations, profile)

    points = select_key_evidence(observations, datasets, primary_subject=profile.primary_subject, limit=5)
    bullets = [f"{p.context}: {p.value}." for p in points if p.kind == "observation"][:6]
    return SignalDraft(
        headline=title.strip().rstrip("."),
        summary="The release contains a measurable economic development, but the current deterministic profile does not yet support a more specific significance statement.",
        canadian_relevance="Canadian relevance should remain unasserted until the measured variable and affected sectors are classified with sufficient confidence.",
        what_happened=bullets,
        key_data=_key_cards(points),
        interpretation="No stronger deterministic interpretation is produced for this statistical profile.",
        sectors=list(profile.sectors),
        profile=profile.kind,
    )


def validate_draft(draft: SignalDraft, observations: list[Observation], datasets: Optional[list[DatasetObservation]] = None) -> list[str]:
    errors = []
    if not draft.headline or len(draft.headline) < 12:
        errors.append("headline is missing or too short")
    if not (1 <= len(draft.what_happened) <= 6):
        errors.append("what_happened must contain 1-6 factual bullets")
    if not (1 <= len(draft.key_data) <= 5):
        errors.append("key_data must contain 1-5 cards")
    if len(draft.summary) > 650:
        errors.append("summary is too long")
    if len(draft.canadian_relevance) > 650:
        errors.append("Canadian relevance is too long")

    if draft.profile == "industrial_output" and re.search(r"factory demand", draft.headline, re.I):
        errors.append("industrial-output headline substitutes inferred demand for measured output")
    if draft.profile == "retail_sales" and re.search(r"price movement|production-input", draft.headline, re.I):
        errors.append("retail headline uses price-table semantics")

    # Key-data claims are traceable: every observation card carries metric and
    # context generated directly from an Observation or DatasetObservation.
    for card in draft.key_data:
        if card.get("metric") == "absolute_value" and str(card.get("value", "")).endswith("%"):
            errors.append(f"absolute value rendered as percentage: {card}")
        if card.get("metric") in {"growth_rate_yoy", "growth_rate_mom", "price_change_rate"} and "%" not in str(card.get("value", "")):
            errors.append(f"rate lost percentage unit: {card}")

    return errors
