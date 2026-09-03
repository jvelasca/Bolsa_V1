"""V1.90 — Map AUTO PositionPolicyDecision outcomes to lifecycle sidecar events.

Distinct from Confirm SEMI vocabulary (reduce=T1, exit_hint=close). AUTO can
emit T2_EXECUTED for TARGET_2 partial reduces and TRAIL_APPLIED for protect/trail.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from bolsa_application.lifecycle_event_store import AppendLifecycleEvent
from bolsa_domain.lifecycle import LifecycleEventInput, LifecycleEventKind

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LifecycleAutoMapping:
    kind: LifecycleEventKind
    position_id: str
    account_id: str
    instrument_id: str
    event_id: str
    fill_id: str | None = None
    quantity: float | None = None
    price: float | None = None
    previous_stop: float | None = None
    new_stop: float | None = None
    at: str | None = None
    decision_id: str | None = None
    trade_plan_id: str | None = None
    symbol: str | None = None
    reason: str | None = None
    venue: str = "PAPER"


def map_auto_verdict_to_kind(
    *,
    verdict: str,
    reason_code: str | None = None,
) -> LifecycleEventKind | None:
    v = (verdict or "").upper()
    reason = (reason_code or "").upper()
    if v in ("PROTECT", "TRAIL"):
        return "TRAIL_APPLIED"
    if v == "REDUCE":
        if reason == "TARGET_2":
            return "T2_EXECUTED"
        return "T1_EXECUTED"
    if v == "EXIT":
        return "POSITION_CLOSED"
    return None


def build_lifecycle_auto_mapping(
    *,
    verdict: str,
    reason_code: str | None,
    account_id: str,
    instrument_id: str,
    position_id: str,
    event_id: str,
    quantity: float | None = None,
    price: float | None = None,
    previous_stop: float | None = None,
    new_stop: float | None = None,
    filled_at: str | None = None,
    decision_id: str | None = None,
    trade_plan_id: str | None = None,
    symbol: str | None = None,
) -> LifecycleAutoMapping | None:
    kind = map_auto_verdict_to_kind(verdict=verdict, reason_code=reason_code)
    if kind is None:
        return None
    if not position_id.strip() or not event_id.strip():
        return None
    if not filled_at or not str(filled_at).strip():
        return None

    fill_id = event_id if kind in ("T1_EXECUTED", "T2_EXECUTED", "POSITION_CLOSED") else None
    return LifecycleAutoMapping(
        kind=kind,
        position_id=position_id.strip(),
        account_id=account_id,
        instrument_id=instrument_id,
        event_id=event_id.strip(),
        fill_id=fill_id,
        quantity=quantity,
        price=price,
        previous_stop=previous_stop,
        new_stop=new_stop,
        at=str(filled_at).strip(),
        decision_id=decision_id,
        trade_plan_id=trade_plan_id,
        symbol=symbol,
        reason=reason_code,
        venue="PAPER",
    )


def auto_mapping_to_input(mapping: LifecycleAutoMapping) -> LifecycleEventInput:
    return LifecycleEventInput(
        kind=mapping.kind,
        at=mapping.at,
        event_id=mapping.event_id,
        position_id=mapping.position_id,
        account_id=mapping.account_id,
        instrument_id=mapping.instrument_id,
        decision_id=mapping.decision_id,
        trade_plan_id=mapping.trade_plan_id,
        symbol=mapping.symbol,
        fill_id=mapping.fill_id,
        quantity=mapping.quantity,
        price=mapping.price,
        previous_stop=mapping.previous_stop,
        new_stop=mapping.new_stop,
        reason=mapping.reason,
        venue=mapping.venue,
        fees=0 if mapping.fill_id else None,
    )


def auto_mapping_to_direct_payload(mapping: LifecycleAutoMapping) -> dict[str, Any]:
    """Payload for outbox drain via direct_input (input_from_body)."""
    body: dict[str, Any] = {
        "kind": mapping.kind,
        "at": mapping.at,
        "eventId": mapping.event_id,
        "positionId": mapping.position_id,
        "accountId": mapping.account_id,
        "instrumentId": mapping.instrument_id,
        "venue": mapping.venue,
    }
    if mapping.fill_id:
        body["fillId"] = mapping.fill_id
    if mapping.quantity is not None:
        body["quantity"] = mapping.quantity
    if mapping.price is not None:
        body["price"] = mapping.price
    if mapping.previous_stop is not None:
        body["previousStop"] = mapping.previous_stop
    if mapping.new_stop is not None:
        body["newStop"] = mapping.new_stop
    if mapping.decision_id:
        body["decisionId"] = mapping.decision_id
    if mapping.trade_plan_id:
        body["tradePlanId"] = mapping.trade_plan_id
    if mapping.symbol:
        body["symbol"] = mapping.symbol
    if mapping.reason:
        body["reason"] = mapping.reason
    return {"direct_input": body}


async def append_lifecycle_from_auto(
    append: AppendLifecycleEvent | None,
    *,
    mapping: LifecycleAutoMapping,
    outbox: Any | None = None,
) -> dict[str, Any]:
    """Enqueue lifecycle sidecar for AUTO (same TX as PositionState when outbox).

    V1.91: with outbox, enqueue failure propagates (rollback with PositionState).
    Drain is post-COMMIT. Without outbox, legacy direct append remains fail-soft.
    """
    if append is None and outbox is None:
        return {"status": "skipped", "reason": "lifecycle_append_not_wired"}

    if outbox is not None:
        # Same TX discipline as PositionSync — do not swallow enqueue errors.
        await outbox.enqueue(
            position_id=mapping.position_id,
            account_id=mapping.account_id,
            transaction_id=mapping.event_id,
            kind=mapping.kind,
            payload=auto_mapping_to_direct_payload(mapping),
        )
        return {
            "status": "pending",
            "kind": mapping.kind,
            "positionId": mapping.position_id,
            "eventId": mapping.event_id,
        }

    assert append is not None
    try:
        # Inherit identity from open event when present.
        existing = await append.store.list_by_position(mapping.position_id)
        input_event = auto_mapping_to_input(mapping)
        if existing:
            anchor = existing[0]
            input_event = LifecycleEventInput(
                kind=mapping.kind,
                at=mapping.at,
                event_id=mapping.event_id,
                position_id=mapping.position_id,
                # Prefer envelope from open event (identity must match).
                account_id=anchor.account_id or mapping.account_id,
                instrument_id=anchor.instrument_id or mapping.instrument_id,
                decision_id=anchor.decision_id or mapping.decision_id,
                trade_plan_id=anchor.trade_plan_id or mapping.trade_plan_id,
                symbol=anchor.symbol or mapping.symbol,
                fill_id=mapping.fill_id,
                quantity=mapping.quantity,
                price=mapping.price,
                previous_stop=mapping.previous_stop,
                new_stop=mapping.new_stop,
                reason=mapping.reason,
                venue=mapping.venue,
                fees=0 if mapping.fill_id else None,
                side=anchor.side,
            )

        # FSM requires T2_TRIGGERED before T2_EXECUTED — insert bridge if needed.
        if mapping.kind == "T2_EXECUTED" and existing:
            from bolsa_domain.lifecycle import reduce_lifecycle_events

            stage, _ = reduce_lifecycle_events(existing)
            if stage == "t1_executed":
                bridge_at = mapping.at
                # T2_EXECUTED must be strictly after T2_TRIGGERED.
                exec_at = mapping.at
                if isinstance(exec_at, str) and exec_at.endswith("Z"):
                    # bump execute by 1ms for time_regression invariant
                    try:
                        from datetime import datetime, timedelta

                        dt = datetime.fromisoformat(exec_at.replace("Z", "+00:00"))
                        bridge_at = (
                            (dt - timedelta(milliseconds=1))
                            .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                            + "Z"
                        )
                    except ValueError:
                        bridge_at = exec_at
                bridge = LifecycleEventInput(
                    kind="T2_TRIGGERED",
                    at=bridge_at,
                    event_id=f"{mapping.event_id}:t2_trigger",
                    position_id=input_event.position_id,
                    account_id=input_event.account_id,
                    instrument_id=input_event.instrument_id,
                    decision_id=input_event.decision_id,
                    trade_plan_id=input_event.trade_plan_id,
                    symbol=input_event.symbol,
                    side=getattr(input_event, "side", None),
                    reason=mapping.reason,
                )
                bridge_result = await append.execute(bridge)
                if not bridge_result.ok:
                    bridge_reason: str = (
                        bridge_result.error.code
                        if bridge_result.error
                        else "t2_trigger_failed"
                    )
                    return {
                        "status": "error",
                        "reason": bridge_reason,
                        "kind": "T2_TRIGGERED",
                        "positionId": mapping.position_id,
                    }

        result = await append.execute(input_event)
        if not result.ok:
            append_reason: str = (
                result.error.code if result.error else "append_failed"
            )
            logger.warning(
                "lifecycle_from_auto append failed kind=%s code=%s",
                mapping.kind,
                append_reason,
            )
            return {
                "status": "error",
                "reason": append_reason,
                "kind": mapping.kind,
                "positionId": mapping.position_id,
            }
        return {
            "status": "applied",
            "idempotent": result.idempotent,
            "kind": mapping.kind,
            "stage": result.stage,
            "positionId": mapping.position_id,
            "eventId": mapping.event_id,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("lifecycle_from_auto exception: %s", exc)
        return {"status": "error", "reason": str(exc)}


__all__ = [
    "LifecycleAutoMapping",
    "append_lifecycle_from_auto",
    "auto_mapping_to_direct_payload",
    "auto_mapping_to_input",
    "build_lifecycle_auto_mapping",
    "map_auto_verdict_to_kind",
]
