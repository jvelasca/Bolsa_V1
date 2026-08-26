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
        country="US",
    )
    assert rec.artifact_type == "ART-RECOMMENDATION"
    assert rec.status == "awaiting_human"
    assert rec.notional == 1000
    assert rec.country == "US"
    assert rec.to_dict()["country"] == "US"
    intent = intent_from_recommendation(rec, account_id="acc-1")
    assert intent.artifact_type == "ART-ORDER-INTENT"
    assert intent.side == "buy"
    assert intent.source == "human_supervised"
    assert intent.status == "authorized"
    from bolsa_analytics.cognitive.order_intent import stable_intent_id_from_decision

    assert intent.intent_id == stable_intent_id_from_decision(package.decision_id)


def test_recommendation_country_optional():
    package = DecisionPackageTa(
        decision_id=f"DEC-{uuid4().hex[:8]}",
        instrument_id="inst-2",
        timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        action="wait",
        overall_confidence=0.4,
        metrics=DecisionMetrics(0.4, 0.4, 0.4, 0.4, 0.4),
        score_ta=0.0,
        evidence_breakdown=(),
        fact_set_ref="FS-2",
    )
    rec = recommendation_from_decision_package(
        package,
        suggested_quantity=1,
        symbol="SAN.MC",
        country="ES",
    )
    assert rec.to_dict()["country"] == "ES"
    assert rec.to_dict()["symbol"] == "SAN.MC"
