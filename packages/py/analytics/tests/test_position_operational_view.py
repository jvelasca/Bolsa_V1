"""V1.65 — PositionOperationalView identity + lineage tests."""

from bolsa_analytics.cognitive.position_operational_view import (
    build_position_operational_view,
)
from bolsa_analytics.cognitive.position_state import (
    PositionState,
    build_position_state_from_fill,
)


def _plan(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "decisionId": "DEC-1",
        "tradePlanId": "TP-1",
        "instrumentId": "AAPL",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
    }
    base.update(overrides)
    return base


def test_birth_separates_decision_id_and_trade_plan_id() -> None:
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )
    assert pos is not None
    assert pos.decision_id == "DEC-1"
    assert pos.trade_plan_id == "TP-1"
    d = pos.to_dict()
    assert d["decisionId"] == "DEC-1"
    assert d["tradePlanId"] == "TP-1"


def test_pov_preserves_decision_id_distinct_from_trade_plan_id() -> None:
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )
    assert pos is not None
    view = build_position_operational_view(pos)
    assert view["decisionId"] == "DEC-1"
    assert view["tradePlanId"] == "TP-1"
    assert view["lineageCollapsed"] is False


def test_pov_legacy_without_decision_id_is_lineage_collapsed() -> None:
    pos = PositionState(
        position_id="pos-legacy",
        trade_plan_id="TP-LEG",
        instrument_id="AAPL",
        direction="long",
        status="OPEN",
        planned_entry=100.0,
        actual_entry=100.0,
        initial_stop=95.0,
        current_stop=95.0,
        target1=105.0,
        target2=110.0,
        quantity=10.0,
        remaining_quantity=10.0,
        initial_risk=5.0,
        realized_r=0.0,
        unrealized_r=None,
        mfe_mae={"mfeR": None, "maeR": None, "source": "none"},
        thesis_health={"status": "none"},
        protection_state={"status": "none"},
        trailing={"status": "none"},
        exit_status="none",
        created_at="2026-09-01T09:00:00Z",
        updated_at="2026-09-01T10:00:00Z",
    )
    view = build_position_operational_view(pos)
    assert view["decisionId"] is None
    assert view["tradePlanId"] == "TP-LEG"
    assert view["lineageCollapsed"] is True
