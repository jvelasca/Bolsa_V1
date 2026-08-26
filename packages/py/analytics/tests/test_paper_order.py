"""PaperOrder OI-4 + OR-3 state machine (ADR-034/035)."""

import pytest

from bolsa_analytics.cognitive.paper_order import (
    apply_paper_order_fill,
    build_paper_order,
    can_transition_paper_order,
    paper_order_status_copy,
    stable_order_id_from_decision,
    transition_paper_order,
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
    assert order.filled_quantity is None
    assert order.order_id == "ORD-1"
    assert order.to_dict()["status"] == "CREATED"
    assert order.to_dict()["transactionId"] is None
    assert order.to_dict()["filledQuantity"] is None


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
    assert filled.filled_quantity == 4.0
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
    assert "desconocido" in paper_order_status_copy("UNKNOWN").lower()


def test_or1_stable_order_id_from_decision() -> None:
    assert stable_order_id_from_decision("DEC-1") == "ORD-DEC-1"
    assert stable_order_id_from_decision("DEC-1") == stable_order_id_from_decision(
        "DEC-1"
    )
    order = build_paper_order(
        instrument_id="inst-1",
        side="buy",
        quantity=1.0,
        order_id=stable_order_id_from_decision("DEC-OR1"),
    )
    assert order.order_id == "ORD-DEC-OR1"


def test_or3_happy_path_submitted_ack_filled() -> None:
    order = build_paper_order(
        order_id="ORD-1", instrument_id="i", side="buy", quantity=10.0
    )
    submitted = transition_paper_order(order, "SUBMITTED")
    ack = transition_paper_order(submitted, "ACK")
    filled = apply_paper_order_fill(ack, transaction_id="tx-1")
    assert submitted.status == "SUBMITTED"
    assert ack.status == "ACK"
    assert filled.status == "FILLED"
    assert filled.transaction_id == "tx-1"


def test_or3_partial_then_filled() -> None:
    order = transition_paper_order(
        build_paper_order(order_id="ORD-1", instrument_id="i", side="buy", quantity=10.0),
        "ACK",
    )
    partial = transition_paper_order(order, "PARTIAL", filled_quantity=4.0)
    assert partial.status == "PARTIAL"
    assert partial.filled_quantity == 4.0
    filled = apply_paper_order_fill(partial, transaction_id="tx-1")
    assert filled.status == "FILLED"
    assert filled.filled_quantity == 10.0


def test_or3_unknown_resolves_to_filled() -> None:
    unknown = transition_paper_order(
        transition_paper_order(
            build_paper_order(order_id="ORD-1", instrument_id="i", side="buy", quantity=1.0),
            "SUBMITTED",
        ),
        "UNKNOWN",
    )
    assert unknown.status == "UNKNOWN"
    filled = apply_paper_order_fill(unknown, transaction_id="tx-r")
    assert filled.status == "FILLED"


def test_or3_reject_cancel_expire_are_terminal() -> None:
    base = build_paper_order(order_id="ORD-1", instrument_id="i", side="buy", quantity=1.0)
    rejected = transition_paper_order(base, "REJECTED")
    assert rejected.status == "REJECTED"
    assert can_transition_paper_order("REJECTED", "FILLED") is False
    with pytest.raises(ValueError, match="illegal_transition"):
        transition_paper_order(rejected, "FILLED")
    cancelled = transition_paper_order(base, "CANCELLED")
    assert cancelled.status == "CANCELLED"
    expired = transition_paper_order(base, "EXPIRED")
    assert expired.status == "EXPIRED"
    with pytest.raises(ValueError, match="fill_from_terminal"):
        apply_paper_order_fill(rejected)


def test_or3_illegal_partial_qty() -> None:
    ack = transition_paper_order(
        build_paper_order(order_id="ORD-1", instrument_id="i", side="buy", quantity=10.0),
        "ACK",
    )
    with pytest.raises(ValueError, match="partial_requires_qty"):
        transition_paper_order(ack, "PARTIAL", filled_quantity=10.0)
    with pytest.raises(ValueError, match="partial_requires_qty"):
        transition_paper_order(ack, "PARTIAL", filled_quantity=0.0)


def test_dex5_build_rejects_non_positive_qty() -> None:
    with pytest.raises(ValueError, match="qty_not_positive"):
        build_paper_order(instrument_id="i", side="buy", quantity=-5.0)
    with pytest.raises(ValueError, match="qty_not_positive"):
        build_paper_order(instrument_id="i", side="buy", quantity=0.0)


def test_dex5_filled_rejects_overfill() -> None:
    ack = transition_paper_order(
        build_paper_order(order_id="ORD-1", instrument_id="i", side="buy", quantity=10.0),
        "ACK",
    )
    with pytest.raises(ValueError, match="filled_gt_ordered"):
        transition_paper_order(ack, "FILLED", filled_quantity=11.0)
