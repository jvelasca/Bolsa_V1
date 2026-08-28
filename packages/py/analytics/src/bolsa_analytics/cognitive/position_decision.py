"""PositionDecision — proyección operativa (V1.27). No durable, no segundo motor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.exit_plan import ExitPlan, build_exit_plan_from_position
from bolsa_analytics.cognitive.exit_policy import ExitPolicy, resolve_exit_policy
from bolsa_analytics.cognitive.position_state import PositionState

PositionDecisionAction = Literal[
    "HOLD", "PROTECT", "REDUCE", "TAKE_PROFIT", "EXIT", "REVIEW"
]
PositionAttention = Literal["NORMAL", "ATTENTION", "URGENT", "BLOCKED"]
PositionNextEvent = Literal[
    "NONE", "T1", "T2", "STOP", "TRAIL", "THESIS_REVIEW", "RECONCILIATION"
]
PositionReconHealth = Literal["CLEAN", "ATTENTION", "CRITICAL"]

POSITION_DECISION_KEY = "positionDecision"

_ATT_RANK = {"NORMAL": 0, "ATTENTION": 1, "URGENT": 2, "BLOCKED": 3}


def map_recon_status_to_health(status: str | None) -> PositionReconHealth:
    s = (status or "").strip().lower()
    if s == "drift":
        return "CRITICAL"
    if s in ("clean", "ok"):
        return "CLEAN"
    return "ATTENTION"


def recon_health_to_attention(health: PositionReconHealth) -> PositionAttention:
    if health == "CRITICAL":
        return "BLOCKED"
    if health == "ATTENTION":
        return "ATTENTION"
    return "NORMAL"


def _max_attention(a: PositionAttention, b: PositionAttention) -> PositionAttention:
    return a if _ATT_RANK[a] >= _ATT_RANK[b] else b


def _next_event(position: PositionState, exit_plan: ExitPlan) -> PositionNextEvent:
    primary = exit_plan.primary_reason
    if primary == "STRUCTURAL_STOP":
        return "STOP"
    if primary == "THESIS_INVALIDATION":
        return "THESIS_REVIEW"
    if primary == "TARGET_1":
        return "T1"
    if primary == "TARGET_2":
        return "T2"
    if primary == "TRAIL":
        return "TRAIL"
    if not position.target1_achieved_at and position.target1 is not None:
        return "T1"
    if not position.target2_achieved_at and position.target2 is not None:
        return "T2"
    if position.current_stop is not None:
        return "STOP"
    return "NONE"


def _action_from_plan(
    exit_plan: ExitPlan,
    recon_health: PositionReconHealth,
    thesis_invalid: bool,
) -> PositionDecisionAction:
    if recon_health == "CRITICAL":
        return "REVIEW"
    if thesis_invalid or exit_plan.primary_reason == "THESIS_INVALIDATION":
        return "REVIEW"
    sug = exit_plan.suggested_action
    primary = exit_plan.primary_reason
    if sug == "protect":
        return "PROTECT"
    if sug == "full_exit":
        return "EXIT"
    if sug == "reduce":
        if primary in ("TARGET_1", "TARGET_2"):
            return "TAKE_PROFIT"
        return "REDUCE"
    return "HOLD"


@dataclass(frozen=True, slots=True)
class PositionDecision:
    position_id: str
    trade_plan_id: str
    action: PositionDecisionAction
    reason: str
    confidence: float
    attention: PositionAttention
    next_event: PositionNextEvent
    recon_health: PositionReconHealth
    suggested_qty: float | None
    suggested_stop: float | None
    primary_reason: str | None
    market_as_of: str | None
    expires_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "positionId": self.position_id,
            "tradePlanId": self.trade_plan_id,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "attention": self.attention,
            "nextEvent": self.next_event,
            "reconHealth": self.recon_health,
            "suggestedQty": self.suggested_qty,
            "suggestedStop": self.suggested_stop,
            "primaryReason": self.primary_reason,
            "marketAsOf": self.market_as_of,
            "expiresAt": self.expires_at,
        }


def build_position_decision(
    position: PositionState | None,
    *,
    mark_price: float | None = None,
    exit_policy: ExitPolicy | None = None,
    template_id: str | None = None,
    portfolio_recon_status: str | None = None,
    thesis_invalid: bool = False,
    at: str | None = None,
    now: str | None = None,
    expires_at: str | None = None,
    trail_hint: bool = False,
    trail_stop: float | None = None,
) -> PositionDecision | None:
    if position is None:
        return None
    if position.direction not in ("long", "short"):
        return None
    policy = exit_policy if exit_policy is not None else (
        resolve_exit_policy(template_id) if template_id else None
    )
    exit_plan = build_exit_plan_from_position(
        position,
        mark_price=mark_price,
        now=now,
        expires_at=expires_at,
        thesis_invalid=thesis_invalid,
        trail_hint=trail_hint,
        trail_stop=trail_stop,
        at=at,
        exit_policy=policy,
    )
    if exit_plan is None:
        return None

    recon_health = map_recon_status_to_health(portfolio_recon_status)
    attention = recon_health_to_attention(recon_health)
    action = _action_from_plan(exit_plan, recon_health, thesis_invalid)
    primary = exit_plan.primary_reason

    if primary == "STRUCTURAL_STOP":
        attention = _max_attention(attention, "URGENT")
    elif thesis_invalid or primary == "THESIS_INVALIDATION":
        attention = _max_attention(attention, "URGENT")
    elif action in ("REDUCE", "TAKE_PROFIT", "EXIT", "PROTECT"):
        attention = _max_attention(attention, "ATTENTION")

    if recon_health == "CRITICAL":
        reason = "reconciliation:portfolio_drift"
        next_event: PositionNextEvent = "RECONCILIATION"
    elif primary:
        reason = primary.lower()
        next_event = _next_event(position, exit_plan)
    else:
        reason = "hold"
        next_event = _next_event(position, exit_plan)

    confidence = 1.0 if attention == "BLOCKED" else (0.7 if action == "HOLD" and attention == "NORMAL" else 0.85)
    stamp = at or exit_plan.updated_at

    return PositionDecision(
        position_id=position.position_id,
        trade_plan_id=position.trade_plan_id,
        action=action,
        reason=reason,
        confidence=confidence,
        attention=attention,
        next_event=next_event,
        recon_health=recon_health,
        suggested_qty=exit_plan.suggested_qty,
        suggested_stop=exit_plan.suggested_stop,
        primary_reason=primary,
        market_as_of=stamp,
        expires_at=None,
    )
