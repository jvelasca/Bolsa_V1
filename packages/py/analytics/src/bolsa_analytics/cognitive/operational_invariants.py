"""DEX-5 — predicados puros de invariantes operacionales (ADR-035).

Sin side effects. Usados por la property suite spine. ≠ OperationalPolicy.
"""

from __future__ import annotations

from typing import Literal

from bolsa_analytics.cognitive.paper_order import PaperOrder, PaperOrderStatus

_TERMINAL: frozenset[PaperOrderStatus] = frozenset(
    {"FILLED", "REJECTED", "CANCELLED", "EXPIRED"}
)

_HARD_TERMINAL_NO_FILL: frozenset[PaperOrderStatus] = frozenset(
    {"REJECTED", "CANCELLED", "EXPIRED"}
)


def qty_non_negative(quantity: float) -> bool:
    """qty ≥ 0 (NaN → False)."""
    return quantity == quantity and quantity >= 0


def qty_positive(quantity: float) -> bool:
    """qty > 0 (nacimiento orden / fill operativo)."""
    return quantity == quantity and quantity > 0


def filled_le_ordered(order: PaperOrder) -> bool:
    """filled ≤ ordered cuando hay fill; None OK en abiertos."""
    if order.quantity != order.quantity or order.quantity < 0:
        return False
    filled = order.filled_quantity
    if filled is None:
        return True
    if filled != filled or filled < 0:
        return False
    return filled <= float(order.quantity) + 1e-12


def is_terminal_status(status: PaperOrderStatus) -> bool:
    return status in _TERMINAL


def is_hard_terminal_no_fill(status: PaperOrderStatus) -> bool:
    """REJECTED/CANCELLED/EXPIRED: no re-ejecuta fill."""
    return status in _HARD_TERMINAL_NO_FILL


def protect_stop_worsens_exposure(
    direction: Literal["long", "short"],
    current_stop: float | None,
    next_stop: float,
) -> bool:
    """True si el nuevo stop empeora (↑ exposición) vs current.

    long: stop más bajo empeora. short: stop más alto empeora.
    Delegates to domain ``stop_worsens`` (V1.98 single house).
    """
    from bolsa_domain.lifecycle import stop_worsens

    if next_stop != next_stop or next_stop <= 0:
        return False
    return stop_worsens(direction, current_stop, next_stop)


def risk_distance(entry: float, stop: float) -> float:
    """Distancia geométrica |entry − stop|."""
    return abs(float(entry) - float(stop))


def adverse_exposure(
    direction: Literal["long", "short"],
    entry: float,
    stop: float,
) -> float:
    """Exposición adversa (riesgo de pérdida vs entry).

    long: max(0, entry − stop). short: max(0, stop − entry).
    Stop en BE o mejor → 0 (PROTECTED).
    """
    if direction == "long":
        return max(0.0, float(entry) - float(stop))
    return max(0.0, float(stop) - float(entry))


def closed_remaining_zero(*, status: str, remaining: float) -> bool:
    """INV-02: CLOSED ⇒ remaining_quantity == 0 (qty de nacimiento se conserva)."""
    if (status or "").upper() != "CLOSED":
        return True
    return abs(float(remaining)) < 1e-12


def executed_leg_has_fill(status: str | None, fill_id: str | None) -> bool:
    """INV-03/04: executed ⇒ fill id presente."""
    if status != "executed":
        return True
    return isinstance(fill_id, str) and bool(fill_id.strip())


def mapping_unchanged(before: object, after: object) -> bool:
    """INV-08/09/10: snapshot de identidad no muta."""
    return before == after
