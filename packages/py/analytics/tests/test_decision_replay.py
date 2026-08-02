"""Decision Replay desde DecisionSession."""

from __future__ import annotations

from bolsa_analytics.cognitive import (
    build_decision_replay,
    build_propose_session,
    resolve_weight_rules,
)


def test_replay_builds_timeline_steps():
    rules = resolve_weight_rules("swing", "neutral")
    session = build_propose_session(
        instrument_id="inst-1",
        symbol="AAPL",
        account_id="acc-1",
        timeframe="1d",
        horizon="swing",
        market_regime="neutral",
        profile_snapshot_ref="p1",
        policy_version="moderate",
        weight_rules=rules,
        missing_assessments=["news"],
        assessments=[
            {"type": "technical", "score": 0.4, "bias": "bullish"},
            {"type": "fundamental", "score": -0.1, "bias": "neutral"},
        ],
        evidence={"band": "skill"},
        runtime={"combinedScore": 0.22},
        recommendation={"recommendationId": "rec-1", "action": "wait"},
        policy_gate={"status": "PASS", "mode": "propose"},
        decision_id="dec-1",
    )
    replay = build_decision_replay(session.to_dict())
    ids = [s.step_id for s in replay.steps]
    assert ids[0] == "context"
    assert "assessments" in ids
    assert "weights" in ids
    assert "runtime" in ids
    assert "recommendation" in ids
    assert "gate" in ids
    assert "execution" in ids
    assert "outcome" in ids
    assert replay.symbol == "AAPL"
    d = replay.to_dict()
    assert d["sessionId"] == session.session_id
    assert len(d["steps"]) >= 7
