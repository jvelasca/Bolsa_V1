"""ExitPlan F3 — razones canónicas (ADR-032). ≠ execution ≠ thin."""

from bolsa_analytics.cognitive.exit_plan import (
    EXIT_REASON_PRECEDENCE,
    build_exit_plan_from_position,
    is_thesis_invalidated,
)
from bolsa_analytics.cognitive.position_state import (
    apply_position_mark,
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


# --------------------------------------------------------------------------------------
# V2.42 slice 2b — horizonte de mantenimiento (E1) e invalidación de tesis (E3)
# --------------------------------------------------------------------------------------


def test_holding_horizon_matches_policy_templates() -> None:
    """D1: el horizonte sale del MISMO modelo de plantilla, sin tabla paralela."""
    from bolsa_analytics.cognitive.exit_policy import resolve_holding_horizon
    from bolsa_analytics.cognitive.trading_policy_templates import POLICY_TEMPLATES

    for template_id, policy in POLICY_TEMPLATES.items():
        horizon = resolve_holding_horizon(template_id)
        assert horizon.max_holding_period_days == policy.horizon.max_holding_period_days
        assert (
            horizon.min_holding_period_minutes == policy.horizon.min_holding_period_minutes
        ), template_id
    # Ausencia/plantilla desconocida ⇒ el default DECLARADO (moderate), nunca None.
    fallback = POLICY_TEMPLATES["moderate"].horizon
    assert resolve_holding_horizon(None).max_holding_period_days == fallback.max_holding_period_days
    assert resolve_holding_horizon("nope").max_holding_period_days == fallback.max_holding_period_days


def test_holding_deadline_is_frozen_at_birth() -> None:
    """E1: el techo se congela al nacer (created_at + días) y sobrevive al round-trip."""
    from bolsa_analytics.cognitive.exit_policy import resolve_holding_horizon
    from bolsa_analytics.cognitive.position_state import position_state_from_dict

    days = resolve_holding_horizon("moderate").max_holding_period_days
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-25T15:00:00Z",
        position_id="pos-deadline",
        max_holding_period_days=days,
    )
    assert pos is not None
    assert pos.holding_deadline_at == "2026-10-09T15:00:00Z"
    restored = position_state_from_dict(dict(pos.to_dict()))
    assert restored is not None
    assert restored.holding_deadline_at == "2026-10-09T15:00:00Z"
    # Sin días declarados NO se inventa techo (TIME_STOP queda inalcanzable, no adivinado).
    assert _open_long().holding_deadline_at is None


def test_frozen_deadline_becomes_time_stop() -> None:
    """E1: el techo congelado, pasado a la gestión, es lo que enciende ``TIME_STOP``."""
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-25T15:00:00Z",
        position_id="pos-deadline-2",
        max_holding_period_days=5,
    )
    assert pos is not None
    assert pos.holding_deadline_at == "2026-08-30T15:00:00Z"
    before = build_exit_plan_from_position(
        pos, now="2026-08-29T15:00:00Z", expires_at=pos.holding_deadline_at
    )
    assert before is not None and before.primary_reason is None
    after = build_exit_plan_from_position(
        pos, now="2026-08-30T15:00:00Z", expires_at=pos.holding_deadline_at
    )
    assert after is not None
    assert after.primary_reason == "TIME_STOP"
    assert after.suggested_action == "full_exit"
    assert after.suggested_qty == 10.0


def test_thesis_invalidation_level_is_frozen_from_plan_or_stop() -> None:
    """E3: el nivel congelado es el que declare el plan, o la regla estructural."""
    declared = build_position_state_from_fill(
        _plan(invalidationPrice=96.5),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-inv-declared",
    )
    assert declared is not None
    assert declared.invalidation_price == 96.5
    structural = _open_long()
    assert structural.invalidation_price == 95.0


def test_thesis_not_invalidated_without_declared_level() -> None:
    """Sin nivel declarado la invalidación NO se inventa (fail-closed)."""
    pos = build_position_state_from_fill(
        _plan(structuralStop=None),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-no-level",
    )
    assert pos is not None
    assert pos.invalidation_price is None
    assert is_thesis_invalidated(pos, mark_price=10.0) is False


def test_thesis_invalidated_when_frozen_level_is_crossed() -> None:
    pos = _open_long()
    assert is_thesis_invalidated(pos, mark_price=96.0) is False
    assert is_thesis_invalidated(pos, mark_price=95.0) is True
    assert is_thesis_invalidated(pos, mark_price=94.0) is True


def test_thesis_invalidation_survives_recovery_via_persisted_mae() -> None:
    """E3: un stop que no llegó a materializarse no se "des-hace" si el precio se recupera.

    El peor adverso queda en ``mfeMae`` (JSONB) y la invalidación sigue confirmada tras un
    reinicio aunque el mark actual esté por encima del nivel.
    """
    from bolsa_analytics.cognitive.position_state import position_state_from_dict

    pos = _open_long()
    dipped = apply_position_mark(pos, 94.0, at="2026-08-25T16:00:00Z")
    assert dipped is not None
    recovered = apply_position_mark(dipped, 108.0, at="2026-08-25T17:00:00Z")
    assert recovered is not None
    assert is_thesis_invalidated(recovered, mark_price=108.0) is True
    # Y sobrevive al reinicio: la confirmación vive en el hecho persistido, no en memoria.
    restored = position_state_from_dict(dict(recovered.to_dict()))
    assert restored is not None
    assert is_thesis_invalidated(restored, mark_price=108.0) is True


def test_thesis_invalidated_for_short_direction() -> None:
    """E3: la simetría se respeta (short = mark por ENCIMA del nivel)."""
    short = build_position_state_from_fill(
        _plan(direction="short", structuralStop=105.0),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="s-inv",
    )
    assert short is not None
    assert short.invalidation_price == 105.0
    assert is_thesis_invalidated(short, mark_price=104.0) is False
    assert is_thesis_invalidated(short, mark_price=105.0) is True
