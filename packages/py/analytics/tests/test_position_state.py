"""PositionState F2 + F2.1 — factory + transitions (ADR-032)."""

from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    apply_position_mark,
    apply_position_reduce,
    build_position_state_from_fill,
    position_state_from_dict,
)


def _plan(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "decisionId": "dec-1",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
    }
    base.update(overrides)
    return base


def _open_long():
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-25T15:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return pos


def test_from_fill_open_geometry() -> None:
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.5,
        fill_quantity=10.0,
        filled_at="2026-08-25T15:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    assert pos.status == "OPEN"
    assert pos.position_id == "pos-1"
    assert pos.trade_plan_id == "dec-1"
    assert pos.planned_entry == 100.0
    assert pos.actual_entry == 100.5
    assert pos.initial_stop == 95.0
    assert pos.current_stop == 95.0
    assert pos.target1 == 105.0
    assert pos.target2 == 110.0
    assert pos.quantity == 10.0
    assert pos.remaining_quantity == 10.0
    assert pos.initial_risk == 5.5
    assert pos.realized_r == 0.0
    assert pos.unrealized_r is None
    assert pos.mfe_mae == {"mfeR": None, "maeR": None, "source": "none"}
    assert pos.thesis_health == {"status": "none"}
    assert pos.protection_state == {"status": "none"}
    assert pos.trailing == {"status": "none"}
    assert pos.exit_status == "none"
    assert pos.revisions == ()
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "pending"
    assert pos.target2_leg is not None
    assert pos.target2_leg.status == "pending"
    d = pos.to_dict()
    assert d["revisions"] == []
    assert d["tradePlanId"] == "dec-1"
    assert d["status"] == "OPEN"


def test_from_fill_requires_trade_plan() -> None:
    assert (
        build_position_state_from_fill(
            None, fill_price=100.0, fill_quantity=1.0
        )
        is None
    )


def test_from_fill_requires_valid_fill() -> None:
    assert (
        build_position_state_from_fill(_plan(), fill_price=0, fill_quantity=1.0)
        is None
    )
    assert (
        build_position_state_from_fill(
            _plan(), fill_price=100.0, fill_quantity=0
        )
        is None
    )


def test_from_fill_rejects_direction_none() -> None:
    assert (
        build_position_state_from_fill(
            _plan(direction="none"), fill_price=100.0, fill_quantity=1.0
        )
        is None
    )


def test_from_fill_short_initial_risk() -> None:
    pos = build_position_state_from_fill(
        _plan(
            direction="short",
            entry=100.0,
            structuralStop=105.0,
            target1=95.0,
            target2=90.0,
        ),
        fill_price=99.0,
        fill_quantity=5.0,
        position_id="pos-s",
    )
    assert pos is not None
    assert pos.direction == "short"
    assert pos.initial_risk == 6.0


def test_mark_sets_unrealized_and_proxy_peaks() -> None:
    marked = apply_position_mark(_open_long(), 105.0, at="2026-08-25T16:00:00Z")
    assert marked is not None
    assert marked.status == "OPEN"
    assert marked.unrealized_r == 1.0
    assert marked.mfe_mae == {"mfeR": 1.0, "maeR": 1.0, "source": "close_proxy"}
    assert marked.updated_at == "2026-08-25T16:00:00Z"


def test_mark_tracks_mae_without_status_change() -> None:
    up = apply_position_mark(_open_long(), 105.0)
    assert up is not None
    down = apply_position_mark(up, 95.0)
    assert down is not None
    assert down.status == "OPEN"
    assert down.unrealized_r == -1.0
    assert down.mfe_mae["mfeR"] == 1.0
    assert down.mfe_mae["maeR"] == -1.0
    assert down.mfe_mae["source"] == "close_proxy"


