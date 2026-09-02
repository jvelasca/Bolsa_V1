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


def test_gp_v171_parity_t2_executed() -> None:
    from bolsa_analytics.cognitive.position_state import apply_target_leg

    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )
    assert pos is not None
    pos = apply_target_leg(pos, which="t1", status="executed", fill_id="tx-t1")
    pos = apply_target_leg(pos, which="t2", status="executed", fill_id="tx-t2")
    view = build_position_operational_view(pos)
    assert view["operatingState"] == "T2_EXECUTED"
    assert view["primaryAction"] == "MONITOR"
    assert view["levels"]["target2"] == 110.0


def test_gp_v171_parity_recon_drift() -> None:
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )
    assert pos is not None
    view = build_position_operational_view(pos, recon_status="drift")
    assert view["operatingState"] == "RECONCILIATION_DRIFT"
    assert view["primaryAction"] == "BLOQUEADO"


def test_gp_v171_parity_stop_history_five_origins() -> None:
    from dataclasses import replace

    from bolsa_analytics.cognitive.position_revision import PositionRevision

    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-1",
    )
    assert pos is not None
    origins = ("protect", "trail", "reduce", "override", "stop")
    revs = tuple(
        PositionRevision(
            revision_id=f"r-{origin}",
            at=f"2026-09-01T10:0{i}:00Z",
            previous_stop=95.0 + i,
            next_stop=96.0 + i,
            previous_status="OPEN",
            next_status="OPEN",
            origin=origin,
            reason=origin,
        )
        for i, origin in enumerate(origins)
    )
    view = build_position_operational_view(replace(pos, revisions=revs))
    hist = [
        h
        for h in view["stopHistory"]
        if h["origin"] not in ("birth", "current")
    ]
    assert [h["origin"] for h in hist] == list(origins)
    assert [h["label"] for h in hist] == [
        "Protect",
        "Trail #1",
        "Reduce",
        "Ajuste manual",
        "Stop",
    ]


def test_gp_v171_invalid_revision_origin_dropped() -> None:
    from bolsa_analytics.cognitive.position_revision import revisions_from_raw

    kept = revisions_from_raw(
        [
            {
                "revisionId": "r-bad",
                "at": "2026-09-01T10:00:00Z",
                "origin": "not-a-real-origin",
                "nextStop": 96,
            },
            {
                "revisionId": "r-ok",
                "at": "2026-09-01T10:00:00Z",
                "origin": "protect",
                "nextStop": 98,
            },
        ]
    )
    assert len(kept) == 1
    assert kept[0].origin == "protect"
