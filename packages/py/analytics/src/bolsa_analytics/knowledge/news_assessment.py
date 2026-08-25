"""NewsAssessment — sentimiento agregado de MarketEvents (no decide BUY)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from bolsa_analytics.knowledge.assessment import Assessment
from bolsa_analytics.knowledge.technical_assessment import (
    BEARISH_THRESHOLD,
    BULLISH_THRESHOLD,
    DirectionalBias,
)
from bolsa_domain.entities.market_event import (
    MarketEvent,
    MarketEventCalendar,
    event_decay_weight,
)


@dataclass(frozen=True, slots=True)
class NewsAssessment:
    assessment_id: str
    instrument_id: str
    timestamp: str
    score: float
    bias: DirectionalBias
    confidence: float
    coverage: float
    sentiment: float
    event_count: int
    narrative_facts: tuple[str, ...]
    warnings: tuple[str, ...]
    event_ids: tuple[str, ...]
    assessment_type: str = "news"
    artifact_type: str = "ART-NEWS-ASSESSMENT"
    schema_version: str = "1.0.0"

    @property
    def facts(self) -> tuple[str, ...]:
        return self.narrative_facts

    def as_assessment(self) -> Assessment:
        return Assessment(
            assessment_id=self.assessment_id,
            assessment_type="news",
            instrument_id=self.instrument_id,
            timestamp=self.timestamp,
            score=self.score,
            confidence=self.confidence,
            facts=self.narrative_facts,
            warnings=self.warnings,
            metadata={
                "bias": self.bias,
                "coverage": self.coverage,
                "sentiment": self.sentiment,
                "eventCount": self.event_count,
                "eventIds": list(self.event_ids),
                "components": {"sentiment": self.sentiment},
                "specializedArtifactType": self.artifact_type,
            },
        )

    def to_assessment_dict(self) -> dict[str, Any]:
        return self.as_assessment().to_assessment_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "type": self.assessment_type,
            "assessmentId": self.assessment_id,
            "instrumentId": self.instrument_id,
            "timestamp": self.timestamp,
            "score": self.score,
            "bias": self.bias,
            "confidence": self.confidence,
            "coverage": self.coverage,
            "sentiment": self.sentiment,
            "eventCount": self.event_count,
            "narrativeFacts": list(self.narrative_facts),
            "facts": list(self.narrative_facts),
            "warnings": list(self.warnings),
            "eventIds": list(self.event_ids),
        }


def bias_from_news_score(score: float) -> DirectionalBias:
    if score >= BULLISH_THRESHOLD:
        return "bullish"
    if score <= BEARISH_THRESHOLD:
        return "bearish"
    return "neutral"


def build_news_assessment(
    instrument_id: str,
    *,
    calendar: MarketEventCalendar | None = None,
    events: Sequence[MarketEvent] | None = None,
    symbol: str | None = None,
    timestamp: str | None = None,
    assessment_id: str | None = None,
) -> NewsAssessment:
    """
    Agrega sentiment×decay de eventos activos.
    Sin eventos → score 0, coverage baja, warning news_unavailable.
    """
    ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    now = datetime.now(UTC)
    sym = (symbol or instrument_id).upper()

    weighted: list[tuple[MarketEvent, float]] = []
    if calendar is not None:
        weighted = calendar.active_events(symbol=sym, now=now)
    elif events:
        for ev in events:
            w = event_decay_weight(ev, now=now)
            if w >= 0.05:
                weighted.append((ev, w))

    warnings: list[str] = []
    if not weighted:
        return NewsAssessment(
            assessment_id=assessment_id or f"NA-{uuid4().hex[:12]}",
            instrument_id=instrument_id,
            timestamp=ts,
            score=0.0,
            bias="neutral",
            confidence=0.15,
            coverage=0.0,
            sentiment=0.0,
            event_count=0,
            narrative_facts=("Sin noticias/eventos activos en calendario",),
            warnings=("news_unavailable",),
            event_ids=(),
        )

    num = 0.0
    den = 0.0
    facts: list[str] = []
    ids: list[str] = []
    for ev, w in weighted:
        num += ev.sentiment * w
        den += w
        ids.append(ev.event_id)
        facts.append(f"{ev.event_type}@{ev.entity} sent={ev.sentiment:.2f} w={w:.2f}")

    sentiment = num / den if den > 0 else 0.0
    score = round(max(-1.0, min(1.0, sentiment)), 4)
    coverage = min(1.0, den / max(1.0, len(weighted)))
    confidence = min(1.0, 0.25 + abs(score) * 0.4 + coverage * 0.35)
    bias = bias_from_news_score(score)
    if abs(score) < 0.15:
        warnings.append("Sentimiento de noticias casi neutro")
    if coverage < 0.3:
        warnings.append("Baja cobertura de eventos")

    return NewsAssessment(
        assessment_id=assessment_id or f"NA-{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        timestamp=ts,
        score=score,
        bias=bias,
        confidence=round(confidence, 3),
        coverage=round(coverage, 3),
        sentiment=round(sentiment, 4),
        event_count=len(weighted),
        narrative_facts=tuple(facts[:8]),
        warnings=tuple(warnings),
        event_ids=tuple(ids),
    )
