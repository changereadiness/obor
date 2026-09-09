#!/usr/bin/env python3
"""Validated evidence primitives built on semantic table observations.

Milestone 2: typed observations -> evidence bundle.
No editorial prose is generated here.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Optional

from .semantic_tables import Observation


@dataclass(frozen=True)
class DatasetObservation:
    population: int
    increased: int
    decreased: int
    unchanged: int
    period: Optional[str] = None
    subject: str = "monitored items"

    def validate(self) -> list[str]:
        errors = []
        if min(self.population, self.increased, self.decreased, self.unchanged) < 0:
            errors.append("dataset counts cannot be negative")
        if self.increased + self.decreased + self.unchanged != self.population:
            errors.append(
                f"dataset counts do not sum to population: "
                f"{self.increased}+{self.decreased}+{self.unchanged}!={self.population}"
            )
        return errors

    def to_dict(self) -> dict:
        return asdict(self)


def extract_dataset_observations(text: str, period: Optional[str] = None) -> list[DatasetObservation]:
    """Extract explicit up/down/flat population statements from prose.

    The extractor requires four explicit counts: population, increased,
    decreased, unchanged. It accepts source wording such as "50 kinds of
    important means of production" without assuming that the population noun
    must literally be "products".
    """
    text = re.sub(r"\s+", " ", text)

    # First find an explicit increase/decrease/flat triplet in source order.
    triplet = re.search(
        r"prices?\s+of\s+(\d+)\s+(?:products?|kinds?|items?)\s+increased.*?"
        r"(\d+)\s+(?:kinds?|products?|items?)\s+decreased.*?"
        r"(\d+)\s+(?:kinds?|products?|items?)\s+(?:remained\s+flat|were\s+unchanged|remained\s+unchanged)",
        text,
        re.I,
    )
    if not triplet:
        triplet = re.search(
            r"(\d+)\s+(?:products?|items?)\s+(?:increased|rose).*?"
            r"(\d+)\s+(?:products?|items?)\s+(?:decreased|fell).*?"
            r"(\d+)\s+(?:products?|items?)\s+(?:were\s+)?(?:unchanged|flat)",
            text,
            re.I,
        )
    if not triplet:
        return []

    increased, decreased, unchanged = map(int, triplet.groups())
    prefix = text[: triplet.start()]

    # Population must be explicit before the movement counts. Prefer language
    # tied to monitoring/tracking and keep the final matching number before the
    # triplet to avoid unrelated dates or category counts.
    population_matches = list(re.finditer(
        r"(?:monitor(?:ing|ed)?|tracked).*?\b(\d+)\b(?:\s+kinds?\s+of)?(?:\s+[A-Za-z-]+){0,7}",
        prefix,
        re.I,
    ))
    if not population_matches:
        population_matches = list(re.finditer(r"\b(\d+)\b\s+(?:monitored|tracked)", prefix, re.I))
    if not population_matches:
        return []
    population = int(population_matches[-1].group(1))

    obs = DatasetObservation(
        population=population,
        increased=increased,
        decreased=decreased,
        unchanged=unchanged,
        period=period,
    )
    return [obs] if not obs.validate() else []


@dataclass(frozen=True)
class EvidencePoint:
    kind: str
    label: str
    value: str
    context: str
    subject: Optional[str] = None
    metric: Optional[str] = None
    period: Optional[str] = None
    source_observation: Optional[Observation] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.source_observation:
            data["source_observation"] = self.source_observation.to_dict()
        return data


def _format_number(value: float) -> str:
    return f"{value:g}"


def observation_label(obs: Observation) -> str:
    labels = {
        "growth_rate_yoy": "YoY growth",
        "growth_rate_mom": "MoM growth",
        "price": "Current price",
        "price_change": "Price change",
        "price_change_rate": "Price change rate",
        "absolute_value": "Absolute value",
        "rate": "Rate",
    }
    return labels.get(obs.metric, obs.metric.replace("_", " ").title())


def observation_value(obs: Observation) -> str:
    base = _format_number(obs.value)
    if obs.unit == "%":
        sign = "+" if obs.value > 0 else ""
        return f"{sign}{base}%"
    if obs.unit:
        return f"{base} {obs.unit}"
    return base


def dataset_evidence(ds: DatasetObservation) -> list[EvidencePoint]:
    if ds.validate():
        return []
    pop = ds.population
    def pct(n: int) -> str:
        return f"{(100*n/pop):g}%" if pop else "n/a"
    return [
        EvidencePoint("dataset_distribution", "Decreased", f"{ds.decreased} of {pop}", pct(ds.decreased), period=ds.period),
        EvidencePoint("dataset_distribution", "Increased", f"{ds.increased} of {pop}", pct(ds.increased), period=ds.period),
        EvidencePoint("dataset_distribution", "Unchanged", f"{ds.unchanged} of {pop}", pct(ds.unchanged), period=ds.period),
    ]


def _priority(obs: Observation, primary_subject: Optional[str]) -> tuple:
    primary = 1 if primary_subject and obs.subject.lower() == primary_subject.lower() else 0
    metric_priority = {
        "growth_rate_yoy": 6,
        "price_change_rate": 6,
        "growth_rate_mom": 5,
        "price_change": 4,
        "absolute_value": 3,
        "price": 2,
        "rate": 1,
    }.get(obs.metric, 0)
    # Within comparable rate metrics, larger absolute movements are generally
    # more useful evidence than small incidental movements.
    magnitude = abs(obs.value) if obs.metric in {"growth_rate_yoy", "growth_rate_mom", "price_change_rate", "rate"} else 0
    return (primary, metric_priority, magnitude)


def select_key_evidence(
    observations: list[Observation],
    dataset_observations: Optional[list[DatasetObservation]] = None,
    primary_subject: Optional[str] = None,
    limit: int = 5,
) -> list[EvidencePoint]:
    """Select concise, typed evidence without changing its economic meaning."""
    selected: list[EvidencePoint] = []

    # Explicit population distributions are highly informative for market-basket
    # releases and take precedence over individual product movements.
    for ds in dataset_observations or []:
        for point in dataset_evidence(ds):
            if len(selected) < limit:
                selected.append(point)

    remaining = max(0, limit - len(selected))
    if remaining == 0:
        return selected

    ranked = sorted(observations, key=lambda o: _priority(o, primary_subject), reverse=True)
    seen: set[tuple] = set()
    for obs in ranked:
        # Avoid showing multiple metrics for the same subject/period unless the
        # primary subject needs an absolute value plus a rate.
        coarse = (obs.subject, obs.period)
        if coarse in seen and not (primary_subject and obs.subject.lower() == primary_subject.lower()):
            continue
        # Key evidence favors rate/change metrics. Absolute values are included
        # for the primary subject or when no rate/change exists for that row.
        if obs.metric in {"price", "absolute_value"} and not (primary_subject and obs.subject.lower() == primary_subject.lower()):
            has_rate = any(
                x.subject == obs.subject and x.period == obs.period and
                x.metric in {"growth_rate_yoy", "growth_rate_mom", "price_change_rate"}
                for x in observations
            )
            if has_rate:
                continue
        selected.append(EvidencePoint(
            kind="observation",
            label=observation_label(obs),
            value=observation_value(obs),
            context=obs.subject,
            subject=obs.subject,
            metric=obs.metric,
            period=obs.period,
            source_observation=obs,
        ))
        seen.add(coarse)
        if len(selected) >= limit:
            break
    return selected


def validate_evidence(points: list[EvidencePoint]) -> list[str]:
    errors = []
    for point in points:
        if point.kind == "observation" and point.source_observation:
            obs = point.source_observation
            if obs.metric in {"growth_rate_yoy", "growth_rate_mom", "price_change_rate", "rate"}:
                if "%" not in point.value:
                    errors.append(f"{obs.subject}: rate evidence lost percentage unit")
            if obs.metric in {"absolute_value", "price"} and obs.value >= 1000 and point.value.endswith("%"):
                errors.append(f"{obs.subject}: absolute value rendered as percentage")
    return errors
