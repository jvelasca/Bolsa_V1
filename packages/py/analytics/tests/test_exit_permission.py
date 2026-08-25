"""ExitPermission — veto salida (ADR-032). ≠ check_opening ≠ auto-exit."""

from dataclasses import replace

from bolsa_analytics.cognitive.execution_plan import build_execution_plan_from_exit_plan
from bolsa_analytics.cognitive.exit_permission import check_exit_permission
from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.position_state import build_position_state_from_fill


def _plan() -> dict[str, object]:
    return {
        "decisionId": "dec-1",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
    }


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


def _exit_triggered():
    exit_plan = build_exit_plan_from_position(
        _open_long(),
        mark_price=95.0,
        exit_plan_id="ex-1",
        at="2026-08-25T16:00:00Z",
    )
    assert exit_plan is not None
    return exit_plan


def test_allow_triggered_full_exit() -> None:
    perm = check_exit_permission(_exit_triggered(), at="2026-08-25T16:10:00Z")
    assert perm.verdict == "ALLOW"
    assert perm.allowed is True
    assert perm.reasons == ()
    assert perm.action == "full_exit"
    assert perm.exit_plan_id == "ex-1"
    assert perm.position_id == "pos-1"
    d = perm.to_dict()
    assert d["verdict"] == "ALLOW"


def test_allow_reduce() -> None:
    exit_plan = build_exit_plan_from_position(_open_long(), mark_price=105.0)
    perm = check_exit_permission(exit_plan)
    assert perm.allowed is True
    assert perm.action == "reduce"


def test_allow_protect() -> None:
    exit_plan = build_exit_plan_from_position(
        _open_long(), trail_hint=True, trail_stop=100.0
    )
    perm = check_exit_permission(exit_plan)
    assert perm.allowed is True
    assert perm.action == "protect"


def test_deny_missing() -> None:
    perm = check_exit_permission(None)
    assert perm.verdict == "DENY"
    assert perm.reasons == ("missing_exit_plan",)
    assert perm.action == "none"


def test_deny_idle() -> None:
    idle = build_exit_plan_from_position(_open_long())
    assert idle is not None
    assert idle.status == "IDLE"
    perm = check_exit_permission(idle)
    assert perm.reasons == ("not_actionable",)


def test_deny_hint() -> None:
    hint = build_exit_plan_from_position(
        _open_long(),
        now="2026-08-26T00:00:00Z",
        expires_at="2026-08-25T23:00:00Z",
    )
    assert hint is not None
    assert hint.status == "HINT"
    perm = check_exit_permission(hint)
    assert perm.reasons == ("not_actionable",)


def test_deny_position_closed() -> None:
    perm = check_exit_permission(_exit_triggered(), position_closed=True)
    assert perm.reasons == ("position_closed",)


def test_allow_human_full_exit_with_kill_switch() -> None:
    perm = check_exit_permission(_exit_triggered(), kill_switch=True)
    assert perm.verdict == "ALLOW"
    assert perm.action == "full_exit"


def test_allow_human_protect_with_kill_switch() -> None:
    exit_plan = build_exit_plan_from_position(
        _open_long(), trail_hint=True, trail_stop=100.0
    )
    perm = check_exit_permission(exit_plan, kill_switch=True)
    assert perm.allowed is True
    assert perm.action == "protect"


def test_deny_kill_switch_for_auto() -> None:
    perm = check_exit_permission(
        _exit_triggered(),
        kill_switch=True,
        auto_execute=True,
        paper_d_execute=True,
    )
    assert perm.reasons == ("kill_switch",)


def test_deny_broker_requested() -> None:
    perm = check_exit_permission(_exit_triggered(), broker_requested=True)
    assert perm.reasons == ("broker_not_allowed",)


def test_deny_broker_execution_plan() -> None:
    exec_plan = build_execution_plan_from_exit_plan(
        _exit_triggered(), force_venue="BROKER"
    )
    perm = check_exit_permission(_exit_triggered(), execution_plan=exec_plan)
    assert perm.reasons == ("broker_not_allowed",)


def test_deny_paper_auto_env() -> None:
    perm = check_exit_permission(
        _exit_triggered(), auto_execute=True, paper_d_execute=False
    )
    assert perm.reasons == ("paper_auto_env_blocked",)


def test_allow_auto_with_paper_d() -> None:
    perm = check_exit_permission(
        _exit_triggered(), auto_execute=True, paper_d_execute=True
    )
    assert perm.allowed is True


def test_deny_execution_blocked_paper() -> None:
    ready = build_execution_plan_from_exit_plan(_exit_triggered())
    assert ready is not None
    weird = replace(
        ready, status="BLOCKED", venue="PAPER", blocked_reason=None
    )
    perm = check_exit_permission(_exit_triggered(), execution_plan=weird)
    assert perm.reasons == ("execution_blocked",)


def test_kill_precedes_not_actionable() -> None:
    idle = build_exit_plan_from_position(_open_long())
    perm = check_exit_permission(idle, kill_switch=True)
    assert perm.reasons == ("kill_switch",)
