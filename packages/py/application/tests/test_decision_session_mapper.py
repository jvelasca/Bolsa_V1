"""Mapper DecisionSession → DecisionSessionRecord."""

from __future__ import annotations

from bolsa_analytics.cognitive import build_propose_session, resolve_weight_rules

from bolsa_application.cognitive_persistence import decision_session_to_record


def test_decision_session_to_record():
    rules = resolve_weight_rules("swing", "neutral")
    session = build_propose_session(
        instrument_id="inst-1",
        symbol="AAPL",
        account_id="acc-1",
        timeframe="1d",
        horizon="swing",
        market_regime="neutral",
        profile_snapshot_ref=None,
        policy_version="moderate",
        weight_rules=rules,
        missing_assessments=[],
        assessments=[],
        evidence=None,
        runtime={"combinedScore": 0.1},
        recommendation={"recommendationId": "rec-9", "action": "wait"},
        policy_gate=None,
    )
    rec = decision_session_to_record(session)
    assert rec.id == session.session_id
    assert rec.payload is not None
    assert rec.payload["sessionId"] == session.session_id
    assert rec.recommendation_id == "rec-9"
