from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_analytics.backtest import BacktestEngineResult, BacktestEquityPoint
from bolsa_domain.entities.backtest import BacktestRunDetail
from bolsa_domain.entities.research_trial import ResearchTrial

from bolsa_application.backtests import RunAndSaveBacktest


def _bar(ts: str, close: float) -> MagicMock:
    bar = MagicMock()
    bar.timestamp = ts
    bar.close = close
    return bar


def _instrument() -> MagicMock:
    inst = MagicMock()
    inst.id = "inst-1"
    inst.symbol = "AAPL"
    inst.name = "Apple"
    return inst


@pytest.mark.asyncio
async def test_run_and_save_writes_research_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    bars = [_bar(f"2024-01-{d:02d}", 100.0 + d) for d in range(1, 61)]

    instruments = MagicMock()
    instruments.get_by_id = AsyncMock(return_value=_instrument())
    ohlcv = MagicMock()
    ohlcv.get_bars = AsyncMock(return_value=bars)
    strategies = MagicMock()

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
        is_metrics={
            "totalReturnPct": 5.0,
            "sharpeRatio": 1.2,
            "commissionBps": 10,
            "slippageBps": 5,
            "spreadBps": 0,
            "totalCommission": 12.5,
        },
    )
    monkeypatch.setattr(
        "bolsa_application.backtests.run_backtest",
        lambda *args, **kwargs: engine_result,
    )

    saved_run = BacktestRunDetail(
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
        created_at="2026-07-24T00:00:00+00:00",
        trades=[],
    )
    backtests = MagicMock()
    backtests.save_run = AsyncMock(return_value=saved_run)

    trial = ResearchTrial(
        id="trial-1",
        instrument_id="inst-1",
        params={},
        is_metrics=engine_result.is_metrics,
        proposed_by="human",
        k_contribution=1,
        created_at="2026-07-24T00:00:00+00:00",
        backtest_run_id="run-1",
    )
    trials = MagicMock()
    trials.insert_trial = AsyncMock(return_value=trial)

    use_case = RunAndSaveBacktest(instruments, ohlcv, backtests, strategies, trials)
    result = await use_case.execute(
        instrument_id="inst-1",
        strategy_type="sma_crossover",
        commission_bps=10,
        slippage_bps=5,
    )

    assert result.trial_id == "trial-1"
    assert result.metrics["sharpeRatio"] == 1.2
    assert result.run.id == "run-1"
    trials.insert_trial.assert_awaited_once()
    kwargs = trials.insert_trial.await_args.kwargs
    assert kwargs["backtest_run_id"] == "run-1"
    assert kwargs["proposed_by"] == "human"
    assert kwargs["k_contribution"] == 1
    assert kwargs["params"]["commissionBps"] == 10
    assert kwargs.get("blocks") is None


@pytest.mark.asyncio
async def test_run_and_save_stamps_lab_blocks_from_adopt_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bars = [_bar(f"2024-01-{d:02d}", 100.0 + d) for d in range(1, 61)]
    instruments = MagicMock()
    instruments.get_by_id = AsyncMock(return_value=_instrument())
    ohlcv = MagicMock()
    ohlcv.get_bars = AsyncMock(return_value=bars)
    strategies = MagicMock()
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
        is_metrics={"totalReturnPct": 5.0, "sharpeRatio": 1.0},
    )
    monkeypatch.setattr(
        "bolsa_application.backtests.run_backtest",
        lambda *args, **kwargs: engine_result,
    )
    saved_run = BacktestRunDetail(
        id="run-2",
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
        created_at="2026-07-24T00:00:00+00:00",
        trades=[],
    )
    backtests = MagicMock()
    backtests.save_run = AsyncMock(return_value=saved_run)
    trial = ResearchTrial(
        id="trial-2",
        instrument_id="inst-1",
        params={},
        is_metrics=engine_result.is_metrics,
        proposed_by="human",
        k_contribution=1,
        created_at="2026-07-24T00:00:00+00:00",
        backtest_run_id="run-2",
    )
    trials = MagicMock()
    trials.insert_trial = AsyncMock(return_value=trial)

    use_case = RunAndSaveBacktest(instruments, ohlcv, backtests, strategies, trials)
    await use_case.execute(
        instrument_id="inst-1",
        strategy_type="sma_crossover",
        lab_evidence={
            "kind": "holdout",
            "oosScore": 3.5,
            "edgeBand": "uncertain",
            "persistedEdgeReportId": "EDGE-xyz",
        },
    )
    blocks = trials.insert_trial.await_args.kwargs["blocks"]
    assert blocks["oosMetrics"]["score"] == 3.5
    assert blocks["edgeReport"]["persistedEdgeReportId"] == "EDGE-xyz"
