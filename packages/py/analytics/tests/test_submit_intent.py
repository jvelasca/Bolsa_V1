"""DurableSubmitIntent OR-2 / DEX-1 — crash/restart UNKNOWN reconstruible (ADR-035)."""

from datetime import UTC, datetime

from bolsa_analytics.cognitive.submit_intent import (
    bind_venue_order,
    mark_send_attempted,
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


def test_record_is_recorded_without_venue_and_not_send_attempted() -> None:
    intent = _recorded()
    assert intent.phase == "recorded"
    assert intent.venue_order_id is None
    assert intent.reason == "crash_before_venue_ack"
    assert intent.venue == "paper"
    assert intent.send_attempted_at is None
    assert intent.to_dict()["decisionId"] == "DEC-1"
    assert intent.to_dict()["sendAttemptedAt"] is None
    # DEX-1: pure recorded ≠ send attempted (Confirm still no-re-POST if row exists).
    assert send_attempted_durable(intent) is False
    assert send_attempted_durable(None) is False


def test_mark_send_attempted_sets_phase_and_timestamp() -> None:
    stamped = mark_send_attempted(_recorded(), at=datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
    assert stamped.phase == "send_attempted"
    assert stamped.send_attempted_at is not None
    assert send_attempted_durable(stamped) is True
    again = mark_send_attempted(stamped)
    assert again.send_attempted_at == stamped.send_attempted_at


def test_bind_venue_keeps_ids_and_is_not_fill() -> None:
    bound = bind_venue_order(_recorded(), venue_order_id="xtb-1")
    assert bound.phase == "venue_bound"
    assert bound.venue_order_id == "xtb-1"
    assert bound.intent_id == "INT-DEC-1"
    assert bound.order_id == "ORD-DEC-1"
    assert bound.phase != "filled"
    assert send_attempted_durable(bound) is True
    again = bind_venue_order(bound, venue_order_id="xtb-other")
    assert again.venue_order_id == "xtb-1"


def test_reconstruct_recorded_is_unknown_never_error() -> None:
    rec = reconstruct_unknown(_recorded())
    assert rec.outcome == "unknown"
    assert rec.send_attempted is True
    assert rec.reason == "crash_before_venue_ack"
    assert rec.outcome != "error"
    assert rec.outcome != "not_executed"


def test_reconstruct_send_attempted_keeps_before_venue_reason() -> None:
    stamped = mark_send_attempted(_recorded())
    rec = reconstruct_unknown(stamped)
    assert rec.outcome == "unknown"
    assert rec.send_attempted is True
    assert rec.reason == "crash_before_venue_ack"


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
