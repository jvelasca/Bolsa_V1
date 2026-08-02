"""TechnicalAssessment — Assessment tipado TA (extends Assessment envelope)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from bolsa_analytics.knowledge.assessment import Assessment
from bolsa_analytics.knowledge.models import FactSet, TechnicalInputs
from bolsa_analytics.knowledge.score_ta import ScoreTaResult, score_ta_from_facts
from bolsa_analytics.knowledge.technical_facts import build_technical_fact_set

DirectionalBias = Literal["bullish", "bearish", "neutral"]

BULLISH_THRESHOLD = 0.35
BEARISH_THRESHOLD = -0.35


@dataclass(frozen=True, slots=True)
class TechnicalAssessment:
    """
    Interpretación técnica. Nunca emite recommend_long/short.
    Implementa el contrato Assessment vía `as_assessment()` / campos base.
    """

    assessment_id: str
    instrument_id: str
    timestamp: str
    score: float
    bias: DirectionalBias
    confidence: float
    coverage: float
    exhaustion: bool
    components: dict[str, float]
    narrative_facts: tuple[str, ...]
    warnings: tuple[str, ...]
    fact_set_ref: str
    assessment_type: str = "technical"
    artifact_type: str = "ART-TECHNICAL-ASSESSMENT"
    schema_version: str = "1.0.0"

    @property
    def facts(self) -> tuple[str, ...]:
        return self.narrative_facts

    def as_assessment(self) -> Assessment:
        """Proyección al envelope común (Runtime / colecciones heterogéneas)."""
        return Assessment(
            assessment_id=self.assessment_id,
            assessment_type="technical",
            instrument_id=self.instrument_id,
            timestamp=self.timestamp,
            score=self.score,
            confidence=self.confidence,
            facts=self.narrative_facts,
            warnings=self.warnings,
            metadata={
                "bias": self.bias,
                "coverage": self.coverage,
                "exhaustion": self.exhaustion,
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
            "exhaustion": self.exhaustion,
            "components": {
                "trend": self.components.get("trend", 0.0),
                "momentum": self.components.get("momentum", 0.0),
                "volatility": self.components.get("structure", 0.0),
                "pattern": self.components.get("structure", 0.0),
                "volume": self.components.get("participation", 0.0),
                **{k: v for k, v in self.components.items()},
            },
            "narrativeFacts": list(self.narrative_facts),
            "facts": list(self.narrative_facts),
            "warnings": list(self.warnings),
            "factSetRef": self.fact_set_ref,
        }


def bias_from_score(score: float) -> DirectionalBias:
    if score >= BULLISH_THRESHOLD:
        return "bullish"
    if score <= BEARISH_THRESHOLD:
        return "bearish"
    return "neutral"


def build_technical_assessment(
    instrument_id: str,
    inputs: TechnicalInputs | dict | FactSet,
    *,
    timestamp: str | None = None,
    assessment_id: str | None = None,
) -> tuple[TechnicalAssessment, FactSet, ScoreTaResult]:
    """Feature/Facts → TechnicalAssessment. No Recommendation."""
    ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(inputs, FactSet):
        fact_set = inputs
    else:
        fact_set = build_technical_fact_set(instrument_id, inputs, timestamp=ts)

    score_result = score_ta_from_facts(fact_set)
    bias = bias_from_score(score_result.score)

    magnitude = abs(score_result.score)
    confidence = min(1.0, 0.35 + magnitude * 0.55 + score_result.coverage * 0.2)
    if score_result.exhaustion:
        confidence *= 0.85

    warnings: list[str] = []
    if score_result.exhaustion:
        warnings.append("Agotamiento / overextension detectado")
    if score_result.coverage < 0.5:
        warnings.append("Baja cobertura de hechos técnicos")
    if bias == "neutral":
        warnings.append("Sesgo técnico neutral — sin dirección clara")

    assessment = TechnicalAssessment(
        assessment_id=assessment_id or f"TA-{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        timestamp=ts,
        score=score_result.score,
        bias=bias,
        confidence=round(confidence, 3),
        coverage=score_result.coverage,
        exhaustion=score_result.exhaustion,
        components=dict(score_result.components),
        narrative_facts=score_result.claims,
        warnings=tuple(warnings),
        fact_set_ref=fact_set.fact_set_id,
    )
    return assessment, fact_set, score_result
