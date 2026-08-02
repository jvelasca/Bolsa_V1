"""FundamentalAssessment — Assessment tipado FUND (no decide BUY)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from bolsa_analytics.knowledge.assessment import Assessment
from bolsa_analytics.knowledge.fundamental_facts import build_fundamental_fact_set
from bolsa_analytics.knowledge.fundamental_inputs import FundamentalInputs
from bolsa_analytics.knowledge.models import FactSet
from bolsa_analytics.knowledge.score_fund import ScoreFundResult, score_fund_from_facts
from bolsa_analytics.knowledge.technical_assessment import (
    BEARISH_THRESHOLD,
    BULLISH_THRESHOLD,
    DirectionalBias,
)

Stance = DirectionalBias


@dataclass(frozen=True, slots=True)
class FundamentalAssessment:
    assessment_id: str
    instrument_id: str
    timestamp: str
    score: float
    bias: Stance
    confidence: float
    coverage: float
    distress: bool
    components: dict[str, float]
    narrative_facts: tuple[str, ...]
    warnings: tuple[str, ...]
    fact_set_ref: str
    assessment_type: str = "fundamental"
    artifact_type: str = "ART-FUNDAMENTAL-ASSESSMENT"
    schema_version: str = "1.0.0"

    @property
    def facts(self) -> tuple[str, ...]:
        return self.narrative_facts

    def as_assessment(self) -> Assessment:
        return Assessment(
            assessment_id=self.assessment_id,
            assessment_type="fundamental",
            instrument_id=self.instrument_id,
            timestamp=self.timestamp,
            score=self.score,
            confidence=self.confidence,
            facts=self.narrative_facts,
            warnings=self.warnings,
            metadata={
                "bias": self.bias,
                "coverage": self.coverage,
                "distress": self.distress,
                "components": dict(self.components),
                "factSetRef": self.fact_set_ref,
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
            "distress": self.distress,
            "components": dict(self.components),
            "narrativeFacts": list(self.narrative_facts),
            "facts": list(self.narrative_facts),
            "warnings": list(self.warnings),
            "factSetRef": self.fact_set_ref,
        }


def bias_from_fund_score(score: float) -> Stance:
    if score >= BULLISH_THRESHOLD:
        return "bullish"
    if score <= BEARISH_THRESHOLD:
        return "bearish"
    return "neutral"


def build_fundamental_assessment(
    instrument_id: str,
    inputs: FundamentalInputs | dict | FactSet,
    *,
    timestamp: str | None = None,
    assessment_id: str | None = None,
) -> tuple[FundamentalAssessment, FactSet, ScoreFundResult]:
    ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(inputs, FactSet):
        fact_set = inputs
    else:
        fact_set = build_fundamental_fact_set(instrument_id, inputs, timestamp=ts)

    score_result = score_fund_from_facts(fact_set)
    bias = bias_from_fund_score(score_result.score)
    magnitude = abs(score_result.score)
    confidence = min(1.0, 0.3 + magnitude * 0.5 + score_result.coverage * 0.25)
    if score_result.distress:
        confidence *= 0.7

    warnings: list[str] = []
    if score_result.distress:
        warnings.append("Distress / solvencia crítica — bloquea long en Runtime")
    if score_result.coverage < 0.4:
        warnings.append("Baja cobertura fundamental")
    if bias == "neutral":
        warnings.append("Sesgo fundamental neutral")

    assessment = FundamentalAssessment(
        assessment_id=assessment_id or f"FA-{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        timestamp=ts,
        score=score_result.score,
        bias=bias,
        confidence=round(confidence, 3),
        coverage=score_result.coverage,
        distress=score_result.distress,
        components=dict(score_result.components),
        narrative_facts=score_result.claims,
        warnings=tuple(warnings),
        fact_set_ref=fact_set.fact_set_id,
    )
    return assessment, fact_set, score_result
