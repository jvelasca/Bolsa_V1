"""DEX-4 — Execution coordinator (OR-1 replay + adapter.submit)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.paper_order import (
    apply_paper_order_fill,
    build_paper_order,
    stable_order_id_from_decision,
)
from bolsa_application.persist_position_from_fill import open_transaction_id_from_trade


class ExecutionCoordinator:
    """Idempotent fill peek/replay + broker adapter submit mapping."""

    def __init__(
        self,
        *,
        execute_trade: Any | None = None,
        broker_adapter: Any | None = None,
        resolve_broker_adapter: Any | None = None,
    ) -> None:
        self._execute_trade = execute_trade
        self._broker_adapter = broker_adapter
        self._resolve_broker_adapter = resolve_broker_adapter

    @property
    def configured(self) -> bool:
        return self._broker_adapter is not None or self._execute_trade is not None

    async def find_existing_fill(
        self,
        *,
        account_id: str,
        idempotency_key: str,
    ) -> Any | None:
        if not idempotency_key or self._execute_trade is None:
            return None
        finder = getattr(self._execute_trade, "find_existing_by_idempotency", None)
        if finder is None:
            return None
        try:
            trade = await finder(
                account_id=account_id,
                idempotency_key=idempotency_key,
            )
        except Exception:  # noqa: BLE001
            return None
        if trade is None:
            return None
        tx_id = open_transaction_id_from_trade(trade)
        if not isinstance(tx_id, str) or not tx_id.strip():
            return None
        return trade

    def apply_idempotent_replay(
        self,
        *,
        result: dict[str, Any],
        intent: Any,
        contract_status: str,
        trade: Any,
        order_id: str,
    ) -> None:
        tx_id = open_transaction_id_from_trade(trade)
        paper = apply_paper_order_fill(
            build_paper_order(
                instrument_id=intent.instrument_id,
                side=intent.side,
                quantity=float(intent.quantity),
                order_id=order_id,
                intent_id=intent.intent_id,
            ),
            transaction_id=tx_id,
        )
        result["trade"] = {
            "status": "executed",
            "transactionId": tx_id,
            "idempotentReplay": True,
        }
        result["intent"] = {
            **intent.to_dict(),
            "status": "executed",
            "contract": contract_status,
        }
        result["paperOrder"] = paper.to_dict()
        result["positionPersist"] = {"status": "applied", "idempotentReplay": True}

    async def submit(
        self,
        *,
        account_id: str,
        intent: Any,
        price: float,
        idempotency_key: str,
    ) -> Any:
        if self._broker_adapter is not None:
            adapter = self._broker_adapter
        else:
            assert self._resolve_broker_adapter is not None
            adapter = await self._resolve_broker_adapter(account_id)
        return await adapter.submit(
            instrument_id=intent.instrument_id,
            side=intent.side,
            quantity=float(intent.quantity),
            price=price,
            account_id=account_id,
            idempotency_key=idempotency_key,
            order_id=stable_order_id_from_decision(idempotency_key),
            intent_id=intent.intent_id,
        )

    @staticmethod
    def map_adapter_receipt(
        *,
        result: dict[str, Any],
        intent: Any,
        contract_status: str,
        pb: Any,
    ) -> Any | None:
        """Apply adapter receipt to result. Returns trade object if executed fill."""
        result["brokerAdapter"] = pb.receipt().to_dict()
        if pb.paper_order is not None:
            result["paperOrder"] = pb.paper_order.to_dict()
        if pb.paper_receipt is not None:
            result["paperBroker"] = pb.paper_receipt.to_dict()
        if pb.status == "not_wired":
            result["trade"] = {
                "status": "skipped",
                "reason": pb.reason or "live_not_wired",
            }
            return None
        if pb.status == "rejected":
            result["trade"] = {
                "status": "skipped",
                "reason": pb.reason or "live_rejected",
            }
            return None
        if pb.status == "submitted":
            trade_payload: dict[str, Any] = {
                "status": "unknown",
                "reason": pb.reason or "live_submitted_no_fill",
            }
            if pb.venue_order_id:
                trade_payload["venueOrderId"] = pb.venue_order_id
            result["trade"] = trade_payload
            result["intent"] = {
                **intent.to_dict(),
                "status": "unknown",
                "contract": contract_status,
            }
            return None
        if pb.status == "unknown":
            unknown_payload: dict[str, Any] = {
                "status": "unknown",
                "reason": pb.reason,
            }
            if pb.venue_order_id:
                unknown_payload["venueOrderId"] = pb.venue_order_id
            result["trade"] = unknown_payload
            result["intent"] = {
                **intent.to_dict(),
                "status": "unknown",
                "contract": contract_status,
            }
            return None
        trade = pb.trade
        tx_id = pb.transaction_id
        result["trade"] = {
            "status": "executed",
            "transactionId": tx_id,
        }
        result["intent"] = {
            **intent.to_dict(),
            "status": "executed",
            "contract": contract_status,
        }
        return trade
