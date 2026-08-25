"""F3 — ProposeRecommendationFromTa (materialize mockeado)."""

from __future__ import annotations

import asyncio
from datetime import UTC

from bolsa_application.propose_recommendation import ProposeRecommendationFromTa


class _FakeOhlcv:
    def __init__(self, bars: list) -> None:
        self._bars = bars

    async def get_bars(self, instrument_id: str, *, timeframe, limit: int):
        return self._bars[:limit]


class _FakeFeaturePort:
    def __init__(self) -> None:
        self._snap = None

    def put_latest(self, snap) -> None:
        self._snap = snap

    def get_latest(self, instrument_id: str, feature_set_id: str):
        return self._snap


class _Bar:
    def __init__(self, i: int) -> None:
        from datetime import datetime, timedelta

        self.timestamp = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i)
        self.open = 100 + i * 0.2
        self.high = self.open + 1
        self.low = self.open - 1
        self.close = self.open + 0.5
        self.volume = 1_000_000 + i * 1000


def test_propose_from_ta_bullish_bars():
    bars = [_Bar(i) for i in range(80)]
    ohlcv = _FakeOhlcv(bars)
    port = _FakeFeaturePort()

    import bolsa_application.propose_recommendation as mod
    from bolsa_analytics.features.models import FeatureSnapshot

    real_materialize = mod.materialize_feature_snapshot

    def fake_materialize(feature_port, *, instrument_id, bars, feature_set_id):
        from datetime import datetime

        snap = FeatureSnapshot(
            instrument_id=instrument_id,
            timestamp=datetime(2026, 3, 20, tzinfo=UTC),
            feature_set_id=feature_set_id,
            composition_hash="test",
            values={
                "rsi_14_close": 62.0,
                "adx_14": 28.0,
                "plus_di_14": 28.0,
                "minus_di_14": 12.0,
                "obv_slope": 1.0,
                "price_slope": 0.5,
                "bb_width_pct": 4.0,
                "atr_14": 1.2,
                "atr_percentile": 40.0,
                "close": float(bars[-1].close),
                "sma_20_close": float(bars[-1].close) - 1,
                "sma_50_close": float(bars[-1].close) - 2,
            },
        )
        feature_port.put_latest(snap)
        return snap

    mod.materialize_feature_snapshot = fake_materialize  # type: ignore[assignment]
    try:
        result = asyncio.run(
            ProposeRecommendationFromTa(ohlcv, port).execute(
                instrument_id="inst-test",
                suggested_quantity=5,
                suggested_price=None,
                symbol="TEST",
            )
        )
    finally:
        mod.materialize_feature_snapshot = real_materialize  # type: ignore[assignment]

    assert result.source == "decision_runtime_v1.1"
    assert result.recommendation.status == "awaiting_human"
    assert result.recommendation.suggested_price == result.last_close
    assert result.package.score_ta is not None
    assert result.technical_assessment.bias in {"bullish", "bearish", "neutral"}
    assert len(result.assessments) >= 1
    assert result.assessments[0].assessment_type == "technical"
    assert result.policy_gate is not None
    assert result.recommendation.action in {
        "recommend_long",
        "recommend_short",
        "wait",
        "reduce",
        "exit_hint",
    }
    payload = result.to_dict()
    plan = payload["tradePlan"]
    assert isinstance(plan, dict)
    assert plan["status"] in {"WATCH", "ARMED", "TRIGGERED", "BLOCKED", "EXPIRED"}
    assert isinstance(plan["whyNot"], list)
    assert plan["decisionId"] == result.package.decision_id
    assert "structuralStop" in plan
    session_runtime = (payload.get("decisionSession") or {}).get("runtime") or {}
    assert session_runtime.get("tradePlan") == plan
    # Ciclo 4.8: echo thin F3 = runtime (ambos None si no hay spring).
    session_anchor = session_runtime.get("wyckoffSpringAnchor")
    assert payload.get("wyckoffSpringAnchor") == session_anchor
    if session_anchor is not None:
        assert "effort" in session_anchor


