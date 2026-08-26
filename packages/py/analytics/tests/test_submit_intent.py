"""DurableSubmitIntent OR-2 — crash/restart UNKNOWN reconstruible (ADR-035)."""

from bolsa_analytics.cognitive.submit_intent import (
    bind_venue_order,
    mark_submit_filled,
    reconstruct_unknown,
    record_submit_intent,
    send_attempted_durable,
)


def _recorded():
    return record_submit_intent(
        decision_id="DEC-1",
        intent_id="INT-DEC-1",
        order_id="ORD-DEC-1",
        account_id="acc-1",
    )


def test_record_is_recorded_without_venue() -> None:
    intent = _recorded()
    assert intent.phase == "recorded"
    assert intent.venue_order_id is None
    assert intent.reason == "crash_before_venue_ack"
    assert intent.to_dict()["decisionId"] == "DEC-1"
    assert send_attempted_durable(intent) is True
    assert send_attempted_durable(None) is False


def test_bind_venue_keeps_ids_and_is_not_fill() -> None:
    bound = bind_venue_order(_recorded(), venue_order_id="xtb-1")
    assert bound.phase == "venue_bound"
    assert bound.venue_order_id == "xtb-1"
    assert bound.intent_id == "INT-DEC-1"
    assert bound.order_id == "ORD-DEC-1"
    assert bound.phase != "filled"
    again = bind_venue_order(bound, venue_order_id="xtb-other")
    assert again.venue_order_id == "xtb-1"


def test_reconstruct_recorded_is_unknown_never_error() -> None:
    rec = reconstruct_unknown(_recorded())
    assert rec.outcome == "unknown"
    assert rec.send_attempted is True
    assert rec.reason == "crash_before_venue_ack"
    assert rec.outcome != "error"
    assert rec.outcome != "not_executed"


def test_reconstruct_venue_bound_keeps_unknown() -> None:
    bound = bind_venue_order(_recorded(), venue_order_id="xtb-1")
    rec = reconstruct_unknown(bound)
    assert rec.outcome == "unknown"
    assert rec.send_attempted is True
    assert rec.reason == "crash_after_venue_ack"


def test_filled_is_not_in_flight_for_resubmit_kernel() -> None:
    filled = mark_submit_filled(_recorded())
    assert filled.phase == "filled"
    assert filled.reason is None
    assert send_attempted_durable(filled) is True
    rec = reconstruct_unknown(filled)
    assert rec.outcome == "unknown"
    assert rec.reason == "crash_after_fill_unconfirmed"


def test_bind_does_not_revert_filled() -> None:
    filled = mark_submit_filled(_recorded())
    again = bind_venue_order(filled, venue_order_id="xtb-1")
    assert again.phase == "filled"
    assert again.venue_order_id is None
