"""ExecutionPlan F4 — PAPER pipeline (ADR-032). ≠ broker ≠ ExecuteTrade."""

from bolsa_analytics.cognitive.execution_plan import (
    attempt_execution_broker,
    build_execution_plan_from_exit_plan,
    stage_execution_journal,
    stage_execution_replay,
    stage_execution_validate,
)
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


def _exit_triggered_full():
    exit_plan = build_exit_plan_from_position(
        _open_long(),
        mark_price=95.0,
        exit_plan_id="ex-1",
        at="2026-08-25T16:00:00Z",
    )
    assert exit_plan is not None
    assert exit_plan.status == "TRIGGERED"
    assert exit_plan.suggested_action == "full_exit"
    return exit_plan


def test_paper_ready_market_exit() -> None:
    plan = build_execution_plan_from_exit_plan(
        _exit_triggered_full(),
        execution_plan_id="ep-1",
        mark_price=95.0,
        at="2026-08-25T16:05:00Z",
    )
    assert plan is not None
    assert plan.execution_plan_id == "ep-1"
    assert plan.exit_plan_id == "ex-1"
    assert plan.position_id == "pos-1"
    assert plan.venue == "PAPER"
    assert plan.status == "PAPER_READY"
    assert plan.intent_kind == "market_exit"
    assert plan.side == "sell"
    assert plan.quantity == 10.0
    assert plan.source_reason == "STRUCTURAL_STOP"
    assert plan.blocked_reason is None
    assert plan.paper_projection is not None
    assert plan.paper_projection.price == 95.0
    assert plan.paper_projection.qty == 10.0
    d = plan.to_dict()
    assert d["status"] == "PAPER_READY"
    assert d["venue"] == "PAPER"


def test_reduce_from_target1() -> None:
    exit_plan = build_exit_plan_from_position(
        _open_long(), mark_price=105.0, exit_plan_id="ex-t1"
    )
    plan = build_execution_plan_from_exit_plan(exit_plan)
    assert plan is not None
    assert plan.intent_kind == "reduce"
    assert plan.status == "PAPER_READY"
    assert plan.quantity == 5.0


def test_idle_null() -> None:
    idle = build_exit_plan_from_position(_open_long(), exit_plan_id="ex-idle")
    assert idle is not None
    assert idle.status == "IDLE"
    assert build_execution_plan_from_exit_plan(idle) is None


def test_hint_time_stop_null() -> None:
    hint = build_exit_plan_from_position(
        _open_long(),
        now="2026-08-26T00:00:00Z",
        expires_at="2026-08-25T23:00:00Z",
    )
    assert hint is not None
    assert hint.status == "HINT"
    assert build_execution_plan_from_exit_plan(hint) is None


def test_armed_protect_draft() -> None:
    armed = build_exit_plan_from_position(
        _open_long(),
        trail_hint=True,
        trail_stop=100.0,
        exit_plan_id="ex-trail",
    )
    assert armed is not None
    assert armed.status == "ARMED"
    plan = build_execution_plan_from_exit_plan(armed)
    assert plan is not None
    assert plan.status == "DRAFT"
    assert plan.intent_kind == "stop_amend"
    assert plan.side == "none"
    assert plan.limit_price == 100.0
    assert plan.venue == "PAPER"


def test_force_broker_blocked() -> None:
    plan = build_execution_plan_from_exit_plan(
        _exit_triggered_full(),
        force_venue="BROKER",
        execution_plan_id="ep-broker",
    )
    assert plan is not None
    assert plan.status == "BLOCKED"
    assert plan.venue == "BROKER"
    assert plan.blocked_reason == "broker_not_allowed"
    assert plan.intent_kind == "market_exit"


def test_null_exit() -> None:
    assert build_execution_plan_from_exit_plan(None) is None


def test_pipeline_stages() -> None:
    ready = build_execution_plan_from_exit_plan(
        _exit_triggered_full(), execution_plan_id="ep-pipe"
    )
    assert ready is not None
    j = stage_execution_journal(ready, "j-1", at="2026-08-25T17:00:00Z")
    assert j is not None
    assert j.status == "JOURNALED"
    assert j.journal_ref == "j-1"
    r = stage_execution_replay(j, "r-1")
    assert r is not None
    assert r.status == "REPLAYED"
    v = stage_execution_validate(r, "v-1")
    assert v is not None
    assert v.status == "VALIDATED"
    assert v.venue == "PAPER"


def test_stages_sequential() -> None:
    ready = build_execution_plan_from_exit_plan(_exit_triggered_full())
    assert stage_execution_replay(ready) is None
    assert stage_execution_validate(ready) is None


def test_draft_cannot_journal() -> None:
    armed = build_exit_plan_from_position(
        _open_long(), trail_hint=True, trail_stop=100.0
    )
    draft = build_execution_plan_from_exit_plan(armed)
    assert draft is not None
    assert draft.status == "DRAFT"
    assert stage_execution_journal(draft) is None


def test_attempt_broker_blocked() -> None:
    ready = build_execution_plan_from_exit_plan(_exit_triggered_full())
    blocked = attempt_execution_broker(ready)
    assert blocked is not None
    assert blocked.status == "BLOCKED"
    assert blocked.blocked_reason == "broker_not_allowed"
    assert blocked.venue == "BROKER"
    pipe = stage_execution_validate(
        stage_execution_replay(stage_execution_journal(ready))
    )
    from_validated = attempt_execution_broker(pipe)
    assert from_validated is not None
    assert from_validated.status == "BLOCKED"
    assert from_validated.blocked_reason == "broker_not_allowed"
