from unittest.mock import AsyncMock, MagicMock

import pytest
from bolsa_infrastructure.database.repositories.optimization_run_repository import (
    OptimizationRunRecord,
)

from bolsa_application.optimization_runs import (
    EnqueueOptimizationRun,
    ProcessOptimizationRun,
    optimize_result_to_dict,
)
from bolsa_application.optimize import OptimizeGridTrial, OptimizeSmaGridResult


def _sample_run(*, status: str = "pending") -> OptimizationRunRecord:
    return OptimizationRunRecord(
        id="run-1",
        instrument_id="inst-1",
        symbol="AAPL",
        status=status,  # type: ignore[arg-type]
        payload={
            "instrumentId": "inst-1",
            "engine": "h0",
            "initialCash": 10000,
            "barLimit": 100,
            "timeframe": "1d",
            "maxTrials": 10,
            "strategyFamily": "sma_crossover",
            "oosPct": 0.2,
        },
        result=None,
        error=None,
        engine="h0",
        best_score=None,
        trial_count=None,
        bar_count=None,
        created_at="2026-07-11T12:00:00+00:00",
        updated_at="2026-07-11T12:00:00+00:00",
        completed_at=None,
    )


def _sample_result() -> OptimizeSmaGridResult:
    metrics = {
        "totalReturnPct": 12.5,
        "maxDrawdownPct": 5.0,
        "sharpeRatio": 1.2,
        "sortinoRatio": 1.5,
        "calmarRatio": 0.8,
        "winRate": 0.5,
        "profitFactor": 1.4,
        "tradeCount": 8,
        "closedTrades": 4,
        "winCount": 2,
        "lossCount": 2,
        "totalCommission": 0.0,
        "commissionBps": 0,
        "slippageBps": 0,
        "spreadBps": 0,
        "score": 7.5,
    }
    oos = {
        "totalReturnPct": 3.0,
        "maxDrawdownPct": 4.0,
        "tradeCount": 2,
        "score": 2.0,
        "sharpeRatio": 0.4,
    }
    trial = OptimizeGridTrial(
        total_return_pct=12.5,
        max_drawdown_pct=5.0,
        trade_count=8,
        score=7.5,
        params={"fastPeriod": 10, "slowPeriod": 50},
        is_metrics=metrics,
        oos_metrics=oos,
    )
    return OptimizeSmaGridResult(
        instrument_id="inst-1",
        bar_count=100,
        engine="h0",
        baseline=trial,
        trials=[trial],
        trials_total=1,
        strategy_family="sma_crossover",
        oos_pct=0.2,
        is_bar_count=80,
        oos_bar_count=20,
        split_timestamp="2024-01-01T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_enqueue_optimization_run_with_arq() -> None:
    repo = MagicMock()
    repo.create_pending = AsyncMock(return_value=_sample_run())
    arq = MagicMock()
    arq.enqueue = AsyncMock()

    use_case = EnqueueOptimizationRun(repo, arq_queue=arq)
    run = await use_case.execute({"instrumentId": "inst-1", "engine": "h0"})

    assert run.id == "run-1"
    repo.create_pending.assert_awaited_once()
    arq.enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_optimization_run_success() -> None:
    run = _sample_run()
    repo = MagicMock()
    repo.claim_by_id = AsyncMock(return_value=run)
    repo.update_progress = AsyncMock()
    repo.mark_completed = AsyncMock(return_value=run)
    optimize = MagicMock()
    optimize.execute = AsyncMock(return_value=_sample_result())
    trials = MagicMock()
    trials.insert_trial = AsyncMock()

    use_case = ProcessOptimizationRun(repo, optimize, trials)
    result = await use_case.execute("run-1")

    assert result.processed is True
    assert result.status == "completed"
    repo.mark_completed.assert_awaited_once()
    saved = repo.mark_completed.await_args.kwargs["result"]
    assert saved["instrumentId"] == "inst-1"
    assert saved["trials"][0]["fastPeriod"] == 10
    assert saved["oosPct"] == 0.2
    assert saved["trials"][0]["oosMetrics"]["score"] == 2.0
    trials.insert_trial.assert_awaited()
    assert trials.insert_trial.await_count == 1
    assert trials.insert_trial.await_args.kwargs["blocks"]["oosMetrics"]["score"] == 2.0


@pytest.mark.asyncio
async def test_process_optimization_run_value_error() -> None:
    run = _sample_run()
    repo = MagicMock()
    repo.claim_by_id = AsyncMock(return_value=run)
    repo.update_progress = AsyncMock()
    repo.mark_failed = AsyncMock(return_value=run)
    optimize = MagicMock()
    optimize.execute = AsyncMock(side_effect=ValueError("sin datos"))
    trials = MagicMock()

    use_case = ProcessOptimizationRun(repo, optimize, trials)
    result = await use_case.execute("run-1")

    assert result.processed is True
    assert result.status == "failed"
    assert result.error == "sin datos"
    trials.insert_trial.assert_not_called()


def test_optimize_result_to_dict() -> None:
    payload = optimize_result_to_dict(_sample_result())
    assert payload["barCount"] == 100
    assert payload["trials"][0]["score"] == 7.5
    assert payload["strategyFamily"] == "sma_crossover"
    assert payload["isBarCount"] == 80
