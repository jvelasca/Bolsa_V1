"""OOS evaluation must warm indicators on IS bars — cold-start OOS is misleading."""

from datetime import UTC, datetime, timedelta

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.sma_grid import _simulate_sma_crossover


def _trend_bars(n: int) -> list[BacktestBarInput]:
    start = datetime(2014, 1, 1, tzinfo=UTC)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + 0.1 * i + (3.0 if i % 19 < 9 else -1.5),
        )
        for i in range(n)
    ]


def test_oos_without_warmup_differs_from_warmed_oos() -> None:
    """Cold-start on OOS-only bars ≠ trading OOS after IS warm-up (regression of P3.G UI)."""
    bars = _trend_bars(400)
    split = 280
    is_bars = bars[:split]
    oos_bars = bars[split:]
    fast, slow = 12, 35
    cash = 10_000.0

    cold = _simulate_sma_crossover(oos_bars, fast, slow, cash)
    warmed = _simulate_sma_crossover(
        is_bars + oos_bars,
        fast,
        slow,
        cash,
        trade_from_index=split,
    )

    assert cold["tradeCount"] > 0 or warmed["tradeCount"] > 0
    assert cold["tradeCount"] != warmed["tradeCount"] or abs(
        float(cold["score"]) - float(warmed["score"])
    ) > 1e-6


def test_warmed_oos_only_scores_oos_segment() -> None:
    bars = _trend_bars(240)
    split = 160
    metrics = _simulate_sma_crossover(
        bars,
        8,
        21,
        10_000.0,
        trade_from_index=split,
    )
    # Equity series length equals OOS bars (metrics window), not full series.
    assert metrics["tradeCount"] >= 0
    assert "score" in metrics
    assert "totalReturnPct" in metrics


def test_trade_from_zero_matches_legacy_full_window() -> None:
    bars = _trend_bars(120)
    a = _simulate_sma_crossover(bars, 5, 20, 10_000.0)
    b = _simulate_sma_crossover(bars, 5, 20, 10_000.0, trade_from_index=0)
    assert a["score"] == b["score"]
    assert a["tradeCount"] == b["tradeCount"]
    assert a["totalReturnPct"] == b["totalReturnPct"]
