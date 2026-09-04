"""V1.99 — Position Management Certification goldens (domain kernel).

No FSM / TRANSITIONS changes. Certifies combinations already legal in V1.98.
G7 (crash/retry) is anchored in application test_lifecycle_t2_atomicity_v197
(test_crash_mid_pair_rolls_back_then_retry_exactly_once) — not reimplemented here.
"""

from __future__ import annotations

from decimal import Decimal

from bolsa_domain.lifecycle import (
    LIFECYCLE_AVG_COST,
    LIFECYCLE_BIRTH_QTY,
    LIFECYCLE_INITIAL_RISK,
    LIFECYCLE_INITIAL_STOP,
    LIFECYCLE_REMAINING_AFTER_T1,
    LIFECYCLE_REMAINING_AFTER_T2,
    AppendFail,
    AppendOk,
    LifecycleEventInput,
    account_lifecycle_fills,
    append_validated_lifecycle_event,
    assert_equity_invariant,
    last_fill_price,
    reduce_lifecycle_events,
    remaining_after_log,
    stop_worsens,
)

# V1.99 Golden 7 anchor (application layer — do not duplicate here).
V199_G7_ANCHOR = (
    "packages/py/application/tests/test_lifecycle_t2_atomicity_v197.py"
    "::test_crash_mid_pair_rolls_back_then_retry_exactly_once"
)


def _append(log: list, inp: LifecycleEventInput) -> list:
    result = append_validated_lifecycle_event(log, inp)
    assert isinstance(result, AppendOk), getattr(result, "error", None)
    return list(result.log)


def _kinds(log: list) -> list[str]:
    return [e.kind for e in log]


def test_v199_g1_open_stop_exit() -> None:
    """G1: OPEN (birth stop 95) → EXIT. STOP ≠ TRAIL_APPLIED."""
    log = _append(
        [],
        LifecycleEventInput(
            kind="POSITION_OPENED",
            event_id="g1-open",
            quantity=LIFECYCLE_BIRTH_QTY,
            price=LIFECYCLE_AVG_COST,
            fill_id="fill-g1-open",
        ),
    )
    assert remaining_after_log(log) == LIFECYCLE_BIRTH_QTY
    assert LIFECYCLE_INITIAL_STOP == Decimal("95")
    assert LIFECYCLE_INITIAL_RISK == Decimal("50")
    stage, path = reduce_lifecycle_events(log)
    assert stage == "open"
    assert path == "trail"

    log = _append(
        log,
        LifecycleEventInput(
            kind="POSITION_CLOSED",
            event_id="g1-exit",
            at="2026-09-02T15:00:00.000Z",
            fill_id="fill-g1-exit",
            quantity=LIFECYCLE_BIRTH_QTY,
            price=LIFECYCLE_AVG_COST,
        ),
    )
    stage, _ = reduce_lifecycle_events(log)
    assert stage == "closed"
    assert remaining_after_log(log) == 0
    acct = account_lifecycle_fills(log)
    assert acct.remaining == 0
    assert_equity_invariant(acct)
    assert "TRAIL_APPLIED" not in _kinds(log)


def test_v199_g2_open_t1_exit() -> None:
    """G2: OPEN → T1 → EXIT (HTTP twin: test_lifecycle_golden_v195)."""
    log: list = []
    for kind in ("POSITION_OPENED", "T1_EXECUTED"):
        log = _append(log, LifecycleEventInput(kind=kind))  # type: ignore[arg-type]
    assert remaining_after_log(log) == LIFECYCLE_REMAINING_AFTER_T1
    log = _append(
        log,
        LifecycleEventInput(
            kind="POSITION_CLOSED",
            event_id="g2-exit",
            at="2026-09-02T15:00:00.000Z",
            fill_id="fill-g2-exit",
        ),
    )
    stage, path = reduce_lifecycle_events(log)
    assert stage == "closed"
    assert path == "trail"
    assert remaining_after_log(log) == 0
    assert_equity_invariant(account_lifecycle_fills(log))


