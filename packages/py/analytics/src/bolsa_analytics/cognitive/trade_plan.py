"""TradePlan v0 — plan condicional sobre DecisionPackage (ADR-031).

No sustituye el spine: mapea tesis + gates a un estado operativo
(WATCH / ARMED / TRIGGERED / BLOCKED / EXPIRED) y un size por stop estructural.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TradePlanStatus = Literal["WATCH", "ARMED", "TRIGGERED", "BLOCKED", "EXPIRED"]
TradePlanDirection = Literal["long", "short", "none"]
WhyNotCode = Literal[
    "fit",
    "freshness",
    "mandate",
    "entry",
    "no_stop",
    "expired",
    "orphan",
    "rr",
    "regime",
]


@dataclass(frozen=True, slots=True)
class TradePlan:
    """Plan operativo mínimo (v0)."""

    decision_id: str
    instrument_id: str
    direction: TradePlanDirection
    status: TradePlanStatus
    quantity: float
    risk_pct: float
    why_not: tuple[str, ...]
    execution_allowed: bool
    opportunity_score: float | None = None
    actionability: float | None = None
    entry: float | None = None
    structural_stop: float | None = None
    expires_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "decisionId": self.decision_id,
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "status": self.status,
            "quantity": self.quantity,
            "riskPct": self.risk_pct,
            "whyNot": list(self.why_not),
            "executionAllowed": self.execution_allowed,
            "opportunityScore": self.opportunity_score,
            "actionability": self.actionability,
            "entry": self.entry,
            "structuralStop": self.structural_stop,
            "expiresAt": self.expires_at,
        }


def compute_risk_size(
    *,
    equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
) -> float:
    """Size = (equity × risk%) / |entry − stop|. 0 si stop inválido o equity≤0."""
    if equity <= 0 or risk_pct <= 0 or entry <= 0:
        return 0.0
    per_share = abs(entry - stop)
    if per_share <= 0:
        return 0.0
    return (equity * (risk_pct / 100.0)) / per_share


def _direction_from_action(action: str) -> TradePlanDirection:
    if action == "recommend_long":
        return "long"
    if action == "recommend_short":
        return "short"
    return "none"


def build_trade_plan(
    *,
    decision_id: str,
    instrument_id: str,
    action: str,
    fit_ok: bool = True,
    freshness_ok: bool = True,
    mandate_ok: bool = True,
    expired: bool = False,
    entry_ready: bool = False,
    entry: float | None = None,
    structural_stop: float | None = None,
    equity: float = 0.0,
    risk_pct: float = 0.5,
    opportunity_score: float | None = None,
    expires_at: str | None = None,
) -> TradePlan:
    """Mapper determinista DecisionPackage + gates → TradePlan v0.

    Golden A: entry_ready + stop válido + gates OK → TRIGGERED.
    Golden B: calidad alta pero entry_ready False → WATCH.
    Golden C: fit_ok False → BLOCKED.
    Golden H: expired → EXPIRED.
    """
    why: list[str] = []
    direction = _direction_from_action(action)
    stop_valid = (
        structural_stop is not None
        and entry is not None
        and entry > 0
        and (
            (direction == "long" and structural_stop < entry)
            or (direction == "short" and structural_stop > entry)
        )
    )

    if expired:
        why.append("expired")
        return TradePlan(
            decision_id=decision_id,
            instrument_id=instrument_id,
            direction=direction,
            status="EXPIRED",
            quantity=0.0,
            risk_pct=risk_pct,
            why_not=tuple(why),
            execution_allowed=False,
            opportunity_score=opportunity_score,
            actionability=0.0,
            entry=entry,
            structural_stop=structural_stop,
            expires_at=expires_at,
        )

    if not fit_ok:
        why.append("fit")
    if not freshness_ok:
        why.append("freshness")
    if not mandate_ok:
        why.append("mandate")
    if why:
        return TradePlan(
            decision_id=decision_id,
            instrument_id=instrument_id,
            direction=direction,
            status="BLOCKED",
            quantity=0.0,
            risk_pct=risk_pct,
            why_not=tuple(why),
            execution_allowed=False,
            opportunity_score=opportunity_score,
            actionability=0.0,
            entry=entry,
            structural_stop=structural_stop,
            expires_at=expires_at,
        )

    if action in {"wait", "reduce", "exit_hint"} or direction == "none":
        why.append("entry")
        return TradePlan(
            decision_id=decision_id,
            instrument_id=instrument_id,
            direction=direction,
            status="WATCH",
            quantity=0.0,
            risk_pct=risk_pct,
            why_not=tuple(why),
            execution_allowed=False,
            opportunity_score=opportunity_score,
            actionability=0.2,
            entry=entry,
            structural_stop=structural_stop,
            expires_at=expires_at,
        )

    if not stop_valid:
        why.append("no_stop")
        return TradePlan(
            decision_id=decision_id,
            instrument_id=instrument_id,
            direction=direction,
            status="WATCH",
            quantity=0.0,
            risk_pct=risk_pct,
            why_not=tuple(why),
            execution_allowed=False,
            opportunity_score=opportunity_score,
            actionability=0.3,
            entry=entry,
            structural_stop=structural_stop,
            expires_at=expires_at,
        )

    if not entry_ready:
        why.append("entry")
        return TradePlan(
            decision_id=decision_id,
            instrument_id=instrument_id,
            direction=direction,
            status="WATCH",
            quantity=0.0,
            risk_pct=risk_pct,
            why_not=tuple(why),
            execution_allowed=False,
            opportunity_score=opportunity_score,
            actionability=0.4,
            entry=entry,
            structural_stop=structural_stop,
            expires_at=expires_at,
        )

    qty = compute_risk_size(
        equity=equity,
        risk_pct=risk_pct,
        entry=float(entry),
        stop=float(structural_stop),
    )
    return TradePlan(
        decision_id=decision_id,
        instrument_id=instrument_id,
        direction=direction,
        status="TRIGGERED",
        quantity=qty,
        risk_pct=risk_pct,
        why_not=(),
        execution_allowed=qty > 0,
        opportunity_score=opportunity_score,
        actionability=0.95 if qty > 0 else 0.0,
        entry=entry,
        structural_stop=structural_stop,
        expires_at=expires_at,
    )
