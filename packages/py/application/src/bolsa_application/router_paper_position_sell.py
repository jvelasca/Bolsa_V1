"""V1.45 — adapter PaperPositionSellPort vía ExecutionRouter (exit/reduce hits)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from bolsa_application.execute_position_policy_auto import PaperPositionSellResult
from bolsa_application.execution_router import ExecutionRouter
from bolsa_application.paper_auto_http_gate import PaperAutoEnvBlockedError
from bolsa_application.paper_d_propose import paper_d_execute_allowed


class RouterPaperPositionSell:
    """Construye hit exit/reduce y delega en ExecutionRouter.execute."""

    def __init__(
        self,
        router: ExecutionRouter,
        *,
        execution_policy_id: str,
        symbol: str | None = None,
    ) -> None:
        self._router = router
        self._policy_id = execution_policy_id
        self._symbol = symbol

    async def sell(
        self,
        *,
        account_id: str,
        instrument_id: str,
        quantity: float,
        price: float,
        full_exit: bool,
    ) -> PaperPositionSellResult:
        _ = account_id
        if not paper_d_execute_allowed():
            return PaperPositionSellResult(
                status="blocked",
                reason="paper_auto_env_blocked",
            )
        kind = "exit" if full_exit else "reduce"
        sig_id = f"pos-auto-{uuid4().hex[:12]}"
        hit: dict[str, Any] = {
            "instrumentId": instrument_id,
            "symbol": self._symbol or instrument_id,
            "quantity": float(quantity) if not full_exit else None,
            "signal": {
                "id": sig_id,
                "instrumentId": instrument_id,
                "timestamp": "",
                "kind": kind if kind == "exit" else "exit",
                # Always use exit kind for SignalEventV1 Literal; qty drives partial.
                "strategyDefinitionId": "position-policy-auto",
                "strategyVersion": 1,
                "barIndex": 0,
                "price": float(price),
                "quantity": float(quantity) if not full_exit else None,
            },
        }
        if not full_exit:
            hit["quantity"] = float(quantity)
            hit["signal"]["quantity"] = float(quantity)
        else:
            hit.pop("quantity", None)
            hit["signal"].pop("quantity", None)

        try:
            batch = await self._router.execute(self._policy_id, [hit])
        except PaperAutoEnvBlockedError:
            return PaperPositionSellResult(
                status="blocked",
                reason="paper_auto_env_blocked",
            )
        if not batch.actions:
            return PaperPositionSellResult(status="skipped", reason="no_actions")
        action = batch.actions[0]
        if action.status == "trade_executed":
            return PaperPositionSellResult(
                status="trade_executed",
                fill_quantity=float(quantity),
                fill_price=float(price),
                transaction_id=action.transaction_id,
            )
        return PaperPositionSellResult(
            status="skipped",
            reason=action.reason or action.status,
        )
