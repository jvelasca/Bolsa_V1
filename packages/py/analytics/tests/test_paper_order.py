"""PaperOrder OI-4 — CREATED→FILLED (ADR-034)."""

from bolsa_analytics.cognitive.paper_order import (
    apply_paper_order_fill,
    build_paper_order,
    paper_order_status_copy,
)


def test_build_is_created_paper_without_fill() -> None:
    order = build_paper_order(
        order_id="ORD-1",
        instrument_id="inst-1",
        side="buy",
        quantity=10.0,
        intent_id="INT-1",
    )
    assert order.status == "CREATED"
    assert order.venue == "PAPER"
    assert order.transaction_id is None
    assert order.order_id == "ORD-1"
    assert order.to_dict()["status"] == "CREATED"
    assert order.to_dict()["transactionId"] is None


def test_apply_fill_created_to_filled() -> None:
    created = build_paper_order(
        order_id="ORD-1",
        instrument_id="inst-1",
        side="sell",
        quantity=4.0,
    )
    filled = apply_paper_order_fill(created, transaction_id="tx-1")
    assert filled.status == "FILLED"
    assert filled.transaction_id == "tx-1"
    assert filled.order_id == created.order_id
    assert filled.venue == "PAPER"
    assert created.status == "CREATED"


def test_filled_does_not_revert_and_is_idempotent() -> None:
    created = build_paper_order(
        order_id="ORD-1",
        instrument_id="inst-1",
        side="buy",
        quantity=1.0,
    )
    filled = apply_paper_order_fill(created, transaction_id="tx-1")
    again = apply_paper_order_fill(filled, transaction_id="tx-other")
    assert again.status == "FILLED"
    assert again.transaction_id == "tx-1"
    assert again is filled or again.transaction_id == filled.transaction_id


def test_blank_order_id_is_generated() -> None:
    order = build_paper_order(
        order_id="  ",
        instrument_id="inst-1",
        side="buy",
        quantity=1.0,
    )
    assert order.order_id.startswith("ORD-")
    assert order.status == "CREATED"


def test_created_copy_is_not_filled() -> None:
    assert "no confirmado" in paper_order_status_copy("CREATED").lower()
    assert "cubierta" in paper_order_status_copy("FILLED").lower()
    assert paper_order_status_copy("CREATED") != paper_order_status_copy("FILLED")
