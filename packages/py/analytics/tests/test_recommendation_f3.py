"""F3 — Recommendation + OrderIntent contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from bolsa_analytics.cognitive import (
    intent_from_recommendation,
    recommendation_from_decision_package,
)
from bolsa_analytics.knowledge.decision_package_ta import DecisionMetrics, DecisionPackageTa


def test_recommendation_from_package_and_intent():
    package = DecisionPackageTa(
        decision_id=f"DEC-{uuid4().hex[:8]}",
        instrument_id="inst-1",
        timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        action="recommend_long",
        overall_confidence=0.7,
        metrics=DecisionMetrics(0.7, 0.6, 0.5, 0.55, 0.65),
        score_ta=0.4,
        evidence_breakdown=(),
        fact_set_ref="FS-1",
    )
    rec = recommendation_from_decision_package(
        package,
        suggested_quantity=10,
        suggested_price=100,
        account_id="acc-1",
        symbol="AAPL",
    )
    assert rec.artifact_type == "ART-RECOMMENDATION"
    assert rec.status == "awaiting_human"
    assert rec.notional == 1000
    intent = intent_from_recommendation(rec, account_id="acc-1")
    assert intent.artifact_type == "ART-ORDER-INTENT"
    assert intent.side == "buy"
    assert intent.source == "human_supervised"
    assert intent.status == "authorized"
