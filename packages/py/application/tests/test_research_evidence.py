"""P2.A — Evidence Store v0: classify + emit (ADR-018)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_domain.entities.research_evidence import ResearchEvidence
from bolsa_domain.entities.research_trial import ResearchTrial

from bolsa_application.research_evidence import (
    MATH_VERSION_EVIDENCE_V0,
    build_evidence_draft_from_dia_d_session,
    build_evidence_draft_from_trial,
    classify_dia_d_session_level,
    classify_evidence_from_blocks,
    emit_evidence_for_dia_d_session,
    emit_evidence_for_trial,
    evidence_weight_for_level,
)


def _trial(**overrides) -> ResearchTrial:
    base = dict(
        id="trial-1",
        instrument_id="inst-1",
        params={},
        is_metrics={"sharpeRatio": 1.1, "totalReturnPct": 4.0},
        proposed_by="human",
        k_contribution=1,
        created_at="2026-07-27T00:00:00+00:00",
        preset_key="sma_crossover",
        is_score=1.1,
    )
    base.update(overrides)
    return ResearchTrial(**base)


def test_classify_is_only_is_level_c():
    level, source = classify_evidence_from_blocks(None, has_is_metrics=True)
    assert level == "C"
    assert source == "trial_is"


def test_classify_holdout_is_level_c():
    level, source = classify_evidence_from_blocks(
        {"oosMetrics": {"score": 2.0}},
        has_is_metrics=True,
    )
    assert (level, source) == ("C", "holdout")


def test_classify_walkforward_is_level_b():
    level, source = classify_evidence_from_blocks(
        {"walkForward": {"meanOosScore": 1.0, "nFolds": 3}},
        has_is_metrics=True,
    )
    assert (level, source) == ("B", "walkforward")


def test_classify_cpcv_beats_holdout_fields():
    level, source = classify_evidence_from_blocks(
        {
            "oosMetrics": {"score": 1.0},
            "cpcv": {"pathCount": 4, "meanOosScore": 0.8},
        },
        has_is_metrics=True,
    )
    assert (level, source) == ("B", "cpcv")


def test_classify_never_returns_a_from_lab_blocks():
    level, _ = classify_evidence_from_blocks(
        {
            "cpcv": {"pathCount": 6},
            "edgeReport": {"band": "edge", "suite": {"monteCarloPValue": 0.01}},
        },
        has_is_metrics=True,
    )
    assert level == "B"


def test_classify_narrative_without_metrics():
    level, source = classify_evidence_from_blocks(None, has_is_metrics=False)
    assert (level, source) == ("D", "narrative")


def test_evidence_weights():
    assert evidence_weight_for_level("A") == 1.0
    assert evidence_weight_for_level("B") == 0.7
    assert evidence_weight_for_level("C") == 0.25
    assert evidence_weight_for_level("D") == 0.0


def test_build_draft_from_cpcv_trial():
    trial = _trial(
        blocks={
            "cpcv": {
                "meanOosScore": 0.9,
                "walkForwardEfficiency": 0.6,
                "pbo": {"pbo": 0.42},
            },
            "labEvidence": {"mode": "cpcv", "pbo": 0.42},
            "edgeReport": {
                "band": "uncertain",
                "persistedEdgeReportId": "EDGE-1",
            },
        },
        hypothesis_id=None,
    )
    draft = build_evidence_draft_from_trial(trial)
    assert draft is not None
    assert draft["level"] == "B"
    assert draft["source"] == "cpcv"
    assert draft["evidence_weight"] == 0.7
    assert draft["trial_id"] == "trial-1"
    assert draft["edge_report_id"] == "EDGE-1"
    assert draft["math_version"] == MATH_VERSION_EVIDENCE_V0
    assert draft["summary"]["pbo"] == 0.42
    assert draft["summary"]["walkForwardEfficiency"] == 0.6
    assert draft["summary"]["edgeBand"] == "uncertain"


@pytest.mark.asyncio
async def test_emit_noop_without_repo():
    assert await emit_evidence_for_trial(None, _trial()) is None


@pytest.mark.asyncio
async def test_emit_inserts_via_repo():
    saved = ResearchEvidence(
        id="ev-1",
        instrument_id="inst-1",
        level="C",
        source="trial_is",
        evidence_weight=0.25,
        summary={"level": "C"},
        created_at="2026-07-27T00:00:00+00:00",
        trial_id="trial-1",
    )
    repo = MagicMock()
    repo.insert_evidence = AsyncMock(return_value=saved)
    out = await emit_evidence_for_trial(repo, _trial())
    assert out is saved
    repo.insert_evidence.assert_awaited_once()
    kwargs = repo.insert_evidence.await_args.kwargs
    assert kwargs["level"] == "C"
    assert kwargs["source"] == "trial_is"
    assert kwargs["trial_id"] == "trial-1"


@pytest.mark.asyncio
async def test_run_and_save_emits_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    from bolsa_analytics.backtest import BacktestEngineResult, BacktestEquityPoint
    from bolsa_domain.entities.backtest import BacktestRunDetail

    from bolsa_application.backtests import RunAndSaveBacktest

    def _bar(ts: str, close: float) -> MagicMock:
        bar = MagicMock()
        bar.timestamp = ts
        bar.close = close
        return bar

    bars = [_bar(f"2024-01-{d:02d}", 100.0 + d) for d in range(1, 61)]
    instruments = MagicMock()
    instruments.get_by_id = AsyncMock(return_value=MagicMock(id="inst-1", symbol="AAPL", name="Apple"))
    ohlcv = MagicMock()
    ohlcv.get_bars = AsyncMock(return_value=bars)
    engine_result = BacktestEngineResult(
        initial_cash=10000,
        final_equity=10500,
        total_return_pct=5.0,
        max_drawdown_pct=1.0,
        trade_count=2,
        win_count=1,
        trades=[],
        equity_curve=[BacktestEquityPoint(timestamp=b.timestamp, equity=10000) for b in bars],
        first_date=bars[0].timestamp,
        last_date=bars[-1].timestamp,
        bar_count=len(bars),
        is_metrics={"totalReturnPct": 5.0, "sharpeRatio": 1.2},
    )
    monkeypatch.setattr(
        "bolsa_application.backtests.run_backtest",
        lambda *args, **kwargs: engine_result,
    )
    backtests = MagicMock()
    backtests.save_run = AsyncMock(
        return_value=BacktestRunDetail(
            id="run-1",
            instrument_id="inst-1",
            symbol="AAPL",
            name="Apple",
            strategy_type="sma_crossover",
            initial_cash=10000,
            final_equity=10500,
            total_return_pct=5.0,
            max_drawdown_pct=1.0,
            trade_count=2,
            win_count=1,
            bar_count=60,
            first_date="2024-01-01",
            last_date="2024-01-60",
            created_at="2026-07-27T00:00:00+00:00",
            trades=[],
        )
    )
    trial = _trial(
        id="trial-emit",
        backtest_run_id="run-1",
        blocks={"oosMetrics": {"score": 2.5}},
    )
    trials = MagicMock()
    trials.insert_trial = AsyncMock(return_value=trial)
    evidence = MagicMock()
    evidence.insert_evidence = AsyncMock(
        return_value=ResearchEvidence(
            id="ev-x",
            instrument_id="inst-1",
            level="C",
            source="holdout",
            evidence_weight=0.25,
            summary={},
            created_at="2026-07-27T00:00:00+00:00",
            trial_id="trial-emit",
        )
    )

    use_case = RunAndSaveBacktest(
        instruments, ohlcv, backtests, MagicMock(), trials, evidence
    )
    await use_case.execute(
        instrument_id="inst-1",
        strategy_type="sma_crossover",
        lab_evidence={"kind": "holdout", "oosScore": 2.5},
    )
    evidence.insert_evidence.assert_awaited_once()
    assert evidence.insert_evidence.await_args.kwargs["source"] == "holdout"
    assert evidence.insert_evidence.await_args.kwargs["level"] == "C"


def test_classify_dia_d_session_level():
    assert classify_dia_d_session_level("favorable") == "C"
    assert classify_dia_d_session_level("incomplete") == "D"
    assert classify_dia_d_session_level(None) == "D"


def test_build_draft_dia_d_session():
    draft = build_evidence_draft_from_dia_d_session(
        {
            "instrumentId": "inst-1",
            "symbol": "ACS",
            "mode": "semi",
            "strategyLabel": "SMA",
            "diaD": "2024-01-01",
            "endDate": "2024-12-31",
            "engine": "heuristic",
            "evidence": {
                "schemaVersion": "dia_d_session_evidence_v1",
                "band": "mixed",
                "confidence": "MEDIUM",
                "claims": ["c1"],
                "warnings": [],
                "metrics": {"returnPct": 5.0},
                "paragraphs": ["a", "b", "c"],
                "disclaimer": "sandbox",
            },
        }
    )
    assert draft is not None
    assert draft["source"] == "dia_d_session"
    assert draft["level"] == "C"
    assert draft["summary"]["sandbox"] is True
    assert draft["hypothesis_id"] is None


@pytest.mark.asyncio
async def test_emit_dia_d_session_evidence():
    saved = ResearchEvidence(
        id="ev-dia",
        instrument_id="inst-1",
        level="C",
        source="dia_d_session",
        evidence_weight=0.25,
        summary={"kind": "dia_d_session"},
        created_at="2026-07-31T00:00:00+00:00",
    )
    repo = MagicMock()
    repo.insert_evidence = AsyncMock(return_value=saved)
    out = await emit_evidence_for_dia_d_session(
        repo,
        {
            "instrumentId": "inst-1",
            "symbol": "ACS",
            "mode": "auto",
            "strategyLabel": "SMA",
            "diaD": "2024-06-01",
            "endDate": "2024-12-31",
            "evidence": {"band": "favorable", "paragraphs": ["1", "2", "3"]},
        },
    )
    assert out is saved
    assert repo.insert_evidence.await_args.kwargs["source"] == "dia_d_session"
