"""V1.89 — Map Confirm/paper fills to lifecycle sidecar events (no cash merge)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from bolsa_domain.lifecycle import LifecycleEventInput, LifecycleEventKind

from bolsa_application.lifecycle_event_store import AppendLifecycleEvent
from bolsa_application.persist_position_from_fill import ledger_position_id_from_trade

logger = logging.getLogger(__name__)

# Mirror confirm.actions — avoid circular import via confirm.__init__.
_OPENING_ACTIONS = frozenset({"recommend_long", "recommend_short"})
_CLOSING_ACTIONS = frozenset({"exit_hint", "reduce"})

LifecycleFillAction = Literal["open", "reduce", "exit", "skip"]


@dataclass(frozen=True, slots=True)
class LifecycleFillMapping:
    kind: LifecycleEventKind
    position_id: str
    account_id: str
    instrument_id: str
    quantity: float
    price: float
    fill_id: str
    event_id: str
    decision_id: str | None = None
    trade_plan_id: str | None = None
    symbol: str | None = None
    at: str | None = None
    venue: str = "PAPER"


def _iso_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def map_confirm_fill_action(action: str) -> LifecycleFillAction:
    if action in _OPENING_ACTIONS:
        return "open"
    if action == "reduce":
        return "reduce"
    if action in _CLOSING_ACTIONS:
        return "exit"
    return "skip"


def resolve_lifecycle_position_id(
    *,
    trade: Any,
    instrument_id: str,
    open_position_id: str | None = None,
) -> str | None:
    if isinstance(open_position_id, str) and open_position_id.strip():
        return open_position_id.strip()
    return ledger_position_id_from_trade(trade, instrument_id)


def build_lifecycle_fill_mapping(
    *,
    action: str,
    account_id: str,
    instrument_id: str,
    quantity: float,
    price: float,
    tx_id: str,
    trade: Any,
    trade_plan_dict: dict[str, Any] | None = None,
    decision_id: str | None = None,
    symbol: str | None = None,
    open_position_id: str | None = None,
    filled_at: str | None = None,
) -> LifecycleFillMapping | None:
    mapped = map_confirm_fill_action(action)
    if mapped == "skip":
        return None
    position_id = resolve_lifecycle_position_id(
        trade=trade,
        instrument_id=instrument_id,
        open_position_id=open_position_id,
    )
    if not position_id or not tx_id.strip():
        return None

    kind: LifecycleEventKind
    if mapped == "open":
        kind = "POSITION_OPENED"
    elif mapped == "reduce":
        kind = "T1_EXECUTED"
    else:
        kind = "POSITION_CLOSED"

    plan = trade_plan_dict if isinstance(trade_plan_dict, dict) else {}
    plan_id = plan.get("id") or plan.get("tradePlanId") or plan.get("trade_plan_id")
    plan_id_s = plan_id.strip() if isinstance(plan_id, str) and plan_id.strip() else None
    sym = symbol
    if not sym:
        raw_sym = plan.get("symbol")
        sym = raw_sym.strip() if isinstance(raw_sym, str) and raw_sym.strip() else None

    return LifecycleFillMapping(
        kind=kind,
        position_id=position_id,
        account_id=account_id,
        instrument_id=instrument_id,
        quantity=quantity,
        price=price,
        fill_id=tx_id,
        event_id=tx_id,
        decision_id=decision_id,
        trade_plan_id=plan_id_s,
        symbol=sym,
        at=filled_at or _iso_now(),
        venue="PAPER",
    )


def mapping_to_input(mapping: LifecycleFillMapping) -> LifecycleEventInput:
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
        venue=mapping.venue,
        fees=0,
    )


async def append_lifecycle_from_confirm_fill(
    append: AppendLifecycleEvent | None,
    *,
    action: str,
    account_id: str,
    instrument_id: str,
    quantity: float,
    price: float,
    tx_id: str,
    trade: Any,
    trade_plan_dict: dict[str, Any] | None = None,
    decision_id: str | None = None,
    symbol: str | None = None,
    open_position_id: str | None = None,
    filled_at: str | None = None,
) -> dict[str, Any]:
    """Fail-soft sidecar append. Never rolls back cash/PositionSync."""
    if append is None:
        return {"status": "skipped", "reason": "lifecycle_append_not_wired"}
    mapping = build_lifecycle_fill_mapping(
        action=action,
        account_id=account_id,
        instrument_id=instrument_id,
        quantity=quantity,
        price=price,
        tx_id=tx_id,
        trade=trade,
        trade_plan_dict=trade_plan_dict,
        decision_id=decision_id,
        symbol=symbol,
        open_position_id=open_position_id,
        filled_at=filled_at,
    )
    if mapping is None:
        return {"status": "skipped", "reason": "unmapped_action_or_missing_ids"}

    try:
        # Inherit identity envelope from open event when Confirm exit/reduce
        # omits plan/decision/symbol (normalize defaults would otherwise mismatch).
        existing = await append.store.list_by_position(mapping.position_id)
        if existing:
            anchor = existing[0]
            mapping = LifecycleFillMapping(
                kind=mapping.kind,
                position_id=mapping.position_id,
                account_id=mapping.account_id or (anchor.account_id or ""),
                instrument_id=mapping.instrument_id
                or (anchor.instrument_id or ""),
                quantity=mapping.quantity,
                price=mapping.price,
                fill_id=mapping.fill_id,
                event_id=mapping.event_id,
                decision_id=mapping.decision_id or anchor.decision_id,
                trade_plan_id=mapping.trade_plan_id or anchor.trade_plan_id,
                symbol=mapping.symbol or anchor.symbol,
                at=mapping.at,
                venue=mapping.venue,
            )

        # Full exit from open/t1: domain allows POSITION_CLOSED directly (V1.89).
        result = await append.execute(mapping_to_input(mapping))
        if not result.ok:
            code = result.error.code if result.error else "append_failed"
            logger.warning(
                "lifecycle_from_fill append failed action=%s kind=%s code=%s",
                action,
                mapping.kind,
                code,
            )
            return {
                "status": "error",
                "reason": code,
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
        logger.warning("lifecycle_from_fill exception: %s", exc)
        return {"status": "error", "reason": str(exc)}


__all__ = [
    "LifecycleFillMapping",
    "append_lifecycle_from_confirm_fill",
    "build_lifecycle_fill_mapping",
    "map_confirm_fill_action",
    "mapping_to_input",
    "resolve_lifecycle_position_id",
]
