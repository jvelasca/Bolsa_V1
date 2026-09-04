"""V1.86 — domain lifecycle kernel: FSM · accounting ENTRY · idempotency · payload."""

from __future__ import annotations

import pytest

from bolsa_domain.lifecycle import (
    LIFECYCLE_CASH,
    AppendFail,
    AppendOk,
    LifecycleEventInput,
    account_lifecycle_fills,
    append_validated_lifecycle_event,
    assert_equity_invariant,
    reduce_lifecycle_events,
    validate_transition_result,
)


def _append_all(kinds: list[str]):
    log: list = []
    for kind in kinds:
        result = append_validated_lifecycle_event(
            log, LifecycleEventInput(kind=kind)  # type: ignore[arg-type]
        )
        assert isinstance(result, AppendOk), getattr(result, "error", None)
        log = list(result.log)
    return log


def test_trail_golden_sequence() -> None:
    log = _append_all(
        [
            "POSITION_OPENED",
            "T1_TRIGGERED",
            "T1_EXECUTED",
            "TRAIL_APPLIED",
            "EXIT_REQUIRED",
            "POSITION_CLOSED",
        ]
    )
    stage, path = reduce_lifecycle_events(log)
    assert stage == "closed"
    assert path == "trail"


def test_t2_golden_shortcut() -> None:
    log = _append_all(
        [
            "POSITION_OPENED",
            "T1_EXECUTED",
            "T2_TRIGGERED",
            "T2_EXECUTED",
            "POSITION_CLOSED",
        ]
    )
    stage, path = reduce_lifecycle_events(log)
    assert stage == "closed"
    assert path == "t2"


def test_illegal_transition_before_open() -> None:
    result = append_validated_lifecycle_event(
        [], LifecycleEventInput(kind="T1_EXECUTED", event_id="bad")
    )
    assert isinstance(result, AppendFail)
    assert result.error.code == "illegal_transition"


def test_accounting_entry_debit_and_equity_invariant() -> None:
    log = _append_all(["POSITION_OPENED"])
    acct = account_lifecycle_fills(log)
    assert acct.cash == LIFECYCLE_CASH - 10 * 100
    assert acct.remaining == 10
    assert acct.market_value == 10 * 106
    assert acct.total_equity == acct.cash + acct.market_value
    assert_equity_invariant(acct)


def test_accounting_trail_closed() -> None:
    log = _append_all(
        [
            "POSITION_OPENED",
            "T1_TRIGGERED",
            "T1_EXECUTED",
            "TRAIL_APPLIED",
            "EXIT_REQUIRED",
            "POSITION_CLOSED",
        ]
    )
    acct = account_lifecycle_fills(log)
    # ENTRY -1000; T1 +525; EXIT +530 ⇒ cash 100055; realized 55
    assert acct.remaining == 0
    assert acct.realized_pnl == 55
    assert acct.cash == 100_055
    assert acct.total_equity == 100_055
    assert_equity_invariant(acct)


def test_accounting_t2_closed() -> None:
    log = _append_all(
        [
            "POSITION_OPENED",
            "T1_EXECUTED",
            "T2_TRIGGERED",
            "T2_EXECUTED",
            "POSITION_CLOSED",
        ]
    )
    acct = account_lifecycle_fills(log)
    # ENTRY -1000; T1 +525; T2 +330; EXIT +220 ⇒ cash 100075; realized 75
    assert acct.realized_pnl == 75
    assert acct.cash == 100_075
    assert acct.total_equity == 100_075
    assert_equity_invariant(acct)


def test_idempotent_close_replay_after_remaining_zero() -> None:
    log = _append_all(
        [
            "POSITION_OPENED",
            "T1_EXECUTED",
            "TRAIL_APPLIED",
            "EXIT_REQUIRED",
        ]
    )
    body = LifecycleEventInput(kind="POSITION_CLOSED", event_id="evt-close-once")
    first = append_validated_lifecycle_event(log, body)
    assert isinstance(first, AppendOk)
    assert account_lifecycle_fills(first.log).remaining == 0
    second = append_validated_lifecycle_event(first.log, body)
    assert isinstance(second, AppendOk)
    assert second.idempotent is True
    assert len(second.log) == 5


def test_idempotent_same_payload() -> None:
    log = _append_all(["POSITION_OPENED"])
    first = append_validated_lifecycle_event(
        log, LifecycleEventInput(kind="T1_EXECUTED", event_id="evt-fixed-t1")
    )
    assert isinstance(first, AppendOk)
    second = append_validated_lifecycle_event(
        first.log, LifecycleEventInput(kind="T1_EXECUTED", event_id="evt-fixed-t1")
    )
    assert isinstance(second, AppendOk)
    assert second.idempotent is True
    assert len(second.log) == len(first.log)


def test_event_id_conflict_different_payload() -> None:
    log = _append_all(["POSITION_OPENED"])
    first = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="T1_EXECUTED",
            event_id="evt-123",
            quantity=5,
            price=105,
        ),
    )
    assert isinstance(first, AppendOk)
    conflict = append_validated_lifecycle_event(
        first.log,
        LifecycleEventInput(
            kind="T1_EXECUTED",
            event_id="evt-123",
            quantity=8,
            price=130,
        ),
    )
    assert isinstance(conflict, AppendFail)
    assert conflict.error.code == "event_id_conflict"
    assert len(first.log) == 2


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"quantity": 0}, "invalid_payload"),
        ({"quantity": -5}, "invalid_payload"),
        ({"price": 0}, "invalid_payload"),
        ({"price": -100}, "invalid_payload"),
        ({"fees": -20}, "invalid_payload"),
        ({"quantity": 1000}, "invalid_payload"),
    ],
)
def test_invalid_fill_payload(kwargs: dict, code: str) -> None:
    log = _append_all(["POSITION_OPENED"])
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(kind="T1_EXECUTED", event_id="evt-bad-payload", **kwargs),
    )
    assert isinstance(result, AppendFail)
    assert result.error.code == code


def test_close_qty_must_equal_remaining() -> None:
    log = _append_all(
        ["POSITION_OPENED", "T1_EXECUTED", "TRAIL_APPLIED", "EXIT_REQUIRED"]
    )
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="POSITION_CLOSED",
            event_id="evt-bad-close",
            quantity=1,
            price=106,
            fill_id="fill-bad-close",
        ),
    )
    assert isinstance(result, AppendFail)
    assert result.error.code == "invalid_payload"


def test_identity_mismatch_instrument() -> None:
    log = _append_all(["POSITION_OPENED"])
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="T1_EXECUTED",
            instrument_id="inst-nvda",
            event_id="evt-wrong-inst",
        ),
    )
    assert isinstance(result, AppendFail)
    assert result.error.code == "identity_mismatch"


def test_trail_relaxation_rejected() -> None:
    log = _append_all(["POSITION_OPENED", "T1_EXECUTED"])
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="evt-relax",
            previous_stop=98,
            new_stop=92,
        ),
    )
    assert isinstance(result, AppendFail)
    assert result.error.code == "trail_relaxation"


def test_trail_relaxation_short() -> None:
    """SHORT ratchet: stop must never rise (relax toward higher prices)."""
    log: list = []
    for kind, kwargs in (
        ("POSITION_OPENED", {"side": "SHORT", "event_id": "open-short"}),
        ("T1_EXECUTED", {"side": "SHORT", "event_id": "t1-short"}),
    ):
        result = append_validated_lifecycle_event(
            log,
            LifecycleEventInput(kind=kind, **kwargs),  # type: ignore[arg-type]
        )
        assert isinstance(result, AppendOk), getattr(result, "error", None)
        log = list(result.log)
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="evt-relax-short",
            side="SHORT",
            previous_stop=110,
            new_stop=115,
        ),
    )
    assert isinstance(result, AppendFail)
    assert result.error.code == "trail_relaxation"


def test_trail_wrong_side_short() -> None:
    """SHORT stop must stay above last price (symmetric to LONG < last)."""
    log: list = []
    for kind, kwargs in (
        ("POSITION_OPENED", {"side": "SHORT", "event_id": "open-short-2"}),
        ("T1_EXECUTED", {"side": "SHORT", "event_id": "t1-short-2"}),
    ):
        result = append_validated_lifecycle_event(
            log,
            LifecycleEventInput(kind=kind, **kwargs),  # type: ignore[arg-type]
        )
        assert isinstance(result, AppendOk), getattr(result, "error", None)
        log = list(result.log)
    # After T1, last_price is 105 (default mock). SHORT stop ≤ 105 is wrong side.
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="evt-wrong-short",
            side="SHORT",
            previous_stop=110,
            new_stop=100,
        ),
    )
    assert isinstance(result, AppendFail)
    assert result.error.code == "invalid_payload"


def test_invalid_timestamp() -> None:
    result = append_validated_lifecycle_event(
        [],
        LifecycleEventInput(
            kind="POSITION_OPENED",
            at="not-a-date",
            event_id="evt-bad-ts",
        ),
    )
    assert isinstance(result, AppendFail)
    assert result.error.code == "invalid_timestamp"


