"""MacroAssessment — Assessment tipado Macro (no decide BUY)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from bolsa_analytics.cognitive.macro_facts import build_macro_fact_set
from bolsa_analytics.cognitive.macro_inputs import MacroInputs
from bolsa_analytics.cognitive.market_state import MarketState, Tradability
from bolsa_analytics.cognitive.score_macro import ScoreMacroResult, score_macro_from_facts
from bolsa_analytics.cognitive.weight_rules import MarketRegime
from bolsa_analytics.knowledge.assessment import Assessment
from bolsa_analytics.knowledge.models import FactSet
from bolsa_analytics.knowledge.technical_assessment import (
    BEARISH_THRESHOLD,
    BULLISH_THRESHOLD,
    DirectionalBias,
)

Stance = DirectionalBias


@dataclass(frozen=True, slots=True)
class MacroAssessment:
    assessment_id: str
    instrument_id: str
    timestamp: str
    score: float
    bias: Stance
    confidence: float
    coverage: float
    stress: bool
    regime: MarketRegime
    tradability: Tradability
    components: dict[str, float]
    narrative_facts: tuple[str, ...]
    warnings: tuple[str, ...]
    fact_set_ref: str
    assessment_type: str = "macro"
    artifact_type: str = "ART-MACRO-ASSESSMENT"
    schema_version: str = "1.0.0"

    @property
    def facts(self) -> tuple[str, ...]:
        return self.narrative_facts

    def as_assessment(self) -> Assessment:
        return Assessment(
            assessment_id=self.assessment_id,
            assessment_type="macro",
            instrument_id=self.instrument_id,
            timestamp=self.timestamp,
            score=self.score,
            confidence=self.confidence,
            facts=self.narrative_facts,
            warnings=self.warnings,
            metadata={
                "bias": self.bias,
                "coverage": self.coverage,
                "stress": self.stress,
                "regime": self.regime,
                "tradability": self.tradability,
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
            "stress": self.stress,
            "regime": self.regime,
            "tradability": self.tradability,
            "components": dict(self.components),
            "narrativeFacts": list(self.narrative_facts),
            "facts": list(self.narrative_facts),
            "warnings": list(self.warnings),
            "factSetRef": self.fact_set_ref,
        }


def bias_from_macro_score(score: float) -> Stance:
    if score >= BULLISH_THRESHOLD:
        return "bullish"
    if score <= BEARISH_THRESHOLD:
        return "bearish"
    return "neutral"


def build_macro_assessment(
    instrument_id: str,
    inputs: MacroInputs | dict | FactSet | MarketState,
    *,
    timestamp: str | None = None,
    assessment_id: str | None = None,
    regime: MarketRegime | None = None,
    tradability: Tradability | None = None,
) -> tuple[MacroAssessment, FactSet, ScoreMacroResult]:
    """Desde MacroInputs / FactSet / MarketState → MacroAssessment."""
    ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")

    if isinstance(inputs, MarketState):
        fact_set = inputs.fact_set
        score_result = inputs.score_macro
        regime_v = inputs.regime
        tradability_v = inputs.tradability
        ts = inputs.timestamp
    elif isinstance(inputs, FactSet):
        fact_set = inputs
        score_result = score_macro_from_facts(fact_set)
        from bolsa_analytics.cognitive.market_state import _tradability, classify_regime

        regime_v = regime or classify_regime(score_result, fact_set)
        tradability_v = tradability or _tradability(regime_v, score_result)
    else:
        fact_set = build_macro_fact_set(inputs if isinstance(inputs, MacroInputs) else MacroInputs.from_dict(inputs), timestamp=ts)
        score_result = score_macro_from_facts(fact_set)
        from bolsa_analytics.cognitive.market_state import _tradability, classify_regime

        regime_v = regime or classify_regime(score_result, fact_set)
        tradability_v = tradability or _tradability(regime_v, score_result)

    bias = bias_from_macro_score(score_result.score)
    magnitude = abs(score_result.score)
    confidence = min(1.0, 0.3 + magnitude * 0.45 + score_result.coverage * 0.3)
    if score_result.stress:
        confidence *= 0.8

    warnings: list[str] = []
    if score_result.stress:
        warnings.append("Estrés macro (volatilidad/crédito)")
    if tradability_v == "wait":
        warnings.append("Tradability=wait — Runtime no abre long")
    if regime_v == "crisis":
        warnings.append("Régimen crisis")
    if score_result.coverage < 0.35:
        warnings.append("Baja cobertura macro")

    assessment = MacroAssessment(
        assessment_id=assessment_id or f"MA-{uuid4().hex[:12]}",
        instrument_id=instrument_id,
        timestamp=ts,
        score=score_result.score,
        bias=bias,
        confidence=round(confidence, 3),
        coverage=score_result.coverage,
        stress=score_result.stress,
        regime=regime_v,
        tradability=tradability_v,
        components=dict(score_result.components),
        narrative_facts=score_result.claims,
        warnings=tuple(warnings),
        fact_set_ref=fact_set.fact_set_id,
    )
    return assessment, fact_set, score_result