def test_v199_g3_open_t1_t2_exit() -> None:
    """G3: OPEN → T1 → T2 → EXIT (HTTP twin: test_lifecycle_golden_v196)."""
    log: list = []
    for kind in (
        "POSITION_OPENED",
        "T1_EXECUTED",
        "T2_TRIGGERED",
        "T2_EXECUTED",
        "POSITION_CLOSED",
    ):
        log = _append(log, LifecycleEventInput(kind=kind))  # type: ignore[arg-type]
    stage, path = reduce_lifecycle_events(log)
    assert stage == "closed"
    assert path == "t2"
    assert remaining_after_log(log) == 0
    assert_equity_invariant(account_lifecycle_fills(log))


def test_v199_g4_open_t1_trail_trail_exit() -> None:
    """G4: OPEN → T1 → TRAIL → TRAIL → EXIT."""
    log: list = []
    for kind in ("POSITION_OPENED", "T1_EXECUTED"):
        log = _append(log, LifecycleEventInput(kind=kind))  # type: ignore[arg-type]

    log = _append(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="g4-trail-1",
            at="2026-09-02T12:00:00.000Z",
            previous_stop=95,
            new_stop=98,
        ),
    )
    log = _append(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="g4-trail-2",
            at="2026-09-02T12:10:00.000Z",
            previous_stop=98,
            new_stop=100,
        ),
    )
    stage, path = reduce_lifecycle_events(log)
    assert stage == "trailing"
    assert path == "trail"
    assert sum(1 for e in log if e.kind == "TRAIL_APPLIED") == 2
    assert remaining_after_log(log) == LIFECYCLE_REMAINING_AFTER_T1

    log = _append(
        log,
        LifecycleEventInput(
            kind="POSITION_CLOSED",
            event_id="g4-exit",
            at="2026-09-02T15:00:00.000Z",
            fill_id="fill-g4-exit",
        ),
    )
    stage, _ = reduce_lifecycle_events(log)
    assert stage == "closed"
    assert remaining_after_log(log) == 0
    assert_equity_invariant(account_lifecycle_fills(log))


def test_v199_g5_aggressive_management() -> None:
    """G5 master: OPEN@100 → T1@120 → TRAIL×2 → T2@125 → TRAIL → EXIT.

    Asserts: stop never retreats · qty · lastFill · remaining · lineage ≠ log.
    """
    log = _append(
        [],
        LifecycleEventInput(
            kind="POSITION_OPENED",
            event_id="g5-open",
            quantity=10,
            price=100,
            fill_id="fill-g5-open",
        ),
    )
    assert remaining_after_log(log) == Decimal("10")
    stage, _ = reduce_lifecycle_events(log)
    assert last_fill_price(log, stage=stage, lineage_path="trail") == Decimal("100")

    log = _append(
        log,
        LifecycleEventInput(
            kind="T1_EXECUTED",
            event_id="g5-t1",
            at="2026-09-02T11:30:00.000Z",
            quantity=5,
            price=120,
            fill_id="fill-g5-t1",
        ),
    )
    assert remaining_after_log(log) == Decimal("5")
    stage, path = reduce_lifecycle_events(log)
    assert stage == "t1_executed"
    assert last_fill_price(log, stage=stage, lineage_path=path) == Decimal("120")

    stops: list[Decimal] = [Decimal("95")]
    for i, (prev, nxt, at) in enumerate(
        (
            (95, 100, "2026-09-02T12:00:00.000Z"),
            (100, 105, "2026-09-02T12:10:00.000Z"),
        ),
        start=1,
    ):
        log = _append(
            log,
            LifecycleEventInput(
                kind="TRAIL_APPLIED",
                event_id=f"g5-trail-{i}",
                at=at,
                previous_stop=prev,
                new_stop=nxt,
            ),
        )
        assert not stop_worsens("LONG", prev, nxt)
        stops.append(Decimal(str(nxt)))
        assert stops[-1] >= stops[-2]

    stage, path = reduce_lifecycle_events(log)
    assert stage == "trailing"
    assert path == "trail"
    assert last_fill_price(log, stage=stage, lineage_path=path) == Decimal("120")

    log = _append(
        log,
        LifecycleEventInput(
            kind="T2_TRIGGERED",
            event_id="g5-t2-trig",
            at="2026-09-02T12:15:00.000Z",
        ),
    )
    log = _append(
        log,
        LifecycleEventInput(
            kind="T2_EXECUTED",
            event_id="g5-t2-exec",
            at="2026-09-02T12:45:00.000Z",
            quantity=3,
            price=125,
            fill_id="fill-g5-t2",
        ),
    )
    assert remaining_after_log(log) == Decimal("2")
    stage, path = reduce_lifecycle_events(log)
    assert stage == "t2_executed"
    assert path == "t2"
    assert last_fill_price(log, stage=stage, lineage_path=path) == Decimal("125")

    log = _append(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="g5-trail-3",
            at="2026-09-02T13:00:00.000Z",
            previous_stop=105,
            new_stop=110,
        ),
    )
    stage, path = reduce_lifecycle_events(log)
    assert stage == "trailing"
    assert path == "trail"
    # lineagePath flipped to trail, but history still has T2.
    assert "T2_EXECUTED" in _kinds(log)
    assert "T1_EXECUTED" in _kinds(log)
    assert sum(1 for e in log if e.kind == "TRAIL_APPLIED") == 3
    stops.append(Decimal("110"))
    assert stops == [Decimal("95"), Decimal("100"), Decimal("105"), Decimal("110")]
    assert last_fill_price(log, stage=stage, lineage_path=path) == Decimal("125")

    log = _append(
        log,
        LifecycleEventInput(
            kind="POSITION_CLOSED",
            event_id="g5-exit",
            at="2026-09-02T15:00:00.000Z",
            fill_id="fill-g5-exit",
            quantity=2,
            price=125,
        ),
    )
    stage, _ = reduce_lifecycle_events(log)
    assert stage == "closed"
    assert remaining_after_log(log) == 0
    acct = account_lifecycle_fills(log)
    assert acct.remaining == 0
    assert_equity_invariant(acct)


