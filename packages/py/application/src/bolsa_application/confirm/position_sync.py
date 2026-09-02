"""DEX-4 — PositionSync coordinator (post-fill / exit / protect persist)."""

from __future__ import annotations

from typing import Any

from bolsa_application.confirm.actions import is_closing_action, is_opening_action
from bolsa_application.lifecycle_from_fill import append_lifecycle_from_confirm_fill
from bolsa_application.persist_position_from_exit import (
    PersistPositionFromExitInput,
    row_position_id,
)
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFillInput,
    ledger_position_id_from_trade,
)


class PositionSyncCoordinator:
    """Persist PositionState tras fill/exit (OI-1). Protect via ExitGate.

    V1.89: after successful PositionState persist, fail-soft append to lifecycle
    sidecar (never merges cash ledger).
    """

    def __init__(
        self,
        *,
        position_from_fill: Any | None = None,
        position_from_exit: Any | None = None,
        lifecycle_append: Any | None = None,
    ) -> None:
        self._position_from_fill = position_from_fill
        self._position_from_exit = position_from_exit
        self._lifecycle_append = lifecycle_append

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
        open_position_id: str | None = None
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
                    open_position_id = ledger_position_id_from_trade(
                        trade, intent.instrument_id
                    )
            if self._position_from_exit is not None and is_closing_action(rec.action):
                if isinstance(tx_id, str) and tx_id.strip():
                    filled_at = getattr(
                        getattr(trade, "transaction", None),
                        "executed_at",
                        None,
                    )
                    # Resolve position id before exit may mark row closed.
                    existing = None
                    getter = getattr(self._position_from_exit, "get_open", None)
                    if getter is not None:
                        existing = await getter(account_id, intent.instrument_id)
                    open_position_id = row_position_id(existing) if existing else None
                    await self._position_from_exit.persist(
                        PersistPositionFromExitInput(
                            account_id=account_id,
                            instrument_id=intent.instrument_id,
                            fill_quantity=float(intent.quantity),
                            fill_price=price,
                            exit_transaction_id=tx_id,
                            filled_at=str(filled_at) if filled_at else None,
                            mark_target1_achieved=rec.action == "reduce",
                            mark_target2_achieved=rec.action == "exit_hint",
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            position_persist = {"status": "error", "reason": str(exc)}
            return position_persist

        if (
            position_persist.get("status") == "applied"
            and isinstance(tx_id, str)
            and tx_id.strip()
        ):
            filled_at = getattr(
                getattr(trade, "transaction", None),
                "executed_at",
                None,
            )
            lifecycle = await append_lifecycle_from_confirm_fill(
                self._lifecycle_append,
                action=rec.action,
                account_id=account_id,
                instrument_id=intent.instrument_id,
                quantity=float(intent.quantity),
                price=price,
                tx_id=tx_id,
                trade=trade,
                trade_plan_dict=trade_plan_dict,
                decision_id=getattr(rec, "decision_id", None),
                open_position_id=open_position_id,
                filled_at=str(filled_at) if filled_at else None,
            )
            position_persist["lifecycle"] = lifecycle
        return position_persist