def test_mark_rejects_closed_or_bad() -> None:
    closed = apply_position_reduce(_open_long(), 10.0, exit_price=100.0)
    assert closed is not None
    assert apply_position_mark(closed, 105.0) is None
    assert apply_position_mark(_open_long(), 0) is None


def test_reduce_partial_then_closed() -> None:
    partial = apply_position_reduce(_open_long(), 5.0, exit_price=105.0, at="t1")
    assert partial is not None
    assert partial.status == "PARTIAL"
    assert partial.remaining_quantity == 5.0
    assert partial.realized_r == 0.5
    assert partial.exit_status == "none"

    closed = apply_position_reduce(partial, 5.0, exit_price=110.0, at="t2")
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.remaining_quantity == 0.0
    assert closed.realized_r == 1.5
    assert closed.exit_status == "done"


def test_reduce_rejects_oversize_and_closed() -> None:
    assert apply_position_reduce(_open_long(), 11.0, exit_price=100.0) is None
    closed = apply_position_reduce(_open_long(), 10.0, exit_price=100.0)
    assert closed is not None
    assert apply_position_reduce(closed, 1.0, exit_price=100.0) is None


def test_current_stop_be_protected() -> None:
    be = apply_position_current_stop(_open_long(), 100.0)
    assert be is not None
    assert be.status == "PROTECTED"
    assert be.current_stop == 100.0

    still_open = apply_position_current_stop(_open_long(), 97.0)
    assert still_open is not None
    assert still_open.status == "OPEN"


def test_protected_wins_over_partial() -> None:
    partial = apply_position_reduce(_open_long(), 4.0, exit_price=105.0)
    assert partial is not None
    assert partial.status == "PARTIAL"
    prot = apply_position_current_stop(partial, 100.0)
    assert prot is not None
    assert prot.status == "PROTECTED"
    assert prot.remaining_quantity == 6.0


def test_short_be_stop() -> None:
    short = build_position_state_from_fill(
        _plan(direction="short", entry=100.0, structuralStop=105.0),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="s1",
    )
    assert short is not None
    assert apply_position_current_stop(short, 100.0).status == "PROTECTED"  # type: ignore[union-attr]
    assert apply_position_current_stop(short, 102.0).status == "OPEN"  # type: ignore[union-attr]


def test_from_fill_rejects_watch_armed() -> None:
    fill = dict(fill_price=100.0, fill_quantity=1.0)
    assert build_position_state_from_fill(_plan(status="WATCH"), **fill) is None
    assert build_position_state_from_fill(_plan(status="ARMED"), **fill) is None
    assert build_position_state_from_fill(_plan(status="BLOCKED"), **fill) is None


def test_from_fill_watch_with_override() -> None:
    pos = build_position_state_from_fill(
        _plan(status="WATCH"),
        fill_price=100.0,
        fill_quantity=1.0,
        position_id="ov-1",
        override={"reason": "manual_fill_after_review"},
    )
    assert pos is not None
    assert pos.status == "OPEN"
    assert pos.position_id == "ov-1"


def test_from_fill_empty_override_rejected() -> None:
    assert (
        build_position_state_from_fill(
            _plan(status="WATCH"),
            fill_price=100.0,
            fill_quantity=1.0,
            override={"reason": "  "},
        )
        is None
    )


def test_long_stop_cannot_worsen() -> None:
    assert apply_position_current_stop(_open_long(), 94.0) is None
    worse = apply_position_current_stop(
        _open_long(), 94.0, override={"reason": "gap_widen"}
    )
    assert worse is not None
    assert worse.current_stop == 94.0


def test_short_stop_cannot_worsen() -> None:
    short = build_position_state_from_fill(
        _plan(direction="short", entry=100.0, structuralStop=105.0),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="s2",
    )
    assert short is not None
    assert apply_position_current_stop(short, 106.0) is None
    worse = apply_position_current_stop(
        short, 106.0, override={"reason": "widen"}
    )
    assert worse is not None
    assert worse.current_stop == 106.0


