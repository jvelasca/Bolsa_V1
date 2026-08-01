"""ART-DECISION-SESSION + WeightContext."""

from __future__ import annotations

from bolsa_analytics.cognitive import (
    WEIGHT_RULES_VERSION,
    WeightContext,
    build_propose_session,
    resolve_weight_rules,
)


def test_weight_context_includes_rule_version():
    rules = resolve_weight_rules("swing", "neutral")
    ctx = WeightContext.from_weight_rules(rules, missing=("news",))
    d = ctx.to_dict()
    assert d["ruleVersion"] == WEIGHT_RULES_VERSION
    assert "news" in d["missingAssessments"]
    assert abs(d["weights"]["ta"] + d["weights"]["fund"] + d["weights"]["macro"] + d["weights"]["news"] - 1.0) < 1e-6


def test_build_propose_session_envelope():
    rules = resolve_weight_rules("swing", "risk_off")
    session = build_propose_session(
        instrument_id="inst-1",
        symbol="AAPL",
        account_id="acc-1",
        timeframe="1d",
        horizon="swing",
        market_regime="risk_off",
        profile_snapshot_ref="prof-1",
        policy_version="moderate",
        weight_rules=rules,
        missing_assessments=["news"],
        assessments=[{"type": "technical", "score": 0.4}],
        evidence=None,
        predictions=[{"modelId": "technical_rating_v1", "value": 0.3}],
        runtime={"combinedScore": 0.2, "lastClose": 190.0, "predictionsDoNotDecide": True},
        recommendation={"recommendationId": "rec-1", "action": "wait"},
        policy_gate={"status": "PASS", "mode": "propose"},
        decision_id="dec-1",
    )
    d = session.to_dict()
    assert d["artifactType"] == "ART-DECISION-SESSION"
    assert d["kind"] == "propose"
    assert d["sessionId"].startswith("DSS-")
    assert d["weightContext"]["ruleVersion"] == WEIGHT_RULES_VERSION
    assert d["recommendationId"] == "rec-1"
    assert d["predictions"][0]["modelId"] == "technical_rating_v1"
    assert d["runtime"]["predictionsDoNotDecide"] is True


def test_build_auto_session_and_attach_execution():
    from bolsa_analytics.cognitive import attach_execution_to_payload, build_auto_session

    auto = build_auto_session(
        kind="paper_auto",
        instrument_id="inst-1",
        account_id="acc-1",
        symbol="AAPL",
        policy_gate={"allowed": True},
        execution={"status": "accepted", "mode": "paper_auto"},
        lineage={"policyId": "pol-1", "policyMode": "paper_auto"},
    )
    d = auto.to_dict()
    assert d["kind"] == "paper_auto"
    assert d["execution"]["mode"] == "paper_auto"

    propose = {"sessionId": "DSS-x", "kind": "propose", "status": "open", "lineage": {}}
    updated = attach_execution_to_payload(
        propose,
        {"intent": {"side": "buy"}, "trade": None},
        kind="confirm",
        extra_lineage={"confirmedAt": "2026-07-23T00:00:00Z"},
    )
    assert updated["kind"] == "confirm"
    assert updated["execution"]["intent"]["side"] == "buy"
    assert updated["lineage"]["confirmedAt"]