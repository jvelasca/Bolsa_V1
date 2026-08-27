"""DEX-4 — PositionSync coordinator (post-fill / exit / protect persist)."""

from __future__ import annotations

from typing import Any

from bolsa_application.confirm.actions import is_closing_action, is_opening_action
from bolsa_application.persist_position_from_exit import PersistPositionFromExitInput
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFillInput,
    ledger_position_id_from_trade,
)


class PositionSyncCoordinator:
    """Persist PositionState tras fill/exit (OI-1). Protect via ExitGate."""

    def __init__(
        self,
        *,
        position_from_fill: Any | None = None,
        position_from_exit: Any | None = None,
    ) -> None:
        self._position_from_fill = position_from_fill
        self._position_from_exit = position_from_exit

    async def sync_after_fill(
        self,
        *,
        rec: Any,
        intent: Any,
        price: float,
        account_id: str,
        trade: Any,
        trade_plan_dict: dict[str, Any] | None,
        tx_id: Any,
    ) -> dict[str, Any]:
        position_persist: dict[str, Any] = {"status": "applied"}
        try:
            if self._position_from_fill is not None and is_opening_action(rec.action):
                if isinstance(tx_id, str) and tx_id.strip():
                    filled_at = getattr(
                        getattr(trade, "transaction", None),
                        "executed_at",
                        None,
                    )
                    await self._position_from_fill.persist(
                        PersistPositionFromFillInput(
                            account_id=account_id,
                            trade_plan=trade_plan_dict
                            if isinstance(trade_plan_dict, dict)
                            else None,
                            fill_price=price,
                            fill_quantity=float(intent.quantity),
                            filled_at=str(filled_at) if filled_at else None,
                            open_transaction_id=tx_id,
                            ledger_position_id=ledger_position_id_from_trade(
                                trade, intent.instrument_id
                            ),
                        )
                    )
            if self._position_from_exit is not None and is_closing_action(rec.action):
                if isinstance(tx_id, str) and tx_id.strip():
                    filled_at = getattr(
                        getattr(trade, "transaction", None),
                        "executed_at",
                        None,
                    )
                    await self._position_from_exit.persist(
                        PersistPositionFromExitInput(
                            account_id=account_id,
                            instrument_id=intent.instrument_id,
                            fill_quantity=float(intent.quantity),
                            fill_price=price,
                            exit_transaction_id=tx_id,
                            filled_at=str(filled_at) if filled_at else None,
                            mark_target1_achieved=rec.action == "reduce",
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            position_persist = {"status": "error", "reason": str(exc)}
        return position_persist