def test_from_dict_roundtrip_ignores_bookkeeping() -> None:
    pos = _open_long()
    blob = dict(pos.to_dict())
    blob["_lastExitTransactionId"] = "tx-exit-1"
    restored = position_state_from_dict(blob)
    assert restored is not None
    assert restored.position_id == pos.position_id
    assert restored.remaining_quantity == pos.remaining_quantity
    assert restored.status == "OPEN"
    assert position_state_from_dict({"direction": "long"}) is None


def test_v152_target_leg_pending_at_birth_and_executed_on_t1_reduce() -> None:
    from bolsa_analytics.cognitive.position_state import apply_target_leg

    pos = _open_long()
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "pending"
    trig = apply_target_leg(
        pos, which="t1", status="triggered", at="2026-09-01T11:00:00Z", event_id="ev-t1"
    )
    assert trig.target1_leg is not None
    assert trig.target1_leg.status == "triggered"
    reduced = apply_position_reduce(
        trig,
        5.0,
        exit_price=105.0,
        at="2026-09-01T11:01:00Z",
        mark_target1_achieved=True,
        fill_id="tx-t1",
        event_id="ev-t1",
    )
    assert reduced is not None
    assert reduced.target1_leg is not None
    assert reduced.target1_leg.status == "executed"
    assert reduced.target1_leg.fill_id == "tx-t1"
    assert reduced.target1_achieved_at is not None
    # mark >= T1 without claim stays pending on a fresh position
    assert _open_long().target1_leg.status == "pending"


def test_v152_legacy_snapshot_hydrates_executed_from_achieved_at() -> None:
    blob = dict(_open_long().to_dict())
    blob.pop("target1Leg", None)
    blob["target1AchievedAt"] = "2026-08-25T16:00:00Z"
    restored = position_state_from_dict(blob)
    assert restored is not None
    assert restored.target1_leg is not None
    assert restored.target1_leg.status == "executed"


def test_v152_jit_deny_does_not_mark_failed_from_pending() -> None:
    from bolsa_analytics.cognitive.position_state import apply_target_leg

    pos = _open_long()
    failed = apply_target_leg(pos, which="t1", status="failed", at="t")
    assert failed.target1_leg is not None
    assert failed.target1_leg.status == "pending"


def test_v199_trail_and_reduce_preserve_initial_risk() -> None:
    """V1.99 P2: trail/T1 must not rewrite birth initialRisk / initialStop."""
    pos = _open_long()
    assert pos.initial_risk == 5.0
    assert pos.initial_stop == 95.0
    birth_risk = pos.initial_risk
    birth_stop = pos.initial_stop
    birth_qty = pos.quantity

    trailed = apply_position_current_stop(pos, 100.0, at="2026-09-04T12:00:00Z")
    assert trailed is not None
    assert trailed.current_stop == 100.0
    assert trailed.initial_stop == birth_stop
    assert trailed.initial_risk == birth_risk
    assert trailed.quantity == birth_qty

    # Worsen denied — state unchanged when None returned
    assert apply_position_current_stop(trailed, 90.0) is None

    reduced = apply_position_reduce(
        trailed,
        5.0,
        exit_price=120.0,
        at="2026-09-04T12:30:00Z",
        mark_target1_achieved=True,
    )
    assert reduced is not None
    assert reduced.remaining_quantity == 5.0
    assert reduced.initial_stop == birth_stop
    assert reduced.initial_risk == birth_risk
    assert reduced.quantity == birth_qty
    assert reduced.current_stop == 100.0

    trailed2 = apply_position_current_stop(reduced, 105.0, at="2026-09-04T13:00:00Z")
    assert trailed2 is not None
    assert trailed2.current_stop == 105.0
    assert trailed2.initial_stop == birth_stop
    assert trailed2.initial_risk == birth_risk
    assert trailed2.remaining_quantity == 5.0

