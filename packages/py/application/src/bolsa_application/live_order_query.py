"""LiveOrderQuery — XL-3 puerto query_broker (resolve UNKNOWN without re-POST).

Implementación real PARKED. Mock en tests.
≠ submit_order · ≠ execute_trade · ≠ thaw.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class BrokerOrderQueryResult:
    outcome: BrokerQueryOutcome
    venue_order_id: str | None
    filled_quantity: float | None
    remaining_quantity: float | None
    reason: str | None = None

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

    async def query_broker_order(
        self, *, venue_order_id: str
    ) -> BrokerOrderQueryResult: ...


class MockLiveOrderQuery:
    """Test double. Real XTB poll PARKED."""

    def __init__(self, result: BrokerOrderQueryResult) -> None:
        self.result = result
        self.calls = 0

    async def query_broker_order(
        self, *, venue_order_id: str
    ) -> BrokerOrderQueryResult:
        self.calls += 1
        _ = venue_order_id
        return self.result
