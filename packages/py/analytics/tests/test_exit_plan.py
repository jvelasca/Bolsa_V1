"""ExitPlan F3 — razones canónicas (ADR-032). ≠ execution ≠ thin."""

from bolsa_analytics.cognitive.exit_plan import (
    EXIT_REASON_PRECEDENCE,
    build_exit_plan_from_position,
)
from bolsa_analytics.cognitive.position_state import (
    apply_position_reduce,
    build_position_state_from_fill,
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


def test_idle_without_signals() -> None:
    plan = build_exit_plan_from_position(
        _open_long(),
        exit_plan_id="ex-1",
        at="2026-08-25T16:00:00Z",
    )
    assert plan is not None
    assert plan.exit_plan_id == "ex-1"
    assert plan.position_id == "pos-1"
    assert plan.trade_plan_id == "dec-1"
    assert plan.status == "IDLE"
    assert plan.reasons == ()
    assert plan.primary_reason is None
    assert plan.suggested_action == "hold"
    assert plan.suggested_qty is None
    assert plan.created_at == "2026-08-25T16:00:00Z"
    d = plan.to_dict()
    assert d["status"] == "IDLE"
    assert d["primaryReason"] is None


def test_null_without_position() -> None:
    assert build_exit_plan_from_position(None) is None


def test_closed_position_done_no_writeback() -> None:
    closed = apply_position_reduce(_open_long(), 10.0, exit_price=100.0)
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed.exit_status == "done"
    plan = build_exit_plan_from_position(
        closed, mark_price=90.0, exit_plan_id="ex-done"
    )
    assert plan is not None
    assert plan.status == "DONE"
    assert plan.suggested_action == "hold"
    assert closed.exit_status == "done"


def test_structural_stop_triggered() -> None:
    plan = build_exit_plan_from_position(
        _open_long(), mark_price=95.0, exit_plan_id="ex-stop"
    )
    assert plan is not None
    assert plan.primary_reason == "STRUCTURAL_STOP"
    assert plan.status == "TRIGGERED"
    assert plan.suggested_action == "full_exit"
    assert plan.suggested_qty == 10.0


def test_target1_reduce() -> None:
    plan = build_exit_plan_from_position(
        _open_long(), mark_price=105.0, exit_plan_id="ex-t1"
    )
    assert plan is not None
    assert plan.primary_reason == "TARGET_1"
    assert plan.status == "TRIGGERED"
    assert plan.suggested_action == "reduce"
    assert plan.suggested_qty == 5.0


def test_target2_subsumes_t1_full_exit() -> None:
    plan = build_exit_plan_from_position(
        _open_long(), mark_price=110.0, exit_plan_id="ex-t2"
    )
    assert plan is not None
    assert plan.primary_reason == "TARGET_2"
    assert "TARGET_2" in plan.reasons
    assert "TARGET_1" not in plan.reasons
    assert plan.suggested_action == "full_exit"
    assert plan.suggested_qty == 10.0


def test_target2_alone_full_exit() -> None:
    pos = build_position_state_from_fill(
        _plan(target1=120.0, target2=110.0),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-t2only",
    )
    assert pos is not None
    plan = build_exit_plan_from_position(pos, mark_price=110.0)
    assert plan is not None
    assert plan.primary_reason == "TARGET_2"
    assert plan.suggested_action == "full_exit"
    assert plan.suggested_qty == 10.0


def test_manual_beats_structural_stop() -> None:
    plan = build_exit_plan_from_position(
        _open_long(),
        mark_price=90.0,
        manual=True,
        exit_plan_id="ex-man",
    )
    assert plan is not None
    assert plan.primary_reason == "MANUAL"
    assert plan.reasons[0] == "MANUAL"
    assert "STRUCTURAL_STOP" in plan.reasons
    assert EXIT_REASON_PRECEDENCE[0] == "MANUAL"


def test_explicit_thesis_and_portfolio() -> None:
    idle = build_exit_plan_from_position(_open_long(), mark_price=101.0)
    assert idle is not None
    assert idle.reasons == ()
    thesis = build_exit_plan_from_position(_open_long(), thesis_invalid=True)
    assert thesis is not None
    assert thesis.primary_reason == "THESIS_INVALIDATION"
    assert thesis.status == "TRIGGERED"
    port = build_exit_plan_from_position(_open_long(), portfolio_risk=True)
    assert port is not None
    assert port.primary_reason == "PORTFOLIO_RISK"


def test_trail_armed_protect() -> None:
    plan = build_exit_plan_from_position(
        _open_long(),
        trail_hint=True,
        trail_stop=100.0,
        exit_plan_id="ex-trail",
    )
    assert plan is not None
    assert plan.primary_reason == "TRAIL"
    assert plan.status == "ARMED"
    assert plan.suggested_action == "protect"
    assert plan.suggested_stop == 100.0


def test_trail_hint_without_stop() -> None:
    plan = build_exit_plan_from_position(_open_long(), trail_hint=True)
    assert plan is not None
    assert plan.status == "HINT"
    assert plan.suggested_action == "protect"
    assert plan.suggested_stop is None


def test_time_stop_hint() -> None:
    plan = build_exit_plan_from_position(
        _open_long(),
        now="2026-08-26T00:00:00Z",
        expires_at="2026-08-25T23:00:00Z",
    )
    assert plan is not None
    assert plan.primary_reason == "TIME_STOP"
    assert plan.status == "HINT"
    assert plan.suggested_action == "full_exit"
    assert plan.suggested_qty == 10.0


def test_no_time_stop_without_both_timestamps() -> None:
    plan = build_exit_plan_from_position(
        _open_long(), now="2026-08-26T00:00:00Z"
    )
    assert plan is not None
    assert plan.reasons == ()
    assert plan.status == "IDLE"
