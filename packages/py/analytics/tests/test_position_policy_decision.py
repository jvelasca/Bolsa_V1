"""V1.44 — PositionPolicyDecision. ≠ auto-exit ≠ Router."""

from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.operating_policy import resolve_operating_policy
from bolsa_analytics.cognitive.position_policy_decision import decide_position_policy
from bolsa_analytics.cognitive.position_revision import revision_origin_from_exit_reason
from bolsa_analytics.cognitive.position_state import build_position_state_from_fill


def _plan() -> dict[str, object]:
    return {
        "decisionId": "dec-pp",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
    }


def _open():
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-31T15:00:00Z",
        position_id="pos-pp",
    )
    assert pos is not None
    return pos


def test_moderate_t1_reduce_30() -> None:
    pos = _open()
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=110.0, at="2026-08-31T15:00:00Z", exit_policy=policy.exit
    )
    d = decide_position_policy(
        pos, exit_plan, policy, session="open", stale=False, as_of="2026-08-31T15:00:00Z"
    )
    assert d.verdict == "REDUCE"
    assert d.reason_code == "TARGET_1"
    assert d.quantity == 3.0
    assert d.policy_id == "moderate"
    assert d.authorization == "policy"


def test_conservative_t2_exit() -> None:
    pos = _open()
    policy = resolve_operating_policy("conservative")
    exit_plan = build_exit_plan_from_position(pos, mark_price=120.0)
    d = decide_position_policy(pos, exit_plan, policy, session="open")
    assert d.verdict == "EXIT"
    assert d.reason_code == "TARGET_2"
    assert d.quantity == 10.0


def test_aggressive_t1_hold() -> None:
    pos = _open()
    policy = resolve_operating_policy("aggressive_swing")
    exit_plan = build_exit_plan_from_position(pos, mark_price=110.0)
    d = decide_position_policy(pos, exit_plan, policy, session="open")
    assert d.verdict == "HOLD"


def test_trail_origin_and_verdict() -> None:
    pos = _open()
    exit_plan = build_exit_plan_from_position(
        pos, trail_hint=True, trail_stop=98.0
    )
    assert revision_origin_from_exit_reason(exit_plan.primary_reason) == "trail"
    d = decide_position_policy(
        pos, exit_plan, resolve_operating_policy("moderate"), session="open"
    )
    assert d.verdict == "TRAIL"
    assert d.new_stop == 98.0


def test_closed_market_t1_queues() -> None:
    pos = _open()
    exit_plan = build_exit_plan_from_position(pos, mark_price=110.0)
    d = decide_position_policy(
        pos,
        exit_plan,
        resolve_operating_policy("moderate"),
        session="closed",
    )
    assert d.verdict == "HOLD"
    assert d.defer_reason == "queue_next_session"


def test_stale_t1_hold_stop_exit() -> None:
    pos = _open()
    policy = resolve_operating_policy("moderate")
    t1 = decide_position_policy(
        pos,
        build_exit_plan_from_position(pos, mark_price=110.0),
        policy,
        session="open",
        stale=True,
    )
    assert t1.defer_reason == "data_stale"
    stop = decide_position_policy(
        pos,
        build_exit_plan_from_position(pos, mark_price=94.0),
        policy,
        session="open",
        stale=True,
    )
    assert stop.verdict == "EXIT"
    assert stop.reason_code == "STRUCTURAL_STOP"


def test_t1_t2_same_tick_target_2_wins() -> None:
    pos = _open()
    exit_plan = build_exit_plan_from_position(pos, mark_price=120.0)
    assert exit_plan is not None
    assert exit_plan.primary_reason == "TARGET_2"
    assert "TARGET_1" not in exit_plan.reasons
    d = decide_position_policy(
        pos, exit_plan, resolve_operating_policy("moderate"), session="open"
    )
    assert d.reason_code == "TARGET_2"
