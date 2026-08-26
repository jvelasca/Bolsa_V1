"""BrokerAdapterReceipt — sello del puerto Paper | Live (ADR-034).

PaperBrokerAdapter = venue PAPER. Mock = LIVE not_wired.
XtbBrokerAdapter = LIVE vía bridge; submitted ≠ fill; filled→ledger (XL-2).
≠ PaperBroker ≠ PaperOrder ≠ ExecutionRecord ≠ money path real.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BrokerAdapterVenue = Literal["PAPER", "LIVE"]
BrokerAdapterName = Literal["paper_broker", "mock", "xtb"]
BrokerAdapterFillStatus = Literal[
    "executed",
    "unknown",
    "not_wired",
    "rejected",
    "submitted",
]

BROKER_ADAPTER_KEY = "brokerAdapter"
BROKER_ADAPTER_PAPER: BrokerAdapterName = "paper_broker"
BROKER_ADAPTER_MOCK: BrokerAdapterName = "mock"
BROKER_ADAPTER_XTB: BrokerAdapterName = "xtb"


@dataclass(frozen=True, slots=True)
class BrokerAdapterReceipt:
    """Foto honesta del submit. submitted ≠ fill; filled→ledger (XL-2)."""

    venue: BrokerAdapterVenue
    adapter: BrokerAdapterName
    fill_status: BrokerAdapterFillStatus

    def to_dict(self) -> dict[str, object]:
        return {
            "venue": self.venue,
            "adapter": self.adapter,
            "fillStatus": self.fill_status,
        }


def build_broker_adapter_receipt(
    *,
    venue: BrokerAdapterVenue,
    adapter: BrokerAdapterName,
    fill_status: BrokerAdapterFillStatus,
) -> BrokerAdapterReceipt:
    """Receipt tras submit: paper / mock / xtb (submitted ≠ fill; filled→ledger)."""
    return BrokerAdapterReceipt(
        venue=venue,
        adapter=adapter,
        fill_status=fill_status,
    )


def broker_adapter_venue_copy(
    venue: BrokerAdapterVenue,
    adapter: BrokerAdapterName | None = None,
) -> str:
    """Copy de mesa: LIVE mock ≠ XTB; submitted ≠ fill; filled→ledger (XL-2)."""
    if venue == "LIVE" and adapter == "xtb":
        return "XTB live — submitted ≠ fill; filled→ledger (≠ paper)"
    if venue == "LIVE":
        return "Mock live — no envío (≠ broker live)"
    return "Puerto paper (≠ broker live)"
