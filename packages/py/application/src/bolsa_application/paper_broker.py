"""PaperBroker — venue PAPER alrededor de execute_trade (ADR-034 · ADR-035 OR-3).

CREATED → SUBMITTED → ledger fill → FILLED. Excepción post-send → UNKNOWN.
PaperBroker = venue paper usado por PaperBrokerAdapter.
≠ IBrokerAdapter live · ≠ thaw PAPER_D_EXECUTE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.cognitive.paper_broker import (
    PaperBrokerFillStatus,
    PaperBrokerReceipt,
    build_paper_broker_receipt,
)
from bolsa_analytics.cognitive.paper_order import (
    PaperOrder,
    PaperOrderSide,
    apply_paper_order_fill,
    build_paper_order,
    transition_paper_order,
)
from bolsa_application.persist_position_from_fill import open_transaction_id_from_trade

PaperBrokerSubmitStatus = Literal["executed", "unknown"]


@dataclass(frozen=True, slots=True)
class PaperBrokerSubmitResult:
    """Resultado de submit paper: orden + trade + honestidad."""

    paper_order: PaperOrder
    trade: Any | None
    status: PaperBrokerSubmitStatus
    reason: str | None
    transaction_id: str | None

    def receipt(self) -> PaperBrokerReceipt:
        fill: PaperBrokerFillStatus = self.status
        return build_paper_broker_receipt(
            paper_order=self.paper_order,
            fill_status=fill,
        )


class PaperBroker:
    """Capa paper antes de BrokerAdapter. Solo venue PAPER."""

    def __init__(self, execute_trade: Any) -> None:
        self._execute_trade = execute_trade

    async def submit(
        self,
        *,
        instrument_id: str,
        side: PaperOrderSide,
        quantity: float,
        price: float,
        account_id: str,
        idempotency_key: str,
        order_id: str | None = None,
        intent_id: str | None = None,
    ) -> PaperBrokerSubmitResult:
        paper = transition_paper_order(
            build_paper_order(
                instrument_id=instrument_id,
                side=side,
                quantity=quantity,
                order_id=order_id,
                intent_id=intent_id,
            ),
            "SUBMITTED",
        )
        try:
            trade = await self._execute_trade.execute(
                instrument_id=instrument_id,
                trade_type=side,
                quantity=quantity,
                price=price,
                account_id=account_id,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:  # noqa: BLE001 — OI-3/OR-3: UNKNOWN ≠ ERROR
            return PaperBrokerSubmitResult(
                paper_order=transition_paper_order(paper, "UNKNOWN"),
                trade=None,
                status="unknown",
                reason=str(exc),
                transaction_id=None,
            )
        tx_id = open_transaction_id_from_trade(trade)
        filled = apply_paper_order_fill(
            paper,
            transaction_id=tx_id,
        )
        return PaperBrokerSubmitResult(
            paper_order=filled,
            trade=trade,
            status="executed",
            reason=None,
            transaction_id=tx_id,
        )
