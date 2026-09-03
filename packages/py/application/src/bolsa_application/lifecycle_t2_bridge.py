"""V1.96/V1.97 — Shared FSM bridge: atomic T2_TRIGGERED + T2_EXECUTED (SEMI + AUTO).

V1.97: the pair is validated in memory and persisted in one savepoint via
``AppendLifecycleEvent`` (``append_many``). Callers that only ``execute(T2_EXECUTED)``
also get the atomic pair — including outbox ``direct_input``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bolsa_domain.lifecycle import LifecycleEventInput, LifecycleStoreEvent, reduce_lifecycle_events


def _parse_exec_at(exec_at: str) -> datetime | None:
    """Parse paper/ledger timestamps (Z, +00:00, or space-separated str(datetime))."""
    raw = exec_at.strip().replace(" ", "T")
    if raw.endswith("+00:00"):
        raw = raw[:-6] + "Z"
    try:
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def to_lifecycle_at(exec_at: str | None) -> str | None:
    """Normalize to canonical ``...SSS Z`` lifecycle timestamps."""
    if not isinstance(exec_at, str) or not exec_at.strip():
        return exec_at
    dt = _parse_exec_at(exec_at)
    if dt is None:
        return exec_at.strip()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def t2_trigger_at_before(exec_at: str | None) -> str | None:
    """T2_EXECUTED must be strictly after T2_TRIGGERED (time_regression)."""
    if not isinstance(exec_at, str) or not exec_at.strip():
        return exec_at
    dt = _parse_exec_at(exec_at)
    if dt is None:
        return exec_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (dt - timedelta(milliseconds=1)).astimezone(UTC).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"


def build_t2_triggered_input(execute_event: LifecycleEventInput) -> LifecycleEventInput:
    """Synthesize T2_TRIGGERED identity envelope for an imminent T2_EXECUTED."""
    exec_at = to_lifecycle_at(execute_event.at) or execute_event.at
    bridge_at = t2_trigger_at_before(exec_at) or exec_at
    return LifecycleEventInput(
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


def needs_atomic_t2_pair(
    existing: list[LifecycleStoreEvent],
    execute_event: LifecycleEventInput,
) -> bool:
    """True when T2_EXECUTED must be paired with a fresh T2_TRIGGERED from t1_executed."""
    if execute_event.kind != "T2_EXECUTED" or not existing:
        return False
    stage, _ = reduce_lifecycle_events(existing)
    return stage == "t1_executed"


# Backward-compatible name: V1.97 AppendLifecycleEvent.execute owns the pair.
# Kept so SEMI/AUTO call sites remain valid during transition; returns None (no-op).
async def maybe_append_t2_triggered_bridge(
    append: object,
    *,
    existing: list[LifecycleStoreEvent],
    execute_event: LifecycleEventInput,
) -> dict[str, object] | None:
    """V1.97 no-op — atomic pair lives in ``AppendLifecycleEvent.execute``.

    Previously appended T2_TRIGGERED in a separate savepoint. That path is removed
    so a mid-pair failure cannot leave a trigger without execute.
    """
    _ = (append, existing, execute_event)
    return None


__all__ = [
    "build_t2_triggered_input",
    "maybe_append_t2_triggered_bridge",
    "needs_atomic_t2_pair",
    "t2_trigger_at_before",
    "to_lifecycle_at",
]
