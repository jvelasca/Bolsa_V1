"""PositionManager — PositionState + ExitPlan + PositionDecision (AUTO 2.0 · P1)."""

from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_application.position_manager import REGIME_EXIT, manage_position


def _open_long(mark: float = 100.0):
    plan = {
        "decisionId": "dec-1",
        "instrumentId": "AAPL",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
    }
    return build_position_state_from_fill(
        plan, fill_price=100.0, fill_quantity=10.0, position_id="pos-1"
    )


def test_hold_when_no_exit_signal() -> None:
    result = manage_position(_open_long(), mark_price=101.0, regime="BULL_TREND")
    assert result is not None
    assert result.order_action == "hold"
    assert result.order_qty is None
    assert result.exit_reasons == ()
    assert result.decision.action == "HOLD"


def test_structural_stop_sells_all() -> None:
    result = manage_position(_open_long(), mark_price=95.0, regime="BULL_TREND")
    assert result is not None
    assert result.order_action == "sell"
    assert result.order_qty == 10.0
    assert "structural_stop" in result.exit_reasons


def test_target1_reduces_partial() -> None:
    # mark >= T1 (105) ⇒ TARGET_1 ⇒ reduce 30% (moderate) de 10 ⇒ 3.
    result = manage_position(
        _open_long(), mark_price=105.0, regime="BULL_TREND", template_id="moderate"
    )
    assert result is not None
    assert result.order_action == "reduce"
    assert result.order_qty == 3.0
    assert "target_1" in result.exit_reasons


def test_thesis_invalidation_flagged_for_review() -> None:
    # El spine cognitivo es conservador: thesis invalidation ⇒ REVIEW (human-in-loop),
    # no venta automática. La salida queda auditada en exit_reasons.
    result = manage_position(
        _open_long(), mark_price=101.0, thesis_invalid=True, regime="BULL_TREND"
    )
    assert result is not None
    assert result.order_action == "hold"
    assert result.decision.action == "REVIEW"
    assert result.attention == "URGENT"
    assert "thesis_invalidation" in result.exit_reasons


def test_regime_exit_only_forces_full_sell() -> None:
    result = manage_position(_open_long(), mark_price=101.0, regime="UNKNOWN")
    assert result is not None
    assert result.order_action == "sell"
    assert result.order_qty == 10.0
    assert REGIME_EXIT in result.exit_reasons


def test_regime_exit_only_overrides_take_profit() -> None:
    """V2.40.1: EXIT_ONLY tiene precedencia ABSOLUTA sobre el take-profit.

    Antes solo se forzaba la venta total cuando la decisión era ``hold``, así que un
    ``TAKE_PROFIT`` (mark ≥ T1) prevalecía y dejaba el 70% de la posición abierta contra
    la política declarada (solo SIM/cuenta simulada, pero riesgo real de diseño).
    """
    result = manage_position(
        _open_long(), mark_price=105.0, regime="UNKNOWN", template_id="moderate"
    )
    assert result is not None
    assert result.order_action == "sell"
    assert result.order_qty == 10.0
    assert REGIME_EXIT in result.exit_reasons


def test_time_stop_exits() -> None:
    result = manage_position(
        _open_long(),
        mark_price=101.0,
        regime="BULL_TREND",
        now="2026-09-15T10:00:00Z",
        expires_at="2026-09-15T09:00:00Z",
    )
    assert result is not None
    assert result.order_action == "sell"
    assert "time_stop" in result.exit_reasons


def test_closed_or_none_position_returns_none() -> None:
    assert manage_position(None, mark_price=100.0) is None
    closed = build_position_state_from_fill(
        {
            "decisionId": "dec-1",
            "instrumentId": "AAPL",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
        },
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )
    from bolsa_analytics.cognitive.position_state import apply_position_reduce

    closed_pos = apply_position_reduce(closed, 10.0, exit_price=100.0)
    assert closed_pos is not None
    assert manage_position(closed_pos, mark_price=100.0) is None


def test_result_to_dict_shape() -> None:
    result = manage_position(_open_long(), mark_price=95.0, regime="BULL_TREND")
    assert result is not None
    d = result.to_dict()
    assert d["positionId"] == "pos-1"
    assert d["orderAction"] == "sell"
    assert d["positionDecision"]["action"] == "EXIT"
    assert "position" in d
