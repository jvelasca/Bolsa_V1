"""DEX-4 — PositionSync coordinator (post-fill / exit / protect persist)."""

from __future__ import annotations

from typing import Any

from bolsa_application.confirm.actions import is_closing_action, is_opening_action
from bolsa_application.lifecycle_from_fill import (
    append_lifecycle_from_confirm_fill,
    build_lifecycle_fill_mapping,
    map_confirm_fill_action,
)
from bolsa_application.lifecycle_outbox import drain_lifecycle_outbox
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

    V1.90: enqueue lifecycle_outbox (same session) then drain best-effort so a
    crash between PositionSync and AppendLifecycleEvent is recoverable.
    """

    def __init__(
        self,
        *,
        position_from_fill: Any | None = None,
        position_from_exit: Any | None = None,
        lifecycle_append: Any | None = None,
        lifecycle_outbox: Any | None = None,
    ) -> None:
        self._position_from_fill = position_from_fill
        self._position_from_exit = position_from_exit
        self._lifecycle_append = lifecycle_append
        self._lifecycle_outbox = lifecycle_outbox

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
            filled_at_s = str(filled_at) if filled_at else None
            lifecycle = await self._enqueue_or_append_lifecycle(
                rec=rec,
                intent=intent,
                price=price,
                account_id=account_id,
                trade=trade,
                trade_plan_dict=trade_plan_dict,
                tx_id=tx_id,
                open_position_id=open_position_id,
                filled_at=filled_at_s,
            )
            position_persist["lifecycle"] = lifecycle
        return position_persist

    async def _enqueue_or_append_lifecycle(
        self,
        *,
        rec: Any,
        intent: Any,
        price: float,
        account_id: str,
        trade: Any,
        trade_plan_dict: dict[str, Any] | None,
        tx_id: str,
        open_position_id: str | None,
        filled_at: str | None,
    ) -> dict[str, Any]:
        mapped = map_confirm_fill_action(rec.action)
        if mapped == "reject_short":
            return {"status": "skipped", "reason": "recommend_short_rejected"}
        if mapped == "skip":
            return {"status": "skipped", "reason": "unmapped_action_or_missing_ids"}

        # Prefer outbox path when wired (V1.90).
        if self._lifecycle_outbox is not None:
            mapping = build_lifecycle_fill_mapping(
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
                filled_at=filled_at,
            )
            # Even without mapping (missing timestamp), enqueue so drain can retry
            # after lookup — but only if we have a position id.
            position_id = (
                mapping.position_id
                if mapping is not None
                else (open_position_id or ledger_position_id_from_trade(
                    trade, intent.instrument_id
                ))
            )
            if not position_id:
                return {"status": "skipped", "reason": "unmapped_action_or_missing_ids"}

            kind = mapping.kind if mapping is not None else "POSITION_OPENED"
            ledger_positions = []
            summary = getattr(trade, "summary", None)
            for pos in getattr(summary, "positions", None) or []:
                ledger_positions.append(
                    {
                        "id": getattr(pos, "id", None),
                        "instrument_id": getattr(pos, "instrument_id", None),
                    }
                )
            payload: dict[str, Any] = {
                "action": rec.action,
                "instrument_id": intent.instrument_id,
                "quantity": float(intent.quantity),
                "price": price,
                "filled_at": filled_at or (mapping.at if mapping else None),
                "decision_id": getattr(rec, "decision_id", None),
                "trade_plan_dict": trade_plan_dict,
                "ledger_positions": ledger_positions,
            }
            try:
                await self._lifecycle_outbox.enqueue(
                    position_id=position_id,
                    account_id=account_id,
                    transaction_id=tx_id,
                    kind=kind,
                    payload=payload,
                )
            except Exception as exc:  # noqa: BLE001
                return {"status": "error", "reason": f"outbox_enqueue:{exc}"}

            drain = await drain_lifecycle_outbox(
                self._lifecycle_outbox,
                self._lifecycle_append,
            )
            return {
                "status": "applied" if drain.get("applied") else "pending",
                "outbox": drain,
                "positionId": position_id,
                "eventId": tx_id,
            }

        # Legacy direct append (tests without outbox).
        return await append_lifecycle_from_confirm_fill(
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
            filled_at=filled_at,
        )