def test_duplicate_fill_id() -> None:
    log = _append_all(["POSITION_OPENED", "T1_EXECUTED", "T2_TRIGGERED"])
    t1_fill = next(e.fill_id for e in log if e.kind == "T1_EXECUTED")
    assert t1_fill
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="T2_EXECUTED",
            fill_id=t1_fill,
            event_id="evt-other-t2",
        ),
    )
    assert isinstance(result, AppendFail)
    assert result.error.code == "duplicate_fill_id"


def test_validate_transition_table() -> None:
    ok, _ = validate_transition_result("candidate", "POSITION_OPENED")
    assert ok is True
    ok2, err = validate_transition_result("open", "T2_EXECUTED")
    assert ok2 is False
    assert err.code == "illegal_transition"  # type: ignore[union-attr]


def test_v198_trail_self_loop_two_ratchets() -> None:
    """V1.98: N TRAIL_APPLIED stay in trailing."""
    log = _append_all(["POSITION_OPENED", "T1_EXECUTED", "TRAIL_APPLIED"])
    stage, _ = reduce_lifecycle_events(log)
    assert stage == "trailing"
    second = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="evt-trail-2",
            at="2026-09-02T12:10:00.000Z",
            previous_stop=98,
            new_stop=100,
        ),
    )
    assert isinstance(second, AppendOk), getattr(second, "error", None)
    assert second.stage == "trailing"
    assert sum(1 for e in second.log if e.kind == "TRAIL_APPLIED") == 2


def test_v198_trail_then_t2() -> None:
    """V1.98: T1 → TRAIL → T2_TRIGGERED → T2_EXECUTED is legal."""
    log = _append_all(
        [
            "POSITION_OPENED",
            "T1_EXECUTED",
            "TRAIL_APPLIED",
            "T2_TRIGGERED",
            "T2_EXECUTED",
        ]
    )
    stage, path = reduce_lifecycle_events(log)
    assert stage == "t2_executed"
    assert path == "t2"


def test_v198_t2_then_trail() -> None:
    """V1.98: T1 → T2 → TRAIL_APPLIED (remainder trails)."""
    log = _append_all(
        [
            "POSITION_OPENED",
            "T1_EXECUTED",
            "T2_TRIGGERED",
            "T2_EXECUTED",
        ]
    )
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="evt-trail-after-t2",
            at="2026-09-02T13:00:00.000Z",
            previous_stop=98,
            new_stop=101,
        ),
    )
    assert isinstance(result, AppendOk), getattr(result, "error", None)
    assert result.stage == "trailing"
    assert result.lineage_path == "trail"


def test_v198_t2_ready_may_close() -> None:
    """V1.98: leftover t2_ready can EXIT without completing T2_EXECUTED."""
    log = _append_all(["POSITION_OPENED", "T1_EXECUTED", "T2_TRIGGERED"])
    ok, nxt = validate_transition_result("t2_ready", "POSITION_CLOSED")
    assert ok is True
    assert nxt == "closed"
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="POSITION_CLOSED",
            event_id="evt-close-t2-ready",
            at="2026-09-02T13:00:00.000Z",
            fill_id="fill-close-t2-ready",
            quantity=5,
            price=106,
        ),
    )
    assert isinstance(result, AppendOk), getattr(result, "error", None)
    assert result.stage == "closed"


def test_v198_trail_geometry_uses_last_fill_not_mock_106() -> None:
    """V1.98: stop vs last fill price (230), not mock stage mark 106."""
    log: list = []
    for kind, kwargs in (
        (
            "POSITION_OPENED",
            {
                "event_id": "open-hi",
                "quantity": 10,
                "price": 200,
                "fill_id": "fill-open-hi",
            },
        ),
        (
            "T1_EXECUTED",
            {
                "event_id": "t1-hi",
                "quantity": 5,
                "price": 230,
                "fill_id": "fill-t1-hi",
            },
        ),
    ):
        result = append_validated_lifecycle_event(
            log,
            LifecycleEventInput(kind=kind, **kwargs),  # type: ignore[arg-type]
        )
        assert isinstance(result, AppendOk), getattr(result, "error", None)
        log = list(result.log)
    result = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="evt-trail-hi",
            at="2026-09-02T12:00:00.000Z",
            previous_stop=190,
            new_stop=220,
        ),
    )
    assert isinstance(result, AppendOk), getattr(result, "error", None)
    assert result.stage == "trailing"


def test_v198_stop_worsens_long_short() -> None:
    from bolsa_domain.lifecycle import stop_worsens

    assert stop_worsens("LONG", 98, 92) is True
    assert stop_worsens("long", 98, 99) is False
    assert stop_worsens("SHORT", 110, 115) is True
    assert stop_worsens("short", 110, 108) is False
    assert stop_worsens("LONG", None, 92) is False
