"""PaperOrder — ciclo paper CREATED→…→FILLED + ramas (ADR-034 OI-4 · ADR-035 OR-3).

CREATED ≠ FILLED. Orden creada no es fill.
OR-3 amplía el Literal; OI-4 nacimiento CREATED se conserva.
≠ OrderIntent ≠ ExecutionPlan ≠ ExecutionRecord ≠ broker.
≠ DurableSubmitIntent (OR-2 fases recorded|venue_bound|filled).

OR-1 (ADR-035): ``order_id`` estable derivado de ``decision_id`` cuando se pasa
explícito (retry Confirm no inventa ``ORD-`` nuevo).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

PaperOrderStatus = Literal[
    "CREATED",
    "SUBMITTED",
    "ACK",
    "PARTIAL",
    "FILLED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
    "UNKNOWN",
]
PaperOrderSide = Literal["buy", "sell"]
PaperOrderVenue = Literal["PAPER"]

PAPER_ORDER_KEY = "paperOrder"

# Terminales duros: no salen.
_TERMINAL: frozenset[PaperOrderStatus] = frozenset(
    {"FILLED", "REJECTED", "CANCELLED", "EXPIRED"}
)

# Grafo OR-3. CREATED→FILLED directo = atajo paper OI-4 (D3).
ALLOWED_TRANSITIONS: dict[PaperOrderStatus, frozenset[PaperOrderStatus]] = {
    "CREATED": frozenset(
        {
            "SUBMITTED",
            "ACK",
            "PARTIAL",
            "FILLED",
            "REJECTED",
            "CANCELLED",
            "EXPIRED",
            "UNKNOWN",
        }
    ),
    "SUBMITTED": frozenset(
        {
            "ACK",
            "PARTIAL",
            "FILLED",
            "REJECTED",
            "CANCELLED",
            "EXPIRED",
            "UNKNOWN",
        }
    ),
    "ACK": frozenset(
        {"PARTIAL", "FILLED", "REJECTED", "CANCELLED", "EXPIRED", "UNKNOWN"}
    ),
    "PARTIAL": frozenset({"FILLED", "CANCELLED", "EXPIRED", "UNKNOWN"}),
    "UNKNOWN": frozenset(
        {"ACK", "PARTIAL", "FILLED", "REJECTED", "CANCELLED", "EXPIRED"}
    ),
    "FILLED": frozenset(),
    "REJECTED": frozenset(),
    "CANCELLED": frozenset(),
    "EXPIRED": frozenset(),
}


def _non_empty(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def stable_order_id_from_decision(decision_id: str) -> str:
    """OR-1 — identidad de orden paper estable (retry = mismo ORD-)."""
    slug = "".join(c for c in decision_id.strip() if c.isalnum() or c in "-_")
    if not slug:
        digest = hashlib.sha256(decision_id.encode("utf-8")).hexdigest()[:12]
        return f"ORD-{digest}"
    return f"ORD-{slug[:48]}"


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
    filled_quantity: float | None = None

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
            "filledQuantity": self.filled_quantity,
        }


def build_paper_order(
    *,
    instrument_id: str,
    side: PaperOrderSide,
    quantity: float,
    order_id: str | None = None,
    intent_id: str | None = None,
) -> PaperOrder:
    """Nacimiento: siempre CREATED, venue PAPER, sin fill.

    DEX-5: ``quantity <= 0`` → fail-closed (qty ≥ 0 estricto en operativa).
    """
    qty = float(quantity)
    if qty <= 0 or qty != qty:
        raise ValueError("paper_order_qty_not_positive")
    oid = _non_empty(order_id) or f"ORD-{uuid4().hex[:12]}"
    return PaperOrder(
        order_id=oid,
        status="CREATED",
        venue="PAPER",
        instrument_id=instrument_id.strip() if isinstance(instrument_id, str) else "",
        side=side,
        quantity=qty,
        transaction_id=None,
        intent_id=_non_empty(intent_id),
        filled_quantity=None,
    )


def can_transition_paper_order(
    from_status: PaperOrderStatus,
    to_status: PaperOrderStatus,
) -> bool:
    """True si el grafo OR-3 permite from→to (incl. misma identidad no-op terminal)."""
    if from_status == to_status:
        return from_status in _TERMINAL or from_status == "UNKNOWN"
    return to_status in ALLOWED_TRANSITIONS.get(from_status, frozenset())


def transition_paper_order(
    order: PaperOrder,
    to_status: PaperOrderStatus,
    *,
    transaction_id: str | None = None,
    filled_quantity: float | None = None,
) -> PaperOrder:
    """Aplica transición legal. Ilegal → ValueError. Terminal idempotente (misma status)."""
    if order.status == to_status:
        if order.status in _TERMINAL or order.status == "UNKNOWN":
            return order
        raise ValueError(f"paper_order_noop_not_terminal:{order.status}")
    if not can_transition_paper_order(order.status, to_status):
        raise ValueError(f"paper_order_illegal_transition:{order.status}->{to_status}")

    next_filled = order.filled_quantity
    next_tx = order.transaction_id
    if to_status == "PARTIAL":
        qty = float(filled_quantity) if filled_quantity is not None else None
        if qty is None or qty <= 0 or qty >= float(order.quantity):
            raise ValueError("paper_order_partial_requires_qty")
        next_filled = qty
    elif to_status == "FILLED":
        next_tx = _non_empty(transaction_id) if transaction_id is not None else order.transaction_id
        next_filled = (
            float(filled_quantity)
            if filled_quantity is not None
            else float(order.quantity)
        )
        # DEX-5: filled ≤ ordered · filled ≥ 0
        if next_filled != next_filled or next_filled < 0 or next_filled > float(order.quantity):
            raise ValueError("paper_order_filled_gt_ordered")
    elif transaction_id is not None:
        next_tx = _non_empty(transaction_id)

    return PaperOrder(
        order_id=order.order_id,
        status=to_status,
        venue="PAPER",
        instrument_id=order.instrument_id,
        side=order.side,
        quantity=order.quantity,
        transaction_id=next_tx,
        intent_id=order.intent_id,
        filled_quantity=next_filled,
    )


def apply_paper_order_fill(
    order: PaperOrder,
    *,
    transaction_id: str | None = None,
) -> PaperOrder:
    """→ FILLED desde estado abierto. FILLED idempotente (primer fill gana). No revierte."""
    if order.status == "FILLED":
        return order
    if order.status in {"REJECTED", "CANCELLED", "EXPIRED"}:
        raise ValueError(f"paper_order_fill_from_terminal:{order.status}")
    return transition_paper_order(
        order,
        "FILLED",
        transaction_id=transaction_id,
        filled_quantity=float(order.quantity),
    )


def paper_order_status_copy(status: PaperOrderStatus) -> str:
    """Copy de mesa: CREATED nunca se lee como cubierta."""
    copies: dict[PaperOrderStatus, str] = {
        "CREATED": "Orden creada — fill no confirmado",
        "SUBMITTED": "Orden enviada — pendiente de ack",
        "ACK": "Orden aceptada por el venue — fill pendiente",
        "PARTIAL": "Orden parcialmente cubierta",
        "FILLED": "Orden cubierta (paper)",
        "REJECTED": "Orden rechazada",
        "CANCELLED": "Orden cancelada",
        "EXPIRED": "Orden expirada",
        "UNKNOWN": "Estado de orden desconocido — no asumir fill",
    }
    return copies[status]
