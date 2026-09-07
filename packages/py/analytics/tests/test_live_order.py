"""XL-3 LiveOrder domain tests — UNKNOWN / PARTIAL / no re-POST."""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.live_order import (
    LiveOrder,
    LiveOrderTransitionError,
    build_live_order,
    can_transition_live_order,
    forbid_execute_trade_for_partial,
    forbid_repost_from_unknown,
    transition_live_order,
)
from bolsa_application.live_order_query import (
    BrokerOrderQueryResult,
    MockLiveOrderQuery,
)


def test_unknown_cannot_transition_to_submitting() -> None:
    assert can_transition_live_order("UNKNOWN", "SUBMITTING") is False
    order = build_live_order(
        order_id="lo-1",
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
        status="UNKNOWN",
    )
    with pytest.raises(LiveOrderTransitionError, match="UNKNOWN → SUBMITTING"):
        transition_live_order(order, "SUBMITTING")


def test_timeout_path_submitting_to_unknown() -> None:
    order = build_live_order(
        order_id="lo-2",
        instrument_id="inst-1",
        side="buy",
        quantity=10.0,
    )
    submitting = transition_live_order(order, "SUBMITTING")
    unknown = transition_live_order(submitting, "UNKNOWN")
    assert unknown.status == "UNKNOWN"
    with pytest.raises(LiveOrderTransitionError, match="re-POST"):
        forbid_repost_from_unknown(unknown)


def test_partial_qty_honesty_and_execute_trade_veto() -> None:
    order = build_live_order(
        order_id="lo-3",
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
    )
    working = transition_live_order(
        transition_live_order(
            transition_live_order(order, "SUBMITTING"),
            "SUBMITTED",
            venue_order_id="xtb-1",
        ),
        "WORKING",
    )
    partial = transition_live_order(
        working, "PARTIAL", filled_quantity=40.0
    )
    assert partial.filled_quantity == 40.0
    assert partial.remaining_quantity == 60.0
    with pytest.raises(LiveOrderTransitionError, match="PARTIAL"):
        forbid_execute_trade_for_partial(partial)


def test_duplicate_filled_single_financial_apply() -> None:
    from bolsa_analytics.cognitive.live_order import LiveOrder

    working = LiveOrder(
        order_id="lo-4",
        status="WORKING",
        venue="LIVE",
        instrument_id="inst-1",
        side="buy",
        quantity=5.0,
        filled_quantity=0.0,
        remaining_quantity=5.0,
        venue_order_id="xtb-1",
        intent_id=None,
        financial_apply_count=0,
    )
    first = transition_live_order(working, "FILLED", apply_financial=True)
    assert first.financial_apply_count == 1

    # Duplicate FILLED event path: already counted once → stays 1.
    working_again = LiveOrder(
        order_id="lo-4",
        status="WORKING",
        venue="LIVE",
        instrument_id="inst-1",
        side="buy",
        quantity=5.0,
        filled_quantity=0.0,
        remaining_quantity=5.0,
        venue_order_id="xtb-1",
        intent_id=None,
        financial_apply_count=1,
    )
    second = transition_live_order(working_again, "FILLED", apply_financial=True)
    assert second.financial_apply_count == 1


@pytest.mark.asyncio
async def test_query_broker_resolves_unknown_without_repost() -> None:
    order = build_live_order(
        order_id="lo-5",
        instrument_id="inst-1",
        side="buy",
        quantity=10.0,
        status="UNKNOWN",
    )
    with pytest.raises(LiveOrderTransitionError, match="re-POST"):
        forbid_repost_from_unknown(order)
    mock = MockLiveOrderQuery(
        BrokerOrderQueryResult(
            outcome="filled",
            venue_order_id="xtb-q-1",
            filled_quantity=10.0,
            remaining_quantity=0.0,
        )
    )
    result = await mock.query_broker_order(venue_order_id="xtb-q-1")
    assert mock.calls == 1
    nxt = result.to_live_status()
    assert nxt == "FILLED"
    resolved = transition_live_order(
        order, nxt, filled_quantity=10.0, venue_order_id="xtb-q-1"
    )
    assert resolved.status == "FILLED"


# ---------------------------------------------------------------------------
# V2.12 honest cancel hardening (pure domain: the store's cancel is domain +
# persistence; these assert the machine refuses resurrection/double-terminal and
# allows cancel from in-flight / UNKNOWN).
# ---------------------------------------------------------------------------


def _submitted(*, order_id: str = "lo-c", venue_order_id: str = "xtb-c") -> LiveOrder:
    """SUBMITTED machine via legal graph transitions."""
    order = build_live_order(
        order_id=order_id,
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
    )
    return transition_live_order(
        transition_live_order(order, "SUBMITTING"),
        "SUBMITTED",
        venue_order_id=venue_order_id,
    )


def test_cancel_from_submitted_and_unknown_are_legal() -> None:
    submitted = _submitted()
    assert can_transition_live_order(submitted.status, "CANCELLED")
    assert transition_live_order(submitted, "CANCELLED").status == "CANCELLED"

    unknown = transition_live_order(submitted, "UNKNOWN")
    # UNKNOWN → CANCELLED es legal (UNKNOWN se resuelve vía query/cancel, no re-POST).
    assert can_transition_live_order("UNKNOWN", "CANCELLED")
    assert transition_live_order(unknown, "CANCELLED").status == "CANCELLED"


def test_cancel_of_terminal_filled_rejected_is_refused() -> None:
    submitted = _submitted()
    rejected = transition_live_order(submitted, "REJECTED")
    filled = LiveOrder(
        order_id="lo-cf",
        status="FILLED",
        venue="LIVE",
        instrument_id="inst-1",
        side="buy",
        quantity=100.0,
        filled_quantity=100.0,
        remaining_quantity=0.0,
        venue_order_id="xtb-cf",
        intent_id=None,
        financial_apply_count=0,
    )
    for order in (filled, rejected):
        assert can_transition_live_order(order.status, "CANCELLED") is False
        with pytest.raises(LiveOrderTransitionError):
            transition_live_order(order, "CANCELLED")


def test_cancel_single_terminal_no_resurrection() -> None:
    working = _submitted(order_id="lo-c", venue_order_id="xtb-c")
    working = transition_live_order(working, "WORKING", venue_order_id="xtb-c")
    cancelled = transition_live_order(working, "CANCELLED")
    assert cancelled.status == "CANCELLED"

    # Ya cancelada (estado terminal único): no admite transición y una orden
    # terminada jamás resucita a FILLED/en curso.
    assert can_transition_live_order("CANCELLED", "CANCELLED") is False
    with pytest.raises(LiveOrderTransitionError):
        transition_live_order(cancelled, "CANCELLED")
    with pytest.raises(LiveOrderTransitionError):
        transition_live_order(cancelled, "FILLED", filled_quantity=100.0)
