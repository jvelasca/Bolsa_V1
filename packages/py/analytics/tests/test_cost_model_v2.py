"""Q3.5 — cost model v2 wiring smoke."""

from bolsa_analytics.backtest import BacktestBarInput, BacktestCostModel, run_backtest
from bolsa_analytics.cost_model_v2 import (
    CostModelV2Config,
    cost_v2_from_fixed,
    resolve_bar_costs_v2,
)


def _bars_with_volume() -> list[BacktestBarInput]:
    out: list[BacktestBarInput] = []
    for i in range(80):
        # Low volume on half the bars → illiquid path when enabled.
        vol = 100.0 if i % 2 == 0 else 10.0
        out.append(
            BacktestBarInput(
                timestamp=f"2024-01-{(i % 28) + 1:02d}",
                close=100.0 + i * 0.2 + (2.0 if i % 15 < 7 else -1.0),
                volume=vol,
            )
        )
    return out


def test_resolve_bar_costs_illiquid() -> None:
    cfg = CostModelV2Config(
        enabled=True,
        commission_bps=10,
        slippage_bps_base=5,
        slippage_bps_illiquid_extra=8,
        volume_ratio_illiquid=0.35,
        spread_bps_tip=2,
        spread_bps_wide=6,
    )
    c, s, sp = resolve_bar_costs_v2(cfg, volume=10.0, median_vol=100.0)
    assert c == 10
    assert s == 13
    assert sp == 6


def test_cost_v2_disabled_matches_fixed() -> None:
    bars = _bars_with_volume()
    fixed = BacktestCostModel(commission_bps=10, slippage_bps=5, spread_bps=2)
    off = cost_v2_from_fixed(
        commission_bps=10, slippage_bps=5, spread_bps=2, enabled=False
    )
    a = run_backtest(bars, "sma_crossover", 10_000, costs=fixed)
    b = run_backtest(bars, "sma_crossover", 10_000, costs=fixed, cost_v2=off)
    assert a.final_equity == b.final_equity
    assert b.is_metrics.get("costModelV2") is False


def test_cost_v2_enabled_can_change_equity() -> None:
    bars = _bars_with_volume()
    fixed = BacktestCostModel(commission_bps=10, slippage_bps=5, spread_bps=2)
    on = cost_v2_from_fixed(
        commission_bps=10, slippage_bps=5, spread_bps=2, enabled=True, illiquid_extra=40
    )
    a = run_backtest(bars, "sma_crossover", 10_000, costs=fixed)
    b = run_backtest(bars, "sma_crossover", 10_000, costs=fixed, cost_v2=on)
    assert b.is_metrics.get("costModelV2") is True
    # Illiquid penalty should not improve fills vs fixed tip.
    assert b.final_equity <= a.final_equity + 1e-6
