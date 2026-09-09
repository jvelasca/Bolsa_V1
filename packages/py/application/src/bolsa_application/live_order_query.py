"""LiveOrderQuery — XL-3 puerto query_broker (resolve UNKNOWN without re-POST).

Implementación real PARKED. Mock en tests.
≠ submit_order · ≠ execute_trade · ≠ thaw.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Protocol

from bolsa_analytics.cognitive.live_order import LiveOrderStatus

BrokerQueryOutcome = Literal[
    "working",
    "partial",
    "filled",
    "rejected",
    "cancelled",
    "unavailable",
]


_D6 = Decimal("0.000001")


def _to_decimal(value: object | None) -> Decimal | None:
    """Cuantifica a ``Decimal(6dp)`` (paridad NUMERIC(18,6) / máquina XL-3).

    Acepta float/str/int/Decimal: el boundary ya no debe arrastrar float hacia
    la reconciliación/dominio, pero un DTO wire (float) que sí entre aquí se
    cuantifica sin perder exactitud mas alla del tipo de origen.
    """
    if value is None:
        return None
    try:
        q = Decimal(str(value))
    except (ValueError, TypeError):
        return None
    if q.is_nan():
        return None
    if q < 0:
        q = Decimal("0")
    return q.quantize(_D6, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class BrokerOrderQueryResult:
    outcome: BrokerQueryOutcome
    venue_order_id: str | None
    filled_quantity: Decimal | None
    remaining_quantity: Decimal | None
    reason: str | None = None
    # V2.19 (P2-01) — identidad financiera del fill + precio de materialización.
    # Opcionales y fail-closed: si el bridge del recovery no los reporta (p.ej.
    # un fill sin fill_seq constatable o sin precio de ejecución), NO materializar
    # dinero (fsm_only intacto, firewall H4/H6: nunca fabricar un precio del fill
    # que el broker no acreditó). ``fill_seq`` completa la identidad financiera
    # ``execution_id = venue_order_id + fill_seq``.
    fill_seq: int | None = None
    fill_price: Decimal | None = None

    def __post_init__(self) -> None:
        # mantiene Decimal(6dp) en el dominio; acepta float wire de tests/DTO.
        object.__setattr__(self, "filled_quantity", _to_decimal(self.filled_quantity))
        object.__setattr__(self, "remaining_quantity", _to_decimal(self.remaining_quantity))
        object.__setattr__(self, "fill_price", _to_decimal(self.fill_price))

    def to_live_status(self) -> LiveOrderStatus | None:
        mapping: dict[BrokerQueryOutcome, LiveOrderStatus | None] = {
            "working": "WORKING",
            "partial": "PARTIAL",
            "filled": "FILLED",
            "rejected": "REJECTED",
            "cancelled": "CANCELLED",
            "unavailable": None,  # stay UNKNOWN
        }
        return mapping[self.outcome]


class LiveOrderQueryPort(Protocol):
    """Única vía legítima para salir de UNKNOWN (sin re-POST)."""

    async def query_broker_order(self, *, venue_order_id: str) -> BrokerOrderQueryResult: ...


class MockLiveOrderQuery:
    """Test double. Real XTB poll PARKED."""

    def __init__(self, result: BrokerOrderQueryResult) -> None:
        self.result = result
        self.calls = 0

    async def query_broker_order(self, *, venue_order_id: str) -> BrokerOrderQueryResult:
        self.calls += 1
        _ = venue_order_id
        return self.result
