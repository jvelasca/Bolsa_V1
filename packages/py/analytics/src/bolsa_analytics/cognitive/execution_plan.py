"""ExecutionPlan — plan de envío PAPER (ADR-032 F4).

Cadena PAPER → Journal → Replay → Validation.
≠ broker ≠ ExecuteTrade ≠ ExitPermission.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from bolsa_analytics.cognitive.exit_plan import ExitPlan, ExitReason, ExitSuggestedAction

ExecutionVenue = Literal["PAPER", "BROKER"]
ExecutionPlanStatus = Literal[
    "DRAFT",
    "PAPER_READY",
    "JOURNALED",
    "REPLAYED",
    "VALIDATED",
    "BLOCKED",
]
ExecutionIntentKind = Literal["market_exit", "reduce", "stop_amend"]
ExecutionSide = Literal["buy", "sell", "none"]
ExecutionBlockedReason = Literal["broker_not_allowed", "not_actionable"]
TradePlanDirection = Literal["long", "short", "none"]

EXECUTION_PLAN_KEY = "executionPlan"


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


@dataclass(frozen=True, slots=True)
class PaperProjection:
    price: float
    qty: float
    at: str

    def to_dict(self) -> dict[str, object]:
        return {"price": self.price, "qty": self.qty, "at": self.at}


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Plan de envío (F4). venue PAPER; broker → BLOCKED."""

    execution_plan_id: str
    exit_plan_id: str
    position_id: str
    trade_plan_id: str
    instrument_id: str
    direction: TradePlanDirection
    venue: ExecutionVenue
    status: ExecutionPlanStatus
    intent_kind: ExecutionIntentKind | None
    side: ExecutionSide
    quantity: float | None
    limit_price: float | None
    source_reason: ExitReason | None
    source_action: ExitSuggestedAction | None
    blocked_reason: ExecutionBlockedReason | None
    journal_ref: str | None
    replay_ref: str | None
    validation_ref: str | None
    paper_projection: PaperProjection | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "executionPlanId": self.execution_plan_id,
            "exitPlanId": self.exit_plan_id,
            "positionId": self.position_id,
            "tradePlanId": self.trade_plan_id,
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "venue": self.venue,
            "status": self.status,
            "intentKind": self.intent_kind,
            "side": self.side,
            "quantity": self.quantity,
            "limitPrice": self.limit_price,
            "sourceReason": self.source_reason,
            "sourceAction": self.source_action,
            "blockedReason": self.blocked_reason,
            "journalRef": self.journal_ref,
            "replayRef": self.replay_ref,
            "validationRef": self.validation_ref,
            "paperProjection": (
                self.paper_projection.to_dict() if self.paper_projection else None
            ),
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


def _closing_side(direction: TradePlanDirection) -> ExecutionSide:
    return "buy" if direction == "short" else "sell"


def _resolve_actionable(
    exit_plan: ExitPlan,
) -> tuple[ExecutionIntentKind, ExecutionSide, float | None, float | None, ExecutionPlanStatus] | None:
    if exit_plan.status == "TRIGGERED" and exit_plan.suggested_action in (
        "full_exit",
        "reduce",
    ):
        qty = exit_plan.suggested_qty
        if qty is None or qty <= 0:
            return None
        kind: ExecutionIntentKind = (
            "reduce" if exit_plan.suggested_action == "reduce" else "market_exit"
        )
        return kind, _closing_side(exit_plan.direction), _round4(qty), None, "PAPER_READY"
    if exit_plan.status == "ARMED" and exit_plan.suggested_action == "protect":
        stop = exit_plan.suggested_stop
        limit = _round4(stop) if stop is not None and stop > 0 else None
        return "stop_amend", "none", None, limit, "DRAFT"
    return None


def _projection(
    mark_price: float | None, qty: float | None, at: str
) -> PaperProjection | None:
    price = _finite_positive(mark_price) if mark_price is not None else None
    q = _finite_positive(qty) if qty is not None else None
    if price is None or q is None:
        return None
    return PaperProjection(price=_round4(price), qty=_round4(q), at=at)


