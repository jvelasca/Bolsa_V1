"""V1.96 — Shared FSM bridge: T2_TRIGGERED before T2_EXECUTED (SEMI + AUTO)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from bolsa_domain.lifecycle import LifecycleEventInput, LifecycleStoreEvent, reduce_lifecycle_events

from bolsa_application.lifecycle_event_store import AppendLifecycleEvent


def t2_trigger_at_before(exec_at: str | None) -> str | None:
    """T2_EXECUTED must be strictly after T2_TRIGGERED (time_regression)."""
    if not isinstance(exec_at, str) or not exec_at.endswith("Z"):
        return exec_at
    try:
        dt = datetime.fromisoformat(exec_at.replace("Z", "+00:00"))
        return (dt - timedelta(milliseconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except ValueError:
        return exec_at


async def maybe_append_t2_triggered_bridge(
    append: AppendLifecycleEvent,
    *,
    existing: list[LifecycleStoreEvent],
    execute_event: LifecycleEventInput,
) -> dict[str, Any] | None:
    """Insert T2_TRIGGERED when appending T2_EXECUTED from stage t1_executed.

    Returns an error dict if the bridge append fails; None if skipped or applied.
    """
    if execute_event.kind != "T2_EXECUTED" or not existing:
        return None
    stage, _ = reduce_lifecycle_events(existing)
    if stage != "t1_executed":
        return None
    bridge_at = t2_trigger_at_before(execute_event.at) or execute_event.at
    bridge = LifecycleEventInput(
        kind="T2_TRIGGERED",
        at=bridge_at,
        event_id=f"{execute_event.event_id}:t2_trigger",
        position_id=execute_event.position_id,
        account_id=execute_event.account_id,
        instrument_id=execute_event.instrument_id,
        decision_id=execute_event.decision_id,
        trade_plan_id=execute_event.trade_plan_id,
        symbol=execute_event.symbol,
        side=execute_event.side,
        reason=execute_event.reason,
    )
    bridge_result = await append.execute(bridge)
    if not bridge_result.ok:
        return {
            "status": "error",
            "reason": (
                bridge_result.error.code if bridge_result.error else "t2_trigger_failed"
            ),
            "kind": "T2_TRIGGERED",
            "positionId": execute_event.position_id,
        }
    return None


__all__ = ["maybe_append_t2_triggered_bridge", "t2_trigger_at_before"]