def test_v199_g6_t2_then_double_trail_exit() -> None:
    """G6: OPEN → T1 → T2 → TRAIL → TRAIL → EXIT."""
    log: list = []
    for kind in (
        "POSITION_OPENED",
        "T1_EXECUTED",
        "T2_TRIGGERED",
        "T2_EXECUTED",
    ):
        log = _append(log, LifecycleEventInput(kind=kind))  # type: ignore[arg-type]
    assert remaining_after_log(log) == LIFECYCLE_REMAINING_AFTER_T2

    log = _append(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="g6-trail-1",
            at="2026-09-02T13:00:00.000Z",
            previous_stop=98,
            new_stop=101,
        ),
    )
    log = _append(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="g6-trail-2",
            at="2026-09-02T13:10:00.000Z",
            previous_stop=101,
            new_stop=104,
        ),
    )
    stage, path = reduce_lifecycle_events(log)
    assert stage == "trailing"
    assert path == "trail"
    assert "T2_EXECUTED" in _kinds(log)
    assert sum(1 for e in log if e.kind == "TRAIL_APPLIED") == 2

    log = _append(
        log,
        LifecycleEventInput(
            kind="POSITION_CLOSED",
            event_id="g6-exit",
            at="2026-09-02T15:00:00.000Z",
            fill_id="fill-g6-exit",
        ),
    )
    assert reduce_lifecycle_events(log)[0] == "closed"
    assert remaining_after_log(log) == 0
    assert_equity_invariant(account_lifecycle_fills(log))


def test_v199_g7_anchor_documented() -> None:
    """G7 is not duplicated — see V199_G7_ANCHOR (V1.97 crash mid-pair)."""
    assert "test_crash_mid_pair_rolls_back_then_retry_exactly_once" in V199_G7_ANCHOR
    assert "test_lifecycle_t2_atomicity_v197" in V199_G7_ANCHOR


