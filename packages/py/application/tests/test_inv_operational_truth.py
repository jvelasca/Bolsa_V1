"""V1.57 — INV-01..10 Operational Truth (predicados nombrados).

Reutiliza DEX-5, clamp_stop_not_worsen, DEX-3 clear, _advance_target_leg.
No sustituye Golden Session GP-SESSION-*.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from bolsa_analytics.cognitive.exit_permission import check_exit_permission
from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.operational_incident import (
    can_clear,
    clear_incident,
    open_incident,
    resolve_incident,
)
from bolsa_analytics.cognitive.operational_invariants import (
    closed_remaining_zero,
    executed_leg_has_fill,
    mapping_unchanged,
    qty_non_negative,
)
from bolsa_analytics.cognitive.position_state import (
    apply_position_current_stop,
    apply_position_reduce,
    apply_target_leg,
    build_position_state_from_fill,
    clamp_stop_not_worsen,
    does_stop_worsen,
)
from bolsa_analytics.cognitive.risk_signature import evaluate_risk_signature
from bolsa_application.operational_context import resolve_position_operating_state


def _plan(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "decisionId": "dec-1",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
        "quantity": 10.0,
        "riskAmount": 50.0,
        "initialRiskR": 5.0,
    }
    base.update(overrides)
    return base


def _open_long():
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-01T09:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    return pos


def test_inv_01_quantity_non_negative() -> None:
    assert qty_non_negative(0.0) is True
    assert qty_non_negative(10.0) is True
    assert qty_non_negative(-0.01) is False
    assert qty_non_negative(float("nan")) is False
    assert qty_non_negative(_open_long().quantity) is True


def test_inv_02_closed_remaining_zero() -> None:
    pos = _open_long()
    closed = apply_position_reduce(pos, 10.0, exit_price=95.0)
    assert closed is not None
    assert closed.status == "CLOSED"
    assert closed_remaining_zero(
        status=closed.status, remaining=closed.remaining_quantity
    )
    assert closed.remaining_quantity == 0.0
    assert qty_non_negative(closed.quantity) is True
    assert not closed_remaining_zero(status="CLOSED", remaining=10.0)


def test_inv_03_t1_executed_has_fill() -> None:
    pos = _open_long()
    reduced = apply_position_reduce(
        pos,
        3.0,
        exit_price=110.0,
        mark_target1_achieved=True,
        fill_id="tx-t1",
    )
    assert reduced is not None
    assert reduced.target1_leg is not None
    assert reduced.target1_leg.status == "executed"
    assert executed_leg_has_fill(
        reduced.target1_leg.status, reduced.target1_leg.fill_id
    )
    assert reduced.target1_leg.fill_id == "tx-t1"
    assert executed_leg_has_fill("executed", None) is False
    assert executed_leg_has_fill("pending", None) is True


def test_inv_04_t2_executed_has_fill() -> None:
    pos = _open_long()
    after_t1 = apply_position_reduce(
        pos,
        3.0,
        exit_price=110.0,
        mark_target1_achieved=True,
        fill_id="tx-t1",
    )
    assert after_t1 is not None
    after_t2 = apply_position_reduce(
        after_t1,
        7.0,
        exit_price=120.0,
        mark_target2_achieved=True,
        fill_id="tx-t2",
    )
    assert after_t2 is not None
    assert after_t2.target2_leg is not None
    assert after_t2.target2_leg.status == "executed"
    assert executed_leg_has_fill(
        after_t2.target2_leg.status, after_t2.target2_leg.fill_id
    )
    assert after_t2.target2_leg.fill_id == "tx-t2"


def test_inv_05_trailing_does_not_worsen() -> None:
    assert does_stop_worsen("long", 98.0, 96.0) is True
    clamped = clamp_stop_not_worsen("long", 98.0, 96.0)
    assert clamped == 98.0
    improved = clamp_stop_not_worsen("long", 98.0, 101.0)
    assert improved == 101.0
    pos = _open_long()
    protected = apply_position_current_stop(pos, 98.0, origin="protect")
    assert protected is not None
    worsen = apply_position_current_stop(protected, 96.0, origin="trail")
    assert worsen is None


def test_inv_06_closed_cannot_generate_new_exit() -> None:
    pos = _open_long()
    closed = apply_position_reduce(pos, 10.0, exit_price=95.0)
    assert closed is not None
    assert closed.status == "CLOSED"
    assert apply_position_reduce(closed, 1.0, exit_price=95.0) is None
    assert apply_position_current_stop(closed, 100.0) is None
    exit_plan = build_exit_plan_from_position(closed, mark_price=90.0)
    assert exit_plan is None or exit_plan.status == "DONE"
    perm = check_exit_permission(exit_plan, position_closed=True)
    assert perm.allowed is False
    assert "position_closed" in perm.reasons


def test_inv_07_drift_clear_only_if_clean() -> None:
    inc = open_incident(
        incident_id="inc-1",
        account_id="acc-demo",
        kind="portfolio_drift",
        snapshot="qty mismatch",
    )
    resolved = resolve_incident(
        inc, resolution_note="broker confirmed", resolved_by="operator"
    )
    assert can_clear(resolved, recon_status="drift") is False
    with pytest.raises(ValueError, match="recon_not_clean"):
        clear_incident(resolved, recon_status="drift")
    cleared = clear_incident(resolved, recon_status="clean")
    assert cleared.status == "cleared"
    assert (
        resolve_position_operating_state(
            position_status="PROTECTED",
            remaining_quantity=10.0,
            quantity=10.0,
            has_trail_revision=False,
            has_protect_revision=True,
            recon_status="drift",
        )
        == "RECONCILIATION_DRIFT"
    )


def test_inv_08_fill_identity_immutable() -> None:
    pos = _open_long()
    reduced = apply_position_reduce(
        pos,
        3.0,
        exit_price=110.0,
        mark_target1_achieved=True,
        fill_id="tx-t1",
    )
    assert reduced is not None
    overwritten = apply_target_leg(
        reduced,
        which="t1",
        status="executed",
        fill_id="tx-OTHER",
    )
    assert overwritten.target1_leg is not None
    assert overwritten.target1_leg.fill_id == "tx-t1"
    assert mapping_unchanged(
        reduced.target1_leg.fill_id if reduced.target1_leg else None,
        overwritten.target1_leg.fill_id,
    )


def test_inv_09_decision_snapshot_immutable() -> None:
    plan = _plan()
    before = deepcopy(plan)
    pos = build_position_state_from_fill(
        plan,
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-09-01T09:00:00Z",
        position_id="pos-1",
    )
    assert pos is not None
    apply_position_reduce(pos, 3.0, exit_price=110.0)
    evaluate_risk_signature(plan, signed_qty=10.0, signed_price=100.0)
    assert mapping_unchanged(before, plan)
    assert pos.trade_plan_id == before["decisionId"]


def test_inv_10_risk_snapshot_immutable() -> None:
    plan = _plan()
    before = deepcopy(plan)
    first = evaluate_risk_signature(plan, signed_qty=10.0, signed_price=100.0)
    second = evaluate_risk_signature(plan, signed_qty=5.0, signed_price=100.0)
    assert mapping_unchanged(before, plan)
    assert first["signedLossAtStop"] == 50.0
    assert second["signedLossAtStop"] == 25.0
    assert first["stop"] == before["structuralStop"]
    assert second["stop"] == before["structuralStop"]
