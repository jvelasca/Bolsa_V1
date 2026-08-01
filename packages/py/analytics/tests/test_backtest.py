from datetime import date, timedelta
from math import sin

from bolsa_analytics.backtest import BacktestBarInput, BacktestCostModel, run_backtest


def _rising_bars(n: int = 60) -> list[BacktestBarInput]:
    return [
        BacktestBarInput(timestamp=f"2024-01-{day:02d}", close=100.0 + day)
        for day in range(1, n + 1)
    ]


def _oscillating_bars(n: int = 250) -> list[BacktestBarInput]:
    start = date(2020, 1, 1)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + 20.0 * sin(i / 8.0),
        )
        for i in range(n)
    ]


def test_run_backtest_sma_crossover() -> None:
    bars = _rising_bars(60)
    result = run_backtest(bars, "sma_crossover", 10000)
    assert result.bar_count == 60
    assert result.initial_cash == 10000
    assert len(result.equity_curve) == 60
    assert result.equity_curve[0].equity == 10000
    assert "sharpeRatio" in result.is_metrics
    assert result.is_metrics["commissionBps"] == 0


def test_costs_reduce_final_equity() -> None:
    bars = _oscillating_bars(250)
    free = run_backtest(bars, "sma_crossover", 10000)
    costly = run_backtest(
        bars,
        "sma_crossover",
        10000,
        costs=BacktestCostModel(commission_bps=50, slippage_bps=20, spread_bps=10),
    )
    assert free.trade_count > 0
    assert costly.trade_count == free.trade_count
    assert costly.final_equity < free.final_equity
    assert costly.is_metrics["totalCommission"] > 0
    assert costly.is_metrics["commissionBps"] == 50
    assert costly.is_metrics["slippageBps"] == 20
    assert costly.is_metrics["spreadBps"] == 10


def test_zero_costs_match_legacy_fill_at_close() -> None:
    """With zero costs, fill price equals mid close."""
    long_bars = _oscillating_bars(250)
    result = run_backtest(long_bars, "sma_crossover", 10000, commission_bps=0, slippage_bps=0)
    assert result.trade_count > 0
    for trade in result.trades:
        bar = next(b for b in long_bars if b.timestamp == trade.timestamp)
        assert abs(trade.price - bar.close) < 1e-9
        assert trade.commission == 0.0