def build_execution_plan_from_exit_plan(
    exit_plan: ExitPlan | None,
    *,
    mark_price: float | None = None,
    at: str | None = None,
    execution_plan_id: str | None = None,
    force_venue: ExecutionVenue | None = None,
) -> ExecutionPlan | None:
    """Factory F4: ExitPlan → ExecutionPlan PAPER. BROKER → BLOCKED. No ejecuta."""
    if exit_plan is None:
        return None
    if exit_plan.direction not in ("long", "short"):
        return None

    actionable = _resolve_actionable(exit_plan)
    if actionable is None:
        return None

    intent_kind, side, quantity, limit_price, status = actionable
    stamp = _now_iso(at)
    epid = (
        execution_plan_id.strip()
        if isinstance(execution_plan_id, str) and execution_plan_id.strip()
        else str(uuid4())
    )
    want_broker = force_venue == "BROKER"

    if want_broker:
        return ExecutionPlan(
            execution_plan_id=epid,
            exit_plan_id=exit_plan.exit_plan_id,
            position_id=exit_plan.position_id,
            trade_plan_id=exit_plan.trade_plan_id,
            instrument_id=exit_plan.instrument_id,
            direction=exit_plan.direction,
            venue="BROKER",
            status="BLOCKED",
            intent_kind=intent_kind,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            source_reason=exit_plan.primary_reason,
            source_action=exit_plan.suggested_action,
            blocked_reason="broker_not_allowed",
            journal_ref=None,
            replay_ref=None,
            validation_ref=None,
            paper_projection=None,
            created_at=stamp,
            updated_at=stamp,
        )

    proj = (
        _projection(mark_price, quantity, stamp)
        if status == "PAPER_READY"
        else None
    )
    return ExecutionPlan(
        execution_plan_id=epid,
        exit_plan_id=exit_plan.exit_plan_id,
        position_id=exit_plan.position_id,
        trade_plan_id=exit_plan.trade_plan_id,
        instrument_id=exit_plan.instrument_id,
        direction=exit_plan.direction,
        venue="PAPER",
        status=status,
        intent_kind=intent_kind,
        side=side,
        quantity=quantity,
        limit_price=limit_price,
        source_reason=exit_plan.primary_reason,
        source_action=exit_plan.suggested_action,
        blocked_reason=None,
        journal_ref=None,
        replay_ref=None,
        validation_ref=None,
        paper_projection=proj,
        created_at=stamp,
        updated_at=stamp,
    )


def stage_execution_journal(
    plan: ExecutionPlan | None,
    journal_ref: str | None = None,
    *,
    at: str | None = None,
) -> ExecutionPlan | None:
    if plan is None or plan.status != "PAPER_READY" or plan.venue != "PAPER":
        return None
    ref = journal_ref.strip() if isinstance(journal_ref, str) and journal_ref.strip() else plan.journal_ref
    return replace(plan, status="JOURNALED", journal_ref=ref, updated_at=_now_iso(at))


def stage_execution_replay(
    plan: ExecutionPlan | None,
    replay_ref: str | None = None,
    *,
    at: str | None = None,
) -> ExecutionPlan | None:
    if plan is None or plan.status != "JOURNALED":
        return None
    ref = replay_ref.strip() if isinstance(replay_ref, str) and replay_ref.strip() else plan.replay_ref
    return replace(plan, status="REPLAYED", replay_ref=ref, updated_at=_now_iso(at))


def stage_execution_validate(
    plan: ExecutionPlan | None,
    validation_ref: str | None = None,
    *,
    at: str | None = None,
) -> ExecutionPlan | None:
    if plan is None or plan.status != "REPLAYED":
        return None
    ref = (
        validation_ref.strip()
        if isinstance(validation_ref, str) and validation_ref.strip()
        else plan.validation_ref
    )
    return replace(
        plan, status="VALIDATED", validation_ref=ref, updated_at=_now_iso(at)
    )


def attempt_execution_broker(
    plan: ExecutionPlan | None,
    *,
    at: str | None = None,
) -> ExecutionPlan | None:
    """Cualquier intento broker → BLOCKED. Invariante F4."""
    if plan is None:
        return None
    if plan.status == "BLOCKED" and plan.blocked_reason == "broker_not_allowed":
        return plan
    return replace(
        plan,
        venue="BROKER",
        status="BLOCKED",
        blocked_reason="broker_not_allowed",
        updated_at=_now_iso(at),
    )
