"""TradePlan v0 — plan condicional sobre DecisionPackage (ADR-031).

No sustituye el spine: mapea tesis + gates a un estado operativo
(WATCH / ARMED / TRIGGERED / BLOCKED / EXPIRED) y un size por stop estructural.
"""

from __future__ import annotations

from collections.abc import Sequence
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


def compliance_fit_ok(compliance_check: object) -> bool:
    """True unless ``compliance_check`` is a dict with ``passed is False``.

    Propose no re-ejecuta cesta: un veto de Fit ya materializado en el package
    marca el plan BLOCKED; ausencia o forma rara no inventa un fail.
    """
    return not (
        isinstance(compliance_check, dict) and compliance_check.get("passed") is False
    )


# Ciclo 4.0 — stop estructural (no familias EntrySetup).
ATR_MULT = 1.5
SWING_LOOKBACK = 10

# Ciclo 4.1 — Golden G: no nuevos longs en régimen adverso (TradePlan only).
NO_NEW_LONGS_REGIMES = frozenset({"risk_off", "crisis"})


def no_new_longs_blocks(*, action: str, market_regime: str | None) -> bool:
    """True si long y régimen en risk_off/crisis. Sin régimen → no veta (D6)."""
    if market_regime is None or market_regime not in NO_NEW_LONGS_REGIMES:
        return False
    return _direction_from_action(action) == "long"


def _finite_positive(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:  # NaN or non-positive
        return None
    return number


def _bar_px(bar: object, attr: str) -> float | None:
    return _finite_positive(getattr(bar, attr, None))


def compute_structural_stop(
    *,
    action: str,
    entry: float | None,
    atr: float | None = None,
    bars: Sequence[object] | None = None,
) -> float | None:
    """Stop más lejano de ATR×1.5 y swing de 10 barras cerradas.

    No se acerca el stop para caber en el riesgo: se elige el candidato más
    lejos de ``entry`` (min long / max short). Sin candidatos válidos → None.
    """
    if entry is None or entry <= 0:
        return None
    direction = _direction_from_action(action)
    if direction == "none":
        return None

    candidates: list[float] = []
    atr_val = _finite_positive(atr)
    if atr_val is not None:
        if direction == "long":
            atr_stop = entry - ATR_MULT * atr_val
            if atr_stop > 0 and atr_stop < entry:
                candidates.append(atr_stop)
        else:
            atr_stop = entry + ATR_MULT * atr_val
            if atr_stop > entry:
                candidates.append(atr_stop)

    if bars is not None and len(bars) >= SWING_LOOKBACK + 1:
        window = bars[-(SWING_LOOKBACK + 1) : -1]
        if direction == "long":
            lows = [_bar_px(bar, "low") for bar in window]
            valid = [low for low in lows if low is not None and low < entry]
            if valid:
                candidates.append(min(valid))
        else:
            highs = [_bar_px(bar, "high") for bar in window]
            valid = [high for high in highs if high is not None and high > entry]
            if valid:
                candidates.append(max(valid))

    if not candidates:
        return None
    return min(candidates) if direction == "long" else max(candidates)


def entry_ready_from_ta(
    *,
    action: str,
    bias: str | None,
    exhaustion: bool = False,
) -> bool:
    """Ciclo 4.0: listo si la acción alinea con bias TA y no hay exhaustion."""
    if exhaustion:
        return False
    if action == "recommend_long":
        return bias == "bullish"
    if action == "recommend_short":
        return bias == "bearish"
    return False


def build_v0_trade_plan_dict(
    *,
    decision_id: str,
    instrument_id: str,
    action: str,
    compliance_check: object = None,
    entry: float | None,
    opportunity_score: float | None,
    expires_at: str | None,
    expired: bool = False,
    atr: float | None = None,
    bars: Sequence[object] | None = None,
    bias: str | None = None,
    exhaustion: bool = False,
    equity: float = 0.0,
    risk_pct: float = 0.5,
    market_regime: str | None = None,
) -> dict[str, object]:
    """TradePlan persistible (PLAN layer; ranking ≠ BUY).

    Freshness/mandate quedan True: esos gates viven en confirm ``check_opening``.
    Sin ATR/barras/bias (rebuild confirm) → ``WATCH`` / ``no_stop`` o ``entry``.
    Sin ``market_regime`` → no inventa veto ``regime`` (Ciclo 4.1 D6).
    """
    structural_stop = compute_structural_stop(
        action=action, entry=entry, atr=atr, bars=bars
    )
    plan = build_trade_plan(
        decision_id=decision_id,
        instrument_id=instrument_id,
        action=action,
        fit_ok=compliance_fit_ok(compliance_check),
        freshness_ok=True,
        mandate_ok=True,
        expired=expired,
        entry_ready=entry_ready_from_ta(
            action=action, bias=bias, exhaustion=exhaustion
        ),
        entry=entry,
        structural_stop=structural_stop,
        equity=equity,
        risk_pct=risk_pct,
        opportunity_score=opportunity_score,
        expires_at=expires_at,
        market_regime=market_regime,
    )
    return plan.to_dict()


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
    market_regime: str | None = None,
) -> TradePlan:
    """Mapper determinista DecisionPackage + gates → TradePlan v0.

    Golden A: entry_ready + stop válido + gates OK → TRIGGERED.
    Golden B: calidad alta pero entry_ready False → WATCH.
    Golden C: fit_ok False → BLOCKED.
    Golden G: long + risk_off/crisis → BLOCKED (why regime).
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

    if no_new_longs_blocks(action=action, market_regime=market_regime):
        why.append("regime")
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
