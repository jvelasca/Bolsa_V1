"""PositionPolicyDecision — autorización de policy post-entrada (V1.44).

≠ ExitPlan ≠ ExitPermission ≠ ExecutionPlan ≠ auto-exit.
No ejecuta. No muta PositionState. No llama al Router.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from bolsa_analytics.cognitive.exit_plan import ExitPlan, ExitReason
from bolsa_analytics.cognitive.exit_policy import suggestion_from_exit_policy
from bolsa_analytics.cognitive.operating_policy import OperatingPolicy
from bolsa_analytics.cognitive.position_event import (
    PositionEvent,
    build_position_event,
    is_immediate_risk_reason,
    is_target_event_kind,
    position_event_kind_from_reason,
)
from bolsa_analytics.cognitive.position_state import PositionState, clamp_stop_not_worsen

PositionPolicyVerdict = Literal["HOLD", "PROTECT", "TRAIL", "REDUCE", "EXIT"]
PositionPolicyRiskImpact = Literal["none", "reduce", "protect", "exit"]
PositionPolicyAuthorization = Literal["human_confirm", "policy"]
PositionPolicyDeferReason = Literal["queue_next_session", "data_stale"]

POSITION_POLICY_DECISION_KEY = "positionPolicyDecision"


def _now_iso(at: str | None = None) -> str:
    if isinstance(at, str) and at.strip():
        return at
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class PositionPolicyDecision:
    verdict: PositionPolicyVerdict
    reason_code: ExitReason | None
    event: PositionEvent | None
    quantity: float | None
    new_stop: float | None
    target: float | None
    risk_impact: PositionPolicyRiskImpact
    policy_id: str
    as_of: str
    authorization: PositionPolicyAuthorization
    defer_reason: PositionPolicyDeferReason | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reasonCode": self.reason_code,
            "event": (
                {
                    "kind": self.event.kind,
                    "reasonCode": self.event.reason_code,
                    "at": self.event.at,
                }
                if self.event
                else None
            ),
            "quantity": self.quantity,
            "newStop": self.new_stop,
            "target": self.target,
            "riskImpact": self.risk_impact,
            "policyId": self.policy_id,
            "asOf": self.as_of,
            "authorization": self.authorization,
            "deferReason": self.defer_reason,
        }


def _hold(
    policy: OperatingPolicy,
    as_of: str,
    reason_code: ExitReason | None,
    event: PositionEvent | None,
    defer_reason: PositionPolicyDeferReason | None,
) -> PositionPolicyDecision:
    return PositionPolicyDecision(
        verdict="HOLD",
        reason_code=reason_code,
        event=event,
        quantity=None,
        new_stop=None,
        target=None,
        risk_impact="none",
        policy_id=policy.template_id,
        as_of=as_of,
        authorization="policy",
        defer_reason=defer_reason,
    )


def _echo_target(position: PositionState, reason: str | None) -> float | None:
    if reason == "TARGET_1":
        return position.target1
    if reason == "TARGET_2":
        return position.target2
    return None


def decide_position_policy(
    position: PositionState | None,
    exit_plan: ExitPlan | None,
    operating_policy: OperatingPolicy,
    *,
    session: str | None = None,
    stale: bool | None = None,
    stop_touched: bool | None = None,
    as_of: str | None = None,
) -> PositionPolicyDecision:
    stamp = _now_iso(as_of or (exit_plan.updated_at if exit_plan else None))
    reason = exit_plan.primary_reason if exit_plan else None
    event = build_position_event(reason, stamp)
    kind = position_event_kind_from_reason(reason)

    if position is None or exit_plan is None or not reason or kind is None:
        return _hold(operating_policy, stamp, reason, event, None)

    immediate = is_immediate_risk_reason(reason) or stop_touched is True

    if stale is True and not immediate:
        return _hold(operating_policy, stamp, reason, event, "data_stale")

    if session == "closed" and is_target_event_kind(kind) and not immediate:
        return _hold(operating_policy, stamp, reason, event, "queue_next_session")

    action, qty, stop = suggestion_from_exit_policy(
        reason,
        position.remaining_quantity,
        operating_policy.exit,
        exit_plan.suggested_stop,
    )

    if action == "hold":
        return _hold(operating_policy, stamp, reason, event, None)

    new_stop = stop
    if new_stop is not None and new_stop > 0:
        new_stop = clamp_stop_not_worsen(
            position.direction, position.current_stop, new_stop
        )

    if action == "protect":
        trail = reason == "TRAIL"
        return PositionPolicyDecision(
            verdict="TRAIL" if trail else "PROTECT",
            reason_code=reason,
            event=event,
            quantity=None,
            new_stop=new_stop,
            target=_echo_target(position, reason),
            risk_impact="protect",
            policy_id=operating_policy.template_id,
            as_of=stamp,
            authorization="policy",
            defer_reason=None,
        )

    if action == "reduce":
        return PositionPolicyDecision(
            verdict="REDUCE",
            reason_code=reason,
            event=event,
            quantity=qty,
            new_stop=None,
            target=_echo_target(position, reason),
            risk_impact="reduce",
            policy_id=operating_policy.template_id,
            as_of=stamp,
            authorization="policy",
            defer_reason=None,
        )

    return PositionPolicyDecision(
        verdict="EXIT",
        reason_code=reason,
        event=event,
        quantity=qty if qty is not None else position.remaining_quantity,
        new_stop=None,
        target=_echo_target(position, reason),
        risk_impact="exit",
        policy_id=operating_policy.template_id,
        as_of=stamp,
        authorization="policy",
        defer_reason=None,
    )
