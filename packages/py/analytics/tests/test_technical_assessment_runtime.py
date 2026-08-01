"""TechnicalAssessment + DecisionRuntime — TA no decide BUY."""

from __future__ import annotations

from bolsa_analytics.knowledge import (
    Assessment,
    TechnicalInputs,
    bias_from_score,
    build_technical_assessment,
    run_decision_runtime,
)


def _bullish_inputs() -> TechnicalInputs:
    return TechnicalInputs(
        rsi=62,
        adx=28,
        plus_di=28,
        minus_di=12,
        obv_slope=1.0,
        price_slope=0.5,
        bb_width_pct=4.0,
        atr=1.2,
        atr_percentile=40,
        close=150,
        sma_20=148,
        sma_50=145,
    )


def test_technical_assessment_emits_bias_not_action():
    assessment, _, score = build_technical_assessment("inst-1", _bullish_inputs())
    assert assessment.bias in {"bullish", "bearish", "neutral"}
    assert not hasattr(assessment, "action")
    d = assessment.to_dict()
    assert d["artifactType"] == "ART-TECHNICAL-ASSESSMENT"
    assert "narrativeFacts" in d
    assert score.score == assessment.score


def test_bias_from_score_thresholds():
    assert bias_from_score(0.5) == "bullish"
    assert bias_from_score(-0.5) == "bearish"
    assert bias_from_score(0.1) == "neutral"


def test_decision_runtime_maps_bias_to_action():
    assessment, _, _ = build_technical_assessment("inst-1", _bullish_inputs())
    result = run_decision_runtime(instrument_id="inst-1", assessments=[assessment])
    assert result.package.artifact_type == "ART-DECISION-PACKAGE"
    assert result.technical_assessment is not None
    assert len(result.assessments) == 1
    assert result.assessments[0].assessment_type == "technical"
    assert result.policy_gate is not None
    assert result.policy_gate["status"] == "SKIPPED"
    # Runtime es quien emite la acción
    if assessment.bias == "bullish":
        assert result.package.action == "recommend_long"
    elif assessment.bias == "bearish":
        assert result.package.action == "recommend_short"
    else:
        assert result.package.action == "wait"


def test_technical_projects_to_assessment_envelope():
    assessment, _, _ = build_technical_assessment("inst-1", _bullish_inputs())
    envelope = assessment.as_assessment()
    assert isinstance(envelope, Assessment)
    assert envelope.assessment_type == "technical"
    assert envelope.metadata["bias"] == assessment.bias
    assert list(envelope.facts) == list(assessment.narrative_facts)


def test_decision_runtime_accepts_heterogeneous_collection():
    ta, _, _ = build_technical_assessment("inst-1", _bullish_inputs())
    macro = Assessment(
        assessment_id="MAC-1",
        assessment_type="macro",
        instrument_id="inst-1",
        timestamp=ta.timestamp,
        score=0.1,
        confidence=0.4,
        facts=("Macro neutral",),
        warnings=(),
        metadata={"regime": "neutral", "tradability": "tradable", "coverage": 0.5},
    )
    result = run_decision_runtime(instrument_id="inst-1", assessments=[ta, macro])
    assert len(result.assessments) == 2
    types = {a.assessment_type for a in result.assessments}
    assert types == {"technical", "macro"}
    # v1.1 fusiona; con macro débil y TA bullish suele seguir long
    assert result.package.action in {"recommend_long", "wait", "recommend_short"}
    assert result.combined_score is not None

