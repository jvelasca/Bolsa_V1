"""V1.18 L2a — origin DecisionPackage snapshot helpers."""

from __future__ import annotations

from bolsa_application.origin_decision_package import (
    ORIGIN_DECISION_PACKAGE_KEY,
    freeze_origin_decision_package,
    origin_thesis_from_position_state,
    preserve_origin_decision_package,
)


def test_freeze_requires_package() -> None:
    plan = {
        "decisionId": "D1",
        "instrumentId": "i1",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
    }
    assert (
        freeze_origin_decision_package(
            package=None,
            trade_plan=plan,
            decision_id="D1",
            instrument_id="i1",
        )
        is None
    )


def test_freeze_rejects_instrument_mismatch() -> None:
    plan = {"decisionId": "D1", "instrumentId": "i1", "direction": "long", "status": "TRIGGERED"}
    snap = freeze_origin_decision_package(
        package={"instrumentId": "OTHER", "action": "recommend_long"},
        trade_plan=plan,
        decision_id="D1",
        instrument_id="i1",
    )
    assert snap is None


def test_freeze_and_preserve_roundtrip() -> None:
    plan = {
        "decisionId": "D1",
        "instrumentId": "i1",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "riskAmount": 50.0,
    }
    snap = freeze_origin_decision_package(
        package={"instrumentId": "i1", "action": "recommend_long", "overallConfidence": 7.5},
        trade_plan=plan,
        decision_id="D1",
        instrument_id="i1",
    )
    assert snap is not None
    assert snap["decisionId"] == "D1"
    assert snap["entry"] == 100.0
    assert snap["strength"] == 7.5

    prev = {ORIGIN_DECISION_PACKAGE_KEY: snap, "currentStop": 95.0}
    nxt = preserve_origin_decision_package(prev, {"currentStop": 98.0, "status": "PROTECTED"})
    assert nxt[ORIGIN_DECISION_PACKAGE_KEY]["entry"] == 100.0
    assert nxt["currentStop"] == 98.0

    thesis = origin_thesis_from_position_state(nxt)
    assert thesis is not None
    assert thesis["decisionId"] == "D1"
    assert thesis["entry"] == 100.0
