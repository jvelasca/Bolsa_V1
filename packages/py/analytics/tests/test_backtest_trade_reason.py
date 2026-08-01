from bolsa_analytics.backtest import BacktestBarInput, run_backtest


def _bars(n: int = 120) -> list[BacktestBarInput]:
    from datetime import date, timedelta

    start = date(2020, 1, 1)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + ((i % 25) - 12) * 1.2,
        )
        for i in range(n)
    ]


def test_backtest_trades_include_reason_summary() -> None:
    result = run_backtest(_bars(), "sma_crossover", 10_000.0)
    assert result.trade_count > 0
    first = result.trades[0]
    assert first.reason is not None
    assert "summary" in first.reason
    assert first.reason["signalKind"] in {"entry_long", "exit"}
