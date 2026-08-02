"""Market State Engine — régimen / Macro antes del TA (RFC-008 D6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from bolsa_analytics.cognitive.evidence import Evidence, EvidenceBundle
from bolsa_analytics.cognitive.macro_facts import build_macro_fact_set
from bolsa_analytics.cognitive.macro_inputs import MacroInputs
from bolsa_analytics.cognitive.score_macro import ScoreMacroResult, score_macro_from_facts
from bolsa_analytics.cognitive.weight_rules import MarketRegime
from bolsa_analytics.knowledge.models import FactSet

Tradability = Literal["tradable", "reduce", "wait"]


@dataclass(frozen=True, slots=True)
class MarketState:
    """Snapshot de estado de mercado (ART-MARKET-STATE lógico)."""

    state_id: str
    timestamp: str
    regime: MarketRegime
    tradability: Tradability
    score_macro: ScoreMacroResult
    fact_set: FactSet
    evidence_bundle: EvidenceBundle
    notes: tuple[str, ...]

    @property
    def tradable(self) -> bool:
        return self.tradability != "wait"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stateId": self.state_id,
            "timestamp": self.timestamp,
            "regime": self.regime,
            "tradability": self.tradability,
            "tradable": self.tradable,
            "scoreMacro": self.score_macro.score,
            "coverage": self.score_macro.coverage,
            "stress": self.score_macro.stress,
            "factSetId": self.fact_set.fact_set_id,
            "notes": list(self.notes),
            "evidence": self.evidence_bundle.to_dict(),
        }


def classify_regime(score: ScoreMacroResult, fact_set: FactSet) -> MarketRegime:
    vol = fact_set.get("macro.volatility_regime")
    credit = fact_set.get("macro.credit")
    appetite = fact_set.get("macro.risk_appetite")

    if score.coverage < 0.35:
        return "uncertain"
    if score.stress or (vol and vol.value == "panic") or (credit and credit.value == "stress"):
        return "crisis"
    if score.score <= -0.45 or (appetite and appetite.value == "risk_off"):
        return "risk_off"
    if score.score >= 0.35 and (appetite is None or appetite.value in ("risk_on", "neutral")):
        return "risk_on"
    return "neutral"


def _tradability(regime: MarketRegime, score: ScoreMacroResult) -> Tradability:
    if regime == "crisis":
        return "wait"
    if regime == "risk_off" or score.stress:
        return "reduce"
    if regime == "uncertain" and score.coverage < 0.4:
        return "reduce"
    return "tradable"


def _build_evidence(
    state_id: str,
    regime: MarketRegime,
    score: ScoreMacroResult,
    fact_set: FactSet,
    ts: str,
) -> EvidenceBundle:
    direction: Literal["supports", "contradicts", "neutral"]
    if regime in ("crisis", "risk_off"):
        direction = "contradicts"
    elif regime == "risk_on":
        direction = "supports"
    else:
        direction = "neutral"

    regime_ev = Evidence(
        evidence_id=f"EV-REG-{uuid4().hex[:10]}",
        evidence_kind="market_regime",
        claim=f"regime={regime} tradability via Market State",
        direction=direction,
        weight=1.0,
        confidence=max(0.3, score.coverage),
        valid_from=ts,
        refs={"stateId": state_id, "regime": regime},
    )
    macro_ev = Evidence(
        evidence_id=f"EV-MAC-{uuid4().hex[:10]}",
        evidence_kind="macro",
        claim=f"Score_MACRO={score.score} coverage={score.coverage}",
        direction=direction,
        weight=abs(score.score),
        confidence=max(0.25, score.coverage),
        valid_from=ts,
        refs={"factSetId": fact_set.fact_set_id, "stateId": state_id},
    )
    return EvidenceBundle(
        bundle_id=f"EB-MS-{uuid4().hex[:10]}",
        instrument_id=fact_set.instrument_id,
        timestamp=ts,
        evidences=(regime_ev, macro_ev),
    )


def build_market_state(
    inputs: MacroInputs | dict | FactSet,
    *,
    timestamp: str | None = None,
) -> MarketState:
    """
    Market State Engine: Macro inputs → Facts → Score_MACRO → régimen → tradability.
    Crisis → tradability=wait (STOP antes de Opportunity / Context).
    """
    ts = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(inputs, FactSet):
        fact_set = inputs
    else:
        fact_set = build_macro_fact_set(inputs, timestamp=ts)

    score = score_macro_from_facts(fact_set)
    regime = classify_regime(score, fact_set)
    tradability = _tradability(regime, score)
    state_id = f"MS-{uuid4().hex[:12]}"
    bundle = _build_evidence(state_id, regime, score, fact_set, ts)
    notes = (
        f"MarketState regime={regime} tradability={tradability}",
        f"scoreMacro={score.score} coverage={score.coverage}",
    )
    return MarketState(
        state_id=state_id,
        timestamp=ts,
        regime=regime,
        tradability=tradability,
        score_macro=score,
        fact_set=fact_set,
        evidence_bundle=bundle,
        notes=notes,
    )


@dataclass(frozen=True, slots=True)
class ContextValidationResult:
    """¿Sigue válida la oportunidad tras Market State (+ blackouts opcionales)?"""

    valid: bool
    reason: str
    market_state_id: str | None = None
    high_impact_macro_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reason": self.reason,
            "marketStateId": self.market_state_id,
            "highImpactMacroActive": self.high_impact_macro_active,
        }


def validate_context(
    market_state: MarketState | None = None,
    *,
    high_impact_macro_active: bool = False,
    earnings_blackout: bool = False,
) -> ContextValidationResult:
    """
    Context Validation Engine (v1 D6): Market State + flags de eventos.
    No mezcla Opportunity con Permission — solo validez de contexto.
    """
    if market_state is not None and market_state.tradability == "wait":
        return ContextValidationResult(
            False,
            f"Market State {market_state.regime}: wait/STOP",
            market_state.state_id,
            high_impact_macro_active,
        )
    if high_impact_macro_active:
        return ContextValidationResult(
            False,
            "High-impact macro blackout activo",
            None if market_state is None else market_state.state_id,
            True,
        )
    if earnings_blackout:
        return ContextValidationResult(
            False,
            "Earnings blackout activo",
            None if market_state is None else market_state.state_id,
            high_impact_macro_active,
        )
    if market_state is not None and market_state.tradability == "reduce":
        return ContextValidationResult(
            True,
            f"Contexto válido con precaución ({market_state.regime})",
            market_state.state_id,
            high_impact_macro_active,
        )
    return ContextValidationResult(
        True,
        "Contexto válido",
        None if market_state is None else market_state.state_id,
        high_impact_macro_active,
    )