def test_propose_with_fundamentals_port():
    bars = [_Bar(i) for i in range(80)]
    ohlcv = _FakeOhlcv(bars)
    port = _FakeFeaturePort()

    class _FakeFund:
        async def get_fundamentals(self, instrument_id: str):
            return {
                "marketCap": 80e9,
                "trailingPe": 14,
                "forwardPe": 13,
                "roe": 0.18,
                "altmanZ": 3.2,
                "fetchedAt": "2026-07-23T00:00:00Z",
            }

    import bolsa_application.propose_recommendation as mod
    from bolsa_analytics.features.models import FeatureSnapshot

    real_materialize = mod.materialize_feature_snapshot

    def fake_materialize(feature_port, *, instrument_id, bars, feature_set_id):
        from datetime import datetime

        snap = FeatureSnapshot(
            instrument_id=instrument_id,
            timestamp=datetime(2026, 3, 20, tzinfo=UTC),
            feature_set_id=feature_set_id,
            composition_hash="test",
            values={
                "rsi_14_close": 62.0,
                "adx_14": 28.0,
                "plus_di_14": 28.0,
                "minus_di_14": 12.0,
                "obv_slope": 1.0,
                "price_slope": 0.5,
                "bb_width_pct": 4.0,
                "atr_14": 1.2,
                "atr_percentile": 40.0,
                "close": float(bars[-1].close),
                "sma_20_close": float(bars[-1].close) - 1,
                "sma_50_close": float(bars[-1].close) - 2,
            },
        )
        feature_port.put_latest(snap)
        return snap

    mod.materialize_feature_snapshot = fake_materialize  # type: ignore[assignment]
    try:
        result = asyncio.run(
            ProposeRecommendationFromTa(ohlcv, port, fundamentals=_FakeFund()).execute(
                instrument_id="inst-test",
                suggested_quantity=2,
                include_fundamentals=True,
            )
        )
    finally:
        mod.materialize_feature_snapshot = real_materialize  # type: ignore[assignment]

    assert result.fundamental_assessment is not None
    assert result.fundamental_assessment.assessment_type == "fundamental"
    assert len(result.assessments) == 2
    types = {a.assessment_type for a in result.assessments}
    assert types == {"technical", "fundamental"}


def test_propose_with_macro_and_evidence():
    bars = [_Bar(i) for i in range(80)]
    ohlcv = _FakeOhlcv(bars)
    port = _FakeFeaturePort()

    from bolsa_analytics.cognitive.edge_report import StatisticalSuiteResult, build_edge_report

    report = build_edge_report(
        "strat-1",
        StatisticalSuiteResult(
            trials_n=40,
            walk_forward_efficiency=0.75,
            monte_carlo_p_value=0.01,
            dsr=0.7,
            stress_survival_rate=0.8,
        ),
    )

    class _FakeEdge:
        async def latest_edge_report(self, *, strategy_or_signal_ref=None, account_id=None):
            return report

    import bolsa_application.propose_recommendation as mod
    from bolsa_analytics.features.models import FeatureSnapshot

    real_materialize = mod.materialize_feature_snapshot

    def fake_materialize(feature_port, *, instrument_id, bars, feature_set_id):
        from datetime import datetime

        snap = FeatureSnapshot(
            instrument_id=instrument_id,
            timestamp=datetime(2026, 3, 20, tzinfo=UTC),
            feature_set_id=feature_set_id,
            composition_hash="test",
            values={
                "rsi_14_close": 62.0,
                "adx_14": 28.0,
                "plus_di_14": 28.0,
                "minus_di_14": 12.0,
                "obv_slope": 1.0,
                "price_slope": 0.5,
                "bb_width_pct": 4.0,
                "atr_14": 1.2,
                "atr_percentile": 40.0,
                "close": float(bars[-1].close),
                "sma_20_close": float(bars[-1].close) - 1,
                "sma_50_close": float(bars[-1].close) - 2,
            },
        )
        feature_port.put_latest(snap)
        return snap

    mod.materialize_feature_snapshot = fake_materialize  # type: ignore[assignment]
    try:
        result = asyncio.run(
            ProposeRecommendationFromTa(ohlcv, port, edge_reports=_FakeEdge()).execute(
                instrument_id="inst-test",
                suggested_quantity=1,
                include_fundamentals=False,
                include_evidence=True,
                macro={
                    "vix": 14,
                    "yieldCurve10y2yBps": 80,
                    "creditSpreadOasBps": 320,
                    "breadthPctAboveMa50": 60,
                },
                strategy_or_signal_ref="strat-1",
            )
        )
    finally:
        mod.materialize_feature_snapshot = real_materialize  # type: ignore[assignment]

    assert result.macro_assessment is not None
    assert result.evidence_assessment is not None
    assert result.recommendation.edge_report_ref == report.edge_report_id
    types = {a.assessment_type for a in result.assessments}
    assert "technical" in types and "macro" in types and "evidence" in types


def test_propose_requires_ohlcv():
    async def _run():
        try:
            await ProposeRecommendationFromTa(_FakeOhlcv([]), _FakeFeaturePort()).execute(
                instrument_id="x",
                suggested_quantity=1,
            )
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "OHLCV" in str(exc)

    asyncio.run(_run())