def test_v199_g8_stop_worsens_ratchet_long_short() -> None:
    """G8: LONG 100→105→110 OK, 110→105 DENY; SHORT 100→95→90 OK, 90→95 DENY."""
    # LONG ratchet
    assert stop_worsens("LONG", 100, 105) is False
    assert stop_worsens("LONG", 105, 110) is False
    assert stop_worsens("LONG", 110, 105) is True

    # T1 @ 120 so trail stops 105/110 stay below lastFill (LONG geometry).
    log = _append(
        [],
        LifecycleEventInput(
            kind="POSITION_OPENED",
            event_id="g8-l-open",
            quantity=10,
            price=100,
            fill_id="fill-g8-l-open",
        ),
    )
    log = _append(
        log,
        LifecycleEventInput(
            kind="T1_EXECUTED",
            event_id="g8-l-t1",
            at="2026-09-02T11:30:00.000Z",
            quantity=5,
            price=120,
            fill_id="fill-g8-l-t1",
        ),
    )
    log = _append(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="g8-l1",
            at="2026-09-02T12:00:00.000Z",
            previous_stop=100,
            new_stop=105,
        ),
    )
    log = _append(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="g8-l2",
            at="2026-09-02T12:10:00.000Z",
            previous_stop=105,
            new_stop=110,
        ),
    )
    deny = append_validated_lifecycle_event(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="g8-l-deny",
            at="2026-09-02T12:20:00.000Z",
            previous_stop=110,
            new_stop=105,
        ),
    )
    assert isinstance(deny, AppendFail)
    assert deny.error.code == "trail_relaxation"

    # SHORT ratchet
    assert stop_worsens("SHORT", 100, 95) is False
    assert stop_worsens("SHORT", 95, 90) is False
    assert stop_worsens("SHORT", 90, 95) is True

    # SHORT: T1 fill @ 80 so trail stops 95/90 stay above lastFill (SHORT geometry).
    slog: list = []
    open_s = append_validated_lifecycle_event(
        slog,
        LifecycleEventInput(
            kind="POSITION_OPENED",
            event_id="g8-s-open",
            side="SHORT",
            quantity=10,
            price=100,
            fill_id="fill-g8-s-open",
        ),
    )
    assert isinstance(open_s, AppendOk)
    slog = list(open_s.log)
    t1_s = append_validated_lifecycle_event(
        slog,
        LifecycleEventInput(
            kind="T1_EXECUTED",
            event_id="g8-s-t1",
            side="SHORT",
            at="2026-09-02T11:30:00.000Z",
            quantity=5,
            price=80,
            fill_id="fill-g8-s-t1",
        ),
    )
    assert isinstance(t1_s, AppendOk)
    slog = list(t1_s.log)
    for eid, prev, nxt, at in (
        ("g8-s1", 100, 95, "2026-09-02T12:00:00.000Z"),
        ("g8-s2", 95, 90, "2026-09-02T12:10:00.000Z"),
    ):
        ok = append_validated_lifecycle_event(
            slog,
            LifecycleEventInput(
                kind="TRAIL_APPLIED",
                event_id=eid,
                at=at,
                side="SHORT",
                previous_stop=prev,
                new_stop=nxt,
            ),
        )
        assert isinstance(ok, AppendOk), getattr(ok, "error", None)
        slog = list(ok.log)
    deny_s = append_validated_lifecycle_event(
        slog,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="g8-s-deny",
            at="2026-09-02T12:20:00.000Z",
            side="SHORT",
            previous_stop=90,
            new_stop=95,
        ),
    )
    assert isinstance(deny_s, AppendFail)
    assert deny_s.error.code == "trail_relaxation"


def test_v199_lineage_path_is_not_history() -> None:
    """P2: after T2 → TRAIL, lineagePath=trail but log still holds T2_EXECUTED."""
    log: list = []
    for kind in (
        "POSITION_OPENED",
        "T1_EXECUTED",
        "T2_TRIGGERED",
        "T2_EXECUTED",
    ):
        log = _append(log, LifecycleEventInput(kind=kind))  # type: ignore[arg-type]
    stage, path = reduce_lifecycle_events(log)
    assert stage == "t2_executed"
    assert path == "t2"

    log = _append(
        log,
        LifecycleEventInput(
            kind="TRAIL_APPLIED",
            event_id="lin-trail",
            at="2026-09-02T13:00:00.000Z",
            previous_stop=98,
            new_stop=101,
        ),
    )
    stage, path = reduce_lifecycle_events(log)
    assert stage == "trailing"
    assert path == "trail"
    assert any(e.kind == "T2_EXECUTED" for e in log)
    assert any(e.kind == "T1_EXECUTED" for e in log)
    # lineage must not erase multi-fact history
    assert _kinds(log).count("T2_EXECUTED") == 1
    assert _kinds(log).count("TRAIL_APPLIED") == 1
