"""PaperOrder — ciclo paper CREATED→FILLED (ADR-034 OI-4).

CREATED ≠ FILLED. Orden creada no es fill.
≠ OrderIntent ≠ ExecutionPlan ≠ ExecutionRecord ≠ broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

PaperOrderStatus = Literal["CREATED", "FILLED"]
PaperOrderSide = Literal["buy", "sell"]
PaperOrderVenue = Literal["PAPER"]

PAPER_ORDER_KEY = "paperOrder"


def _non_empty(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


@dataclass(frozen=True, slots=True)
class PaperOrder:
    """Orden paper. CREATED = existe, fill no confirmado. FILLED = fill registrado."""

    order_id: str
    status: PaperOrderStatus
    venue: PaperOrderVenue
    instrument_id: str
    side: PaperOrderSide
    quantity: float
    transaction_id: str | None
    intent_id: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "orderId": self.order_id,
            "status": self.status,
            "venue": self.venue,
            "instrumentId": self.instrument_id,
            "side": self.side,
            "quantity": self.quantity,
            "transactionId": self.transaction_id,
            "intentId": self.intent_id,
        }


def build_paper_order(
    *,
    instrument_id: str,
    side: PaperOrderSide,
    quantity: float,
    order_id: str | None = None,
    intent_id: str | None = None,
) -> PaperOrder:
    """Nacimiento: siempre CREATED, venue PAPER, sin fill."""
    oid = _non_empty(order_id) or f"ORD-{uuid4().hex[:12]}"
    return PaperOrder(
        order_id=oid,
        status="CREATED",
        venue="PAPER",
        instrument_id=instrument_id.strip() if isinstance(instrument_id, str) else "",
        side=side,
        quantity=float(quantity),
        transaction_id=None,
        intent_id=_non_empty(intent_id),
    )


def apply_paper_order_fill(
    order: PaperOrder,
    *,
    transaction_id: str | None = None,
) -> PaperOrder:
    """CREATED→FILLED. FILLED es idempotente (primer fill gana). No revierte."""
    if order.status == "FILLED":
        return order
    return PaperOrder(
        order_id=order.order_id,
        status="FILLED",
        venue="PAPER",
        instrument_id=order.instrument_id,
        side=order.side,
        quantity=order.quantity,
        transaction_id=_non_empty(transaction_id),
        intent_id=order.intent_id,
    )


def paper_order_status_copy(status: PaperOrderStatus) -> str:
    """Copy de mesa: CREATED nunca se lee como cubierta."""
    if status == "FILLED":
        return "Orden cubierta (paper)"
    return "Orden creada — fill no confirmado"
