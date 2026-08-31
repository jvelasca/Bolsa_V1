"""PositionRevision OI-5 — historia auditada (ADR-034)."""

from bolsa_analytics.cognitive.position_revision import (
    build_position_revision,
    position_revision_from_dict,
    revisions_from_raw,
    stop_or_status_changed,
)
from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    apply_position_mark,
    apply_position_reduce,
    build_position_state_from_fill,
    position_state_from_dict,
)


def _open_long(*, stop: float = 95.0):
    pos = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "inst-1",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": stop,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-26T00:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return pos


def test_build_revision_fields() -> None:
    rev = build_position_revision(
        at="2026-08-26T12:00:00Z",
        previous_stop=95.0,
        next_stop=98.0,
        previous_status="OPEN",
        next_status="OPEN",
        origin="protect",
        reason=None,
        revision_id="REV-1",
    )
    assert rev.to_dict() == {
        "revisionId": "REV-1",
        "at": "2026-08-26T12:00:00Z",
        "previousStop": 95.0,
        "nextStop": 98.0,
        "previousStatus": "OPEN",
        "nextStatus": "OPEN",
        "origin": "protect",
        "reason": None,
    }


def test_stop_or_status_changed() -> None:
    assert stop_or_status_changed(
        previous_stop=95.0,
        next_stop=98.0,
        previous_status="OPEN",
        next_status="OPEN",
    )
    assert stop_or_status_changed(
        previous_stop=95.0,
        next_stop=95.0,
        previous_status="OPEN",
        next_status="PARTIAL",
    )
    assert not stop_or_status_changed(
        previous_stop=95.0,
        next_stop=95.0,
        previous_status="OPEN",
        next_status="OPEN",
    )


def test_from_fill_starts_with_empty_revisions() -> None:
    pos = _open_long()
    assert pos.revisions == ()
    assert pos.to_dict()["revisions"] == []


def test_apply_stop_appends_revision() -> None:
    pos = _open_long()
    nxt = apply_position_current_stop(
        pos, 98.0, at="2026-08-26T01:00:00Z", origin="protect"
    )
    assert nxt is not None
    assert nxt.current_stop == 98.0
    assert len(nxt.revisions) == 1
    rev = nxt.revisions[0]
    assert rev.origin == "protect"
    assert rev.previous_stop == 95.0
    assert rev.next_stop == 98.0
    assert rev.previous_status == "OPEN"
    assert rev.next_status == "OPEN"
    assert rev.at == "2026-08-26T01:00:00Z"


def test_apply_stop_appends_trail_revision() -> None:
    pos = _open_long()
    nxt = apply_position_current_stop(
        pos, 98.0, at="2026-08-26T01:00:00Z", origin="trail", reason="trail_confirm"
    )
    assert nxt is not None
    assert len(nxt.revisions) == 1
    assert nxt.revisions[0].origin == "trail"
    assert nxt.revisions[0].reason == "trail_confirm"


def test_same_stop_no_revision() -> None:
    pos = _open_long()
    nxt = apply_position_current_stop(pos, 95.0, at="2026-08-26T01:00:00Z")
    assert nxt is not None
    assert nxt.revisions == ()


def test_be_stop_appends_status_change() -> None:
    pos = _open_long()
    be = apply_position_current_stop(pos, 100.0, at="t1", origin="stop")
    assert be is not None
    assert be.status == "PROTECTED"
    assert len(be.revisions) == 1
    assert be.revisions[0].previous_status == "OPEN"
    assert be.revisions[0].next_status == "PROTECTED"


def test_worsen_with_override_origin() -> None:
    pos = _open_long(stop=98.0)
    worse = apply_position_current_stop(
        pos, 94.0, at="t1", override={"reason": "gap_widen"}
    )
    assert worse is not None
    assert worse.revisions[0].origin == "override"
    assert worse.revisions[0].reason == "gap_widen"


def test_reduce_appends_status_revision() -> None:
    pos = _open_long()
    partial = apply_position_reduce(pos, 5.0, exit_price=105.0, at="t1")
    assert partial is not None
    assert partial.status == "PARTIAL"
    assert len(partial.revisions) == 1
    assert partial.revisions[0].origin == "reduce"
    assert partial.revisions[0].previous_status == "OPEN"
    assert partial.revisions[0].next_status == "PARTIAL"


def test_mark_does_not_append() -> None:
    pos = _open_long()
    marked = apply_position_mark(pos, 105.0, at="t1")
    assert marked is not None
    assert marked.revisions == ()


def test_round_trip_revisions_in_snapshot() -> None:
    pos = _open_long()
    nxt = apply_position_current_stop(pos, 98.0, at="t1", origin="protect")
    assert nxt is not None
    blob = nxt.to_dict()
    back = position_state_from_dict(blob)
    assert back is not None
    assert len(back.revisions) == 1
    assert back.revisions[0].origin == "protect"
    assert back.revisions[0].next_stop == 98.0


def test_revisions_from_raw_skips_invalid() -> None:
    assert revisions_from_raw(None) == ()
    assert revisions_from_raw([{"revisionId": "x"}]) == ()
    ok = position_revision_from_dict(
        {
            "revisionId": "REV-1",
            "at": "t",
            "previousStop": 1.0,
            "nextStop": 2.0,
            "previousStatus": "OPEN",
            "nextStatus": "OPEN",
            "origin": "protect",
            "reason": None,
        }
    )
    assert ok is not None
    assert ok.revision_id == "REV-1"
