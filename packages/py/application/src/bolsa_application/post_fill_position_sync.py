"""OI-1 — sincronizar PositionState tras fill ledger (ADR-034).

Un post-fill, varios orígenes: plan TRIGGERED (IA) o snapshot manual auditado.
Clasifica por fila OPEN + lado del fill; no por el diálogo que originó la orden.
"""

from __future__ import annotations

from typing import Any, Literal

from bolsa_application.persist_position_from_exit import (
    PersistPositionFromExit,
    PersistPositionFromExitInput,
    row_position_state,
)
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFill,
    PersistPositionFromFillInput,
    ledger_position_id_from_trade,
    open_transaction_id_from_trade,
)

HUMAN_MANUAL_OVERRIDE = "human_manual"
PositionFillKind = Literal["opening_ai", "opening_manual", "closing", "noop"]


def trade_side_closes_position(direction: str, side: str) -> bool:
    d = direction.lower()
    s = side.lower()
    if d == "long" and s == "sell":
        return True
    if d == "short" and s == "buy":
        return True
    return False


def trade_side_opens_long(side: str) -> bool:
    return side.lower() == "buy"


def build_human_manual_trade_plan_snapshot(
    *,
    instrument_id: str,
    open_transaction_id: str,
    fill_price: float,
    direction: str = "long",
) -> dict[str, Any]:
    return {
        "decisionId": f"manual-{open_transaction_id}",
        "instrumentId": instrument_id,
        "direction": direction,
        "status": "HUMAN_MANUAL",
        "origin": "HUMAN_MANUAL",
        "entry": fill_price,
    }


def _direction_from_open_row(open_row: Any) -> str:
    state = row_position_state(open_row)
    if state is None:
        return "long"
    raw = state.get("direction")
    return str(raw).lower() if isinstance(raw, str) and raw.strip() else "long"


def classify_ledger_fill(
    *,
    side: str,
    open_row: Any | None,
    trade_plan_snapshot: dict[str, Any] | None = None,
) -> PositionFillKind:
    normalized_side = side.lower()
    if open_row is not None:
        direction = _direction_from_open_row(open_row)
        if trade_side_closes_position(direction, normalized_side):
            return "closing"
        return "noop"

    if not trade_side_opens_long(normalized_side):
        return "noop"

    plan = trade_plan_snapshot if isinstance(trade_plan_snapshot, dict) else None
    if plan is not None and plan.get("status") == "TRIGGERED":
        return "opening_ai"
    return "opening_manual"


async def sync_position_after_ledger_fill(
    *,
    account_id: str,
    instrument_id: str,
    side: str,
    fill_price: float,
    fill_quantity: float,
    trade: Any,
    open_transaction_id: str | None = None,
    filled_at: str | None = None,
    position_from_fill: PersistPositionFromFill | None = None,
    position_from_exit: PersistPositionFromExit | None = None,
    trade_plan_snapshot: dict[str, Any] | None = None,
) -> Any | None:
    """Actualiza PositionState tras un fill paper. Idempotente vía persist layers."""
    acc = account_id.strip() if account_id else ""
    inst = instrument_id.strip() if instrument_id else ""
    if not acc or not inst:
        return None

    tx_id = (open_transaction_id or open_transaction_id_from_trade(trade) or "").strip()
    if not tx_id:
        return None

    open_row: Any | None = None
    if position_from_exit is not None:
        open_row = await position_from_exit.get_open(acc, inst)
    elif position_from_fill is not None:
        open_row = await position_from_fill.get_open(acc, inst)

    kind = classify_ledger_fill(
        side=side,
        open_row=open_row,
        trade_plan_snapshot=trade_plan_snapshot,
    )
    if kind == "noop":
        return None

    if kind == "closing":
        if position_from_exit is None:
            return None
        return await position_from_exit.persist(
            PersistPositionFromExitInput(
                account_id=acc,
                instrument_id=inst,
                fill_quantity=float(fill_quantity),
                fill_price=float(fill_price),
                exit_transaction_id=tx_id,
                filled_at=filled_at,
            )
        )

    if position_from_fill is None:
        return None

    plan = trade_plan_snapshot if isinstance(trade_plan_snapshot, dict) else None
    override_reason: str | None = None
    if kind == "opening_manual":
        plan = build_human_manual_trade_plan_snapshot(
            instrument_id=inst,
            open_transaction_id=tx_id,
            fill_price=float(fill_price),
        )
        override_reason = HUMAN_MANUAL_OVERRIDE

    return await position_from_fill.persist(
        PersistPositionFromFillInput(
            account_id=acc,
            trade_plan=plan,
            fill_price=float(fill_price),
            fill_quantity=float(fill_quantity),
            filled_at=filled_at,
            open_transaction_id=tx_id,
            ledger_position_id=ledger_position_id_from_trade(trade, inst),
            override_reason=override_reason,
        )
    )
