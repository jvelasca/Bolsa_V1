"""LiveOrder — XL-3 LIVE execution state machine (domain only).

≠ PaperOrder (venue PAPER) · ≠ XL-2 sync filled→ledger slice (cerrado).
UNKNOWN is first-class: timeout/lost response → UNKNOWN · NO automatic re-POST.
PARTIAL: filledQuantity + remainingQuantity · execute_trade with full qty FORBIDDEN.
query_broker is the only path out of UNKNOWN (real poll PARKED; mock in tests).

≠ thaw · ≠ PAPER_D_EXECUTE · ≠ LIVE_EXECUTION_UNLOCKED.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LiveOrderStatus = Literal[
    "AUTHORIZED",
    "SUBMITTING",
    "SUBMITTED",
    "WORKING",
    "PARTIAL",
    "FILLED",
    "REJECTED",
    "CANCELLED",
    "UNKNOWN",
]

LiveOrderSide = Literal["buy", "sell"]
LiveOrderVenue = Literal["LIVE"]

LIVE_ORDER_KEY = "liveOrder"

# Terminales: resultado cerrado (FILLED/REJECTED/CANCELLED). Una fila aquí ya no
# está in-flight: no admite más transiciones ni cuenta como "open".
_TERMINAL: frozenset[LiveOrderStatus] = frozenset({"FILLED", "REJECTED", "CANCELLED"})

# UNKNOWN → SUBMITTING (re-POST) is intentionally ABSENT.
ALLOWED_LIVE_ORDER_TRANSITIONS: dict[LiveOrderStatus, frozenset[LiveOrderStatus]] = {
    "AUTHORIZED": frozenset({"SUBMITTING", "REJECTED", "CANCELLED"}),
    "SUBMITTING": frozenset({"REJECTED", "UNKNOWN", "SUBMITTED"}),
    "SUBMITTED": frozenset({"WORKING", "UNKNOWN", "CANCELLED", "REJECTED"}),
    "WORKING": frozenset({"PARTIAL", "FILLED", "UNKNOWN", "CANCELLED", "REJECTED"}),
    "PARTIAL": frozenset({"FILLED", "UNKNOWN", "CANCELLED"}),
    "FILLED": frozenset(),
    "REJECTED": frozenset(),
    "CANCELLED": frozenset(),
    # Resolve UNKNOWN only via broker query (not re-POST).
    "UNKNOWN": frozenset({"WORKING", "REJECTED", "FILLED", "PARTIAL", "CANCELLED"}),
}

# "open" = no-terminal: la orden sigue viva / en curso / en riesgo. Complemento
# de ``_TERMINAL`` sobre las claves del grafo (que cubren todo el literal), para
# que listar/cancelar no repita strings mágicos y derive de la misma semántica
# terminal del grafo.
NON_TERMINAL_LIVE_STATUSES: frozenset[LiveOrderStatus] = frozenset(
    set(ALLOWED_LIVE_ORDER_TRANSITIONS) - _TERMINAL
)


@dataclass(frozen=True, slots=True)
class LiveOrder:
    order_id: str
    status: LiveOrderStatus
    venue: LiveOrderVenue
    instrument_id: str
    side: LiveOrderSide
    quantity: float
    filled_quantity: float
    remaining_quantity: float
    venue_order_id: str | None
    intent_id: str | None
    financial_apply_count: int
    account_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "orderId": self.order_id,
            "status": self.status,
            "venue": self.venue,
            "instrumentId": self.instrument_id,
            "side": self.side,
            "quantity": self.quantity,
            "filledQuantity": self.filled_quantity,
            "remainingQuantity": self.remaining_quantity,
            "venueOrderId": self.venue_order_id,
            "intentId": self.intent_id,
            "financialApplyCount": self.financial_apply_count,
            "accountId": self.account_id,
        }


def build_live_order(
    *,
    order_id: str,
    instrument_id: str,
    side: LiveOrderSide,
    quantity: float,
    intent_id: str | None = None,
    status: LiveOrderStatus = "AUTHORIZED",
    account_id: str | None = None,
) -> LiveOrder:
    qty = float(quantity)
    return LiveOrder(
        order_id=order_id,
        status=status,
        venue="LIVE",
        instrument_id=instrument_id,
        side=side,
        quantity=qty,
        filled_quantity=0.0,
        remaining_quantity=qty,
        venue_order_id=None,
        intent_id=intent_id,
        financial_apply_count=0,
        account_id=account_id,
    )


def can_transition_live_order(current: LiveOrderStatus, nxt: LiveOrderStatus) -> bool:
    if current in _TERMINAL and nxt != current:
        return False
    return nxt in ALLOWED_LIVE_ORDER_TRANSITIONS.get(current, frozenset())


class LiveOrderTransitionError(ValueError):
    """Transición ilegal del grafo LIVE (p.ej. UNKNOWN → SUBMITTING)."""


def transition_live_order(
    order: LiveOrder,
    nxt: LiveOrderStatus,
    *,
    filled_quantity: float | None = None,
    venue_order_id: str | None = None,
    apply_financial: bool = False,
) -> LiveOrder:
    """Aplica transición. apply_financial solo en FILLED (idempotente)."""
    if not can_transition_live_order(order.status, nxt):
        raise LiveOrderTransitionError(f"live_order forbidden: {order.status} → {nxt}")

    filled = order.filled_quantity
    remaining = order.remaining_quantity
    if filled_quantity is not None:
        filled = float(filled_quantity)
        if filled < 0 or filled > order.quantity + 1e-9:
            raise LiveOrderTransitionError("filled_quantity out of range")
        remaining = max(0.0, order.quantity - filled)

    if nxt == "PARTIAL" and filled <= 0:
        raise LiveOrderTransitionError("PARTIAL requires filled_quantity > 0")
    if nxt == "PARTIAL" and remaining <= 0:
        raise LiveOrderTransitionError("PARTIAL requires remaining_quantity > 0")
    if nxt == "FILLED":
        filled = order.quantity if filled_quantity is None else filled
        remaining = 0.0

    apply_count = order.financial_apply_count
    if apply_financial:
        if nxt != "FILLED":
            raise LiveOrderTransitionError("financial apply only allowed on FILLED")
        # Duplicate FILLED events: only one financial effect.
        if apply_count >= 1:
            apply_count = 1
        else:
            apply_count = 1

    return LiveOrder(
        order_id=order.order_id,
        status=nxt,
        venue="LIVE",
        instrument_id=order.instrument_id,
        side=order.side,
        quantity=order.quantity,
        filled_quantity=filled,
        remaining_quantity=remaining,
        venue_order_id=venue_order_id if venue_order_id is not None else order.venue_order_id,
        intent_id=order.intent_id,
        financial_apply_count=apply_count,
        account_id=order.account_id,
    )


def forbid_execute_trade_for_partial(order: LiveOrder) -> None:
    """PARKED: Partial → PositionState/ledger. Never execute_trade with full qty."""
    if order.status == "PARTIAL":
        raise LiveOrderTransitionError(
            "execute_trade forbidden on PARTIAL · use filled_quantity only (PARKED)"
        )


def forbid_repost_from_unknown(order: LiveOrder) -> None:
    """UNKNOWN must not re-POST; only query_broker may resolve."""
    if order.status == "UNKNOWN":
        raise LiveOrderTransitionError("UNKNOWN forbids re-POST · query_broker only")
