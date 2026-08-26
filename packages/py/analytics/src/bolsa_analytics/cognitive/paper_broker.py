"""PaperBrokerReceipt — sello venue PAPER (ADR-034 post-OI-6).

PaperBroker = capa paper antes de BrokerAdapter.
≠ PaperOrder ≠ ExecutionRecord ≠ ExecutionPlan ≠ broker live.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from bolsa_analytics.cognitive.paper_order import PaperOrder

PaperBrokerVenue = Literal["PAPER"]
PaperBrokerAdapter = Literal["paper_broker"]
PaperBrokerFillStatus = Literal["executed", "unknown"]

PAPER_BROKER_KEY = "paperBroker"
PAPER_BROKER_ADAPTER: PaperBrokerAdapter = "paper_broker"


@dataclass(frozen=True, slots=True)
class PaperBrokerReceipt:
    """Foto honesta del submit paper. Venue siempre PAPER."""

    venue: PaperBrokerVenue
    adapter: PaperBrokerAdapter
    paper_order: PaperOrder
    fill_status: PaperBrokerFillStatus

    def to_dict(self) -> dict[str, object]:
        return {
            "venue": self.venue,
            "adapter": self.adapter,
            "paperOrder": self.paper_order.to_dict(),
            "fillStatus": self.fill_status,
        }


def build_paper_broker_receipt(
    *,
    paper_order: PaperOrder,
    fill_status: PaperBrokerFillStatus,
) -> PaperBrokerReceipt:
    """Receipt tras submit: executed o unknown (OI-3/OI-4)."""
    return PaperBrokerReceipt(
        venue="PAPER",
        adapter=PAPER_BROKER_ADAPTER,
        paper_order=paper_order,
        fill_status=fill_status,
    )


def paper_broker_venue_copy() -> str:
    """Copy de mesa: PaperBroker ≠ broker live."""
    return "Venue paper (≠ broker live)"
