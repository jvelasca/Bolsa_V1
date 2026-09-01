"""V1.48 — durable PositionEvent identity (no day-key for TRAIL)."""

from __future__ import annotations

from bolsa_application.position_event_log import (
    claim_durable_event,
    make_durable_event_id,
)


def test_trail_distinct_stops_distinct_event_ids() -> None:
    a = make_durable_event_id(
        position_id="pos-1", event_type="TRAIL", action="protect", next_stop=182.0
    )
    b = make_durable_event_id(
        position_id="pos-1", event_type="TRAIL", action="protect", next_stop=185.0
    )
    assert a != b
    assert a.startswith("EVT-")
    assert 16 <= len(a) <= 128


def test_t1_same_day_same_event_id() -> None:
    a = make_durable_event_id(
        position_id="pos-1", event_type="T1", action="reduce", as_of_day="2026-09-01"
    )
    b = make_durable_event_id(
        position_id="pos-1", event_type="T1", action="reduce", as_of_day="2026-09-01"
    )
    stop = make_durable_event_id(
        position_id="pos-1", event_type="STOP", action="exit", as_of_day="2026-09-01"
    )
    assert a == b
    assert a != stop


def test_claim_trail_sequence_increments_same_day() -> None:
    blob: dict = {"currentStop": 180.0}
    blob, e1, c1 = claim_durable_event(
        blob,
        position_id="pos-1",
        event_type="TRAIL",
        action="protect",
        as_of="2026-09-01T10:00:00Z",
        next_stop=182.0,
    )
    blob, e2, c2 = claim_durable_event(
        blob,
        position_id="pos-1",
        event_type="TRAIL",
        action="protect",
        as_of="2026-09-01T11:00:00Z",
        next_stop=185.0,
    )
    blob, e1b, c1b = claim_durable_event(
        blob,
        position_id="pos-1",
        event_type="TRAIL",
        action="protect",
        as_of="2026-09-01T10:05:00Z",
        next_stop=182.0,
    )
    assert c1 is True and c2 is True and c1b is False
    assert e1.sequence == 1
    assert e2.sequence == 2
    assert e1.event_id == e1b.event_id
    assert e1.event_id != e2.event_id
