"""PaperBrokerReceipt — venue PAPER ≠ broker live."""

from __future__ import annotations

from bolsa_analytics.cognitive.paper_broker import (
    PAPER_BROKER_ADAPTER,
    build_paper_broker_receipt,
    paper_broker_venue_copy,
)
from bolsa_analytics.cognitive.paper_order import (
    apply_paper_order_fill,
    build_paper_order,
)


def test_receipt_executed_stamps_paper_venue() -> None:
    order = apply_paper_order_fill(
        build_paper_order(instrument_id="inst-1", side="buy", quantity=10.0),
        transaction_id="tx-1",
    )
    receipt = build_paper_broker_receipt(paper_order=order, fill_status="executed")
    assert receipt.venue == "PAPER"
    assert receipt.adapter == PAPER_BROKER_ADAPTER
    assert receipt.fill_status == "executed"
    assert receipt.paper_order.status == "FILLED"
    assert receipt.to_dict()["fillStatus"] == "executed"


def test_receipt_unknown_keeps_created() -> None:
    order = build_paper_order(instrument_id="inst-1", side="sell", quantity=5.0)
    receipt = build_paper_broker_receipt(paper_order=order, fill_status="unknown")
    assert receipt.fill_status == "unknown"
    assert receipt.paper_order.status == "CREATED"
    assert receipt.venue == "PAPER"
    assert "broker live" in paper_broker_venue_copy().lower() or "≠" in paper_broker_venue_copy()
