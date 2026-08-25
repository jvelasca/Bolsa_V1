"""ExitPlan — plan condicional de salida (ADR-032 F3).

Simétrico a TradePlan, post-entrada. ≠ execution ≠ ExitPermission.
Thin exitRadar / trail / protect siguen advisory aparte; este módulo
**no** importa ni copia esos mappers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from bolsa_analytics.cognitive.position_state import PositionState

ExitReason = Literal[
    "STRUCTURAL_STOP",
    "THESIS_INVALIDATION",
    "TARGET_1",
    "TARGET_2",
    "TRAIL",
    "TIME_STOP",
    "PORTFOLIO_RISK",
    "MANUAL",
]
ExitPlanStatus = Literal["IDLE", "HINT", "ARMED", "TRIGGERED", "DONE"]
ExitSuggestedAction = Literal["hold", "protect", "reduce", "full_exit"]
TradePlanDirection = Literal["long", "short", "none"]

EXIT_PLAN_KEY = "exitPlan"

EXIT_REASON_PRECEDENCE: tuple[ExitReason, ...] = (
    "MANUAL",
    "STRUCTURAL_STOP",
    "THESIS_INVALIDATION",
    "PORTFOLIO_RISK",
    "TARGET_1",
    "TARGET_2",
    "TRAIL",
    "TIME_STOP",
)

_HARD_TRIGGER: frozenset[ExitReason] = frozenset(
    {
        "MANUAL",
        "STRUCTURAL_STOP",
        "THESIS_INVALIDATION",
        "PORTFOLIO_RISK",
        "TARGET_1",
        "TARGET_2",
    }
)


def _finite_positive(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0:
        return None
    return number


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


def _now_iso(at: str | None = None) -> str:
    if isinstance(at, str) and at.strip():
        return at
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stop_touched(direction: TradePlanDirection, mark: float, stop: float) -> bool:
    if direction == "long":
        return mark <= stop
    if direction == "short":
        return mark >= stop
    return False


def _target_touched(
    direction: TradePlanDirection, mark: float, target: float
) -> bool:
    if direction == "long":
        return mark >= target
    if direction == "short":
        return mark <= target
    return False


@dataclass(frozen=True, slots=True)
class ExitPlan:
    """Plan condicional de salida (F3)."""

    exit_plan_id: str
    position_id: str
    trade_plan_id: str
    instrument_id: str
    direction: TradePlanDirection
    status: ExitPlanStatus
    reasons: tuple[ExitReason, ...]
    primary_reason: ExitReason | None
    suggested_action: ExitSuggestedAction
    suggested_qty: float | None
    suggested_stop: float | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "exitPlanId": self.exit_plan_id,
            "positionId": self.position_id,
            "tradePlanId": self.trade_plan_id,
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "status": self.status,
            "reasons": list(self.reasons),
            "primaryReason": self.primary_reason,
            "suggestedAction": self.suggested_action,
            "suggestedQty": self.suggested_qty,
            "suggestedStop": self.suggested_stop,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


def _collect_reasons(
    position: PositionState,
    *,
    mark_price: float | None,
    now: str | None,
    expires_at: str | None,
    thesis_invalid: bool,
    portfolio_risk: bool,
    manual: bool,
    trail_hint: bool,
) -> list[ExitReason]:
    fired: set[ExitReason] = set()
    if manual:
        fired.add("MANUAL")
    if thesis_invalid:
        fired.add("THESIS_INVALIDATION")
    if portfolio_risk:
        fired.add("PORTFOLIO_RISK")
    if trail_hint:
        fired.add("TRAIL")

    if mark_price is not None:
        if position.current_stop is not None and position.current_stop > 0:
            if _stop_touched(position.direction, mark_price, position.current_stop):
                fired.add("STRUCTURAL_STOP")
        if position.target1 is not None and _target_touched(
            position.direction, mark_price, position.target1
        ):
            fired.add("TARGET_1")
        if position.target2 is not None and _target_touched(
            position.direction, mark_price, position.target2
        ):
            fired.add("TARGET_2")
        # H2: T2 no interpreta T1 a ciegas (no reduce mitad por atajo T1).
        if "TARGET_2" in fired:
            fired.discard("TARGET_1")

    now_s = now.strip() if isinstance(now, str) else ""
    exp_s = expires_at.strip() if isinstance(expires_at, str) else ""
    if now_s and exp_s and now_s >= exp_s:
        fired.add("TIME_STOP")

    return [r for r in EXIT_REASON_PRECEDENCE if r in fired]


def _derive_status(
    position: PositionState,
    primary: ExitReason | None,
    trail_stop: float | None,
) -> ExitPlanStatus:
    if position.status == "CLOSED" or position.remaining_quantity <= 0:
        return "DONE"
    if primary is None:
        return "IDLE"
    if primary in _HARD_TRIGGER:
        return "TRIGGERED"
    if primary == "TRAIL" and trail_stop is not None:
        return "ARMED"
    return "HINT"


def _derive_suggestion(
    status: ExitPlanStatus,
    primary: ExitReason | None,
    remaining: float,
    trail_stop: float | None,
) -> tuple[ExitSuggestedAction, float | None, float | None]:
    if status in ("DONE", "IDLE") or primary is None:
        return "hold", None, None
    if primary == "TARGET_1":
        return "reduce", _round4(remaining / 2), None
    if primary == "TRAIL":
        stop = _round4(trail_stop) if trail_stop is not None else None
        return "protect", None, stop
    return "full_exit", _round4(remaining), None


def build_exit_plan_from_position(
    position: PositionState | None,
    *,
    mark_price: float | None = None,
    now: str | None = None,
    expires_at: str | None = None,
    thesis_invalid: bool = False,
    portfolio_risk: bool = False,
    manual: bool = False,
    trail_hint: bool = False,
    trail_stop: float | None = None,
    exit_plan_id: str | None = None,
    at: str | None = None,
) -> ExitPlan | None:
    """Factory F3: PositionState + señales → ExitPlan. No muta PositionState."""
    if position is None:
        return None
    if position.direction not in ("long", "short"):
        return None

    mark = _finite_positive(mark_price) if mark_price is not None else None
    trail_s = _finite_positive(trail_stop) if trail_stop is not None else None

    reasons = _collect_reasons(
        position,
        mark_price=mark,
        now=now,
        expires_at=expires_at,
        thesis_invalid=thesis_invalid,
        portfolio_risk=portfolio_risk,
        manual=manual,
        trail_hint=trail_hint,
    )
    primary: ExitReason | None = reasons[0] if reasons else None
    status = _derive_status(position, primary, trail_s)
    action, qty, stop = _derive_suggestion(
        status, primary, position.remaining_quantity, trail_s
    )
    stamp = _now_iso(at)
    epid = (
        exit_plan_id.strip()
        if isinstance(exit_plan_id, str) and exit_plan_id.strip()
        else str(uuid4())
    )

    return ExitPlan(
        exit_plan_id=epid,
        position_id=position.position_id,
        trade_plan_id=position.trade_plan_id,
        instrument_id=position.instrument_id,
        direction=position.direction,
        status=status,
        reasons=tuple(reasons),
        primary_reason=primary,
        suggested_action=action,
        suggested_qty=qty,
        suggested_stop=stop,
        created_at=stamp,
        updated_at=stamp,
    )
