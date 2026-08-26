"""BrokerAdapterReceipt — puerto Paper | Live; mock ≠ XTB; submitted ≠ fill."""

from __future__ import annotations

from bolsa_analytics.cognitive.broker_adapter import (
    BROKER_ADAPTER_MOCK,
    BROKER_ADAPTER_PAPER,
    BROKER_ADAPTER_XTB,
    broker_adapter_venue_copy,
    build_broker_adapter_receipt,
)


def test_receipt_paper_stamps_paper_venue() -> None:
    receipt = build_broker_adapter_receipt(
        venue="PAPER",
        adapter=BROKER_ADAPTER_PAPER,
        fill_status="executed",
    )
    assert receipt.venue == "PAPER"
    assert receipt.adapter == "paper_broker"
    assert receipt.fill_status == "executed"
    assert receipt.to_dict()["fillStatus"] == "executed"
    assert "broker live" in broker_adapter_venue_copy("PAPER").lower() or "≠" in broker_adapter_venue_copy(
        "PAPER"
    )


def test_receipt_mock_live_is_not_wired() -> None:
    receipt = build_broker_adapter_receipt(
        venue="LIVE",
        adapter=BROKER_ADAPTER_MOCK,
        fill_status="not_wired",
    )
    assert receipt.venue == "LIVE"
    assert receipt.adapter == "mock"
    assert receipt.fill_status == "not_wired"
    assert receipt.fill_status != "executed"
    copy = broker_adapter_venue_copy("LIVE")
    assert "no envío" in copy.lower()
    assert "broker live" in copy.lower() or "≠" in copy


def test_receipt_xtb_rejected_and_submitted() -> None:
    rejected = build_broker_adapter_receipt(
        venue="LIVE",
        adapter=BROKER_ADAPTER_XTB,
        fill_status="rejected",
    )
    assert rejected.adapter == "xtb"
    assert rejected.fill_status == "rejected"
    assert rejected.fill_status != "executed"
    submitted = build_broker_adapter_receipt(
        venue="LIVE",
        adapter=BROKER_ADAPTER_XTB,
        fill_status="submitted",
    )
    assert submitted.fill_status == "submitted"
    assert submitted.fill_status != "executed"
    copy = broker_adapter_venue_copy("LIVE", "xtb")
    assert "xtb" in copy.lower()
    assert "ledger" in copy.lower() or "≠" in copy
