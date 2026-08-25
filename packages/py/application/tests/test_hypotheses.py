"""P2.B — Hypothesis CRUD + falsifiers stub + trial link."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bolsa_application.hypotheses import (
    CreateHypothesis,
    LinkTrialToHypothesis,
    UpdateHypothesis,
    normalize_falsifiers,
)
from bolsa_domain.entities.hypothesis import Hypothesis
from bolsa_domain.entities.research_trial import ResearchTrial


def test_normalize_falsifiers_requires_one():
    with pytest.raises(ValueError, match="al menos"):
        normalize_falsifiers([])


def test_normalize_falsifiers_requires_description():
    with pytest.raises(ValueError, match="description"):
        normalize_falsifiers([{"kind": "narrative"}])


def test_normalize_falsifiers_rejects_bad_kind():
    with pytest.raises(ValueError, match="kind"):
        normalize_falsifiers([{"description": "x", "kind": "magic"}])


def test_normalize_falsifiers_assigns_id_and_defaults():
    out = normalize_falsifiers([{"description": "  WFE < 0.3  "}])
    assert len(out) == 1
    assert out[0]["description"] == "WFE < 0.3"
    assert out[0]["kind"] == "narrative"
    assert isinstance(out[0]["id"], str) and out[0]["id"]


def test_normalize_falsifiers_keeps_params():
    out = normalize_falsifiers(
        [
            {
                "id": "f1",
                "description": "Sharpe OOS < 0",
                "kind": "metric_threshold",
                "params": {"metric": "sharpe", "lt": 0},
            }
        ]
    )
    assert out[0]["id"] == "f1"
    assert out[0]["params"]["lt"] == 0


@pytest.mark.asyncio
async def test_create_hypothesis_persists_normalized():
    saved = Hypothesis(
        id="h1",
        kind="hypothesis",
        statement="SMA edge persists OOS",
        falsifiers=[{"id": "f1", "description": "PBO >= 0.5", "kind": "metric_threshold"}],
        status="open",
        created_at="2026-07-27T00:00:00+00:00",
        updated_at="2026-07-27T00:00:00+00:00",
        domain="IBEX35",
    )
    repo = MagicMock()
    repo.insert = AsyncMock(return_value=saved)
    use_case = CreateHypothesis(repo)
    out = await use_case.execute(
        statement="  SMA edge persists OOS ",
        falsifiers=[{"description": "PBO >= 0.5", "kind": "metric_threshold"}],
        domain="IBEX35",
    )
    assert out.id == "h1"
    kwargs = repo.insert.await_args.kwargs
    assert kwargs["statement"] == "SMA edge persists OOS"
    assert kwargs["falsifiers"][0]["description"] == "PBO >= 0.5"


@pytest.mark.asyncio
async def test_create_rejects_empty_statement():
    use_case = CreateHypothesis(MagicMock())
    with pytest.raises(ValueError, match="statement"):
        await use_case.execute(statement="  ", falsifiers=[{"description": "x"}])


@pytest.mark.asyncio
async def test_update_revalidates_falsifiers():
    repo = MagicMock()
    repo.update = AsyncMock(
        return_value=Hypothesis(
            id="h1",
            kind="anti",
            statement="no edge",
            falsifiers=[{"id": "a", "description": "any fold > 0", "kind": "narrative"}],
            status="paused",
            created_at="t0",
            updated_at="t1",
        )
    )
    use_case = UpdateHypothesis(repo)
    await use_case.execute(
        "h1",
        kind="anti",
        status="paused",
        falsifiers=[{"description": "any fold > 0"}],
    )
    assert repo.update.await_args.kwargs["falsifiers"][0]["kind"] == "narrative"


@pytest.mark.asyncio
async def test_link_trial_to_hypothesis():
    hyp_repo = MagicMock()
    hyp_repo.get_by_id = AsyncMock(
        return_value=Hypothesis(
            id="h1",
            kind="hypothesis",
            statement="s",
            falsifiers=[{"id": "f", "description": "d", "kind": "narrative"}],
            status="open",
            created_at="t0",
            updated_at="t0",
        )
    )
    trial = ResearchTrial(
        id="tr1",
        instrument_id="inst-1",
        params={},
        is_metrics={},
        proposed_by="human",
        k_contribution=1,
        created_at="t0",
    )
    linked = ResearchTrial(
        id="tr1",
        instrument_id="inst-1",
        params={},
        is_metrics={},
        proposed_by="human",
        k_contribution=1,
        created_at="t0",
        hypothesis_id="h1",
    )
    trial_repo = MagicMock()
    trial_repo.get_by_id = AsyncMock(return_value=trial)
    trial_repo.set_hypothesis_id = AsyncMock(return_value=linked)

    use_case = LinkTrialToHypothesis(hyp_repo, trial_repo)
    out = await use_case.execute(trial_id="tr1", hypothesis_id="h1")
    assert out.hypothesis_id == "h1"
    trial_repo.set_hypothesis_id.assert_awaited_once_with("tr1", "h1")


@pytest.mark.asyncio
async def test_link_trial_missing_hypothesis():
    hyp_repo = MagicMock()
    hyp_repo.get_by_id = AsyncMock(return_value=None)
    trial_repo = MagicMock()
    trial_repo.get_by_id = AsyncMock(
        return_value=ResearchTrial(
            id="tr1",
            instrument_id="i",
            params={},
            is_metrics={},
            proposed_by="human",
            k_contribution=1,
            created_at="t0",
        )
    )
    use_case = LinkTrialToHypothesis(hyp_repo, trial_repo)
    with pytest.raises(LookupError, match="Hypothesis"):
        await use_case.execute(trial_id="tr1", hypothesis_id="missing")


@pytest.mark.asyncio
async def test_run_and_save_passes_hypothesis_id(monkeypatch: pytest.MonkeyPatch) -> None:
    from bolsa_analytics.backtest import BacktestEngineResult, BacktestEquityPoint
    from bolsa_application.backtests import RunAndSaveBacktest
    from bolsa_domain.entities.backtest import BacktestRunDetail

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
        is_metrics={"totalReturnPct": 5.0},
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
    trial = ResearchTrial(
        id="trial-h",
        instrument_id="inst-1",
        params={},
        is_metrics=engine_result.is_metrics,
        proposed_by="human",
        k_contribution=1,
        created_at="2026-07-27T00:00:00+00:00",
        hypothesis_id="hyp-1",
    )
    trials = MagicMock()
    trials.insert_trial = AsyncMock(return_value=trial)
    hyp_repo = MagicMock()
    hyp_repo.get_by_id = AsyncMock(
        return_value=Hypothesis(
            id="hyp-1",
            kind="hypothesis",
            statement="s",
            falsifiers=[{"id": "f", "description": "d", "kind": "narrative"}],
            status="open",
            created_at="t0",
            updated_at="t0",
        )
    )

    use_case = RunAndSaveBacktest(
        instruments, ohlcv, backtests, MagicMock(), trials, None, hyp_repo
    )
    await use_case.execute(
        instrument_id="inst-1",
        strategy_type="sma_crossover",
        hypothesis_id="hyp-1",
    )
    assert trials.insert_trial.await_args.kwargs["hypothesis_id"] == "hyp-1"
