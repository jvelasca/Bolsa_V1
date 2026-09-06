"""XL-3 LiveOrder domain tests — UNKNOWN / PARTIAL / no re-POST."""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.live_order import (
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
