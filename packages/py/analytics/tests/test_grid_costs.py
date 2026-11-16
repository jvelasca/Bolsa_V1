"""RD-1 — la rejilla debe medir sin fricción cero (auditoría LAB 2026-11-16).

Estos tests fijan el contrato que habilita el gate P1: con costes declarados la simulación
se entrega **neta**, el score declara su base, y las métricas que faltan quedan en ``None``
(hueco declarado) en lugar de rellenarse con ceros o números inventados.
"""

from datetime import UTC, datetime, timedelta
from math import sin

from bolsa_analytics.backtest import (
    BacktestBarInput,
    BacktestCostModel,
    compute_buy_hold_return_pct,
    round_trip_cost_bps,
    run_backtest,
)
from bolsa_analytics.backtest import REFERENCE_COSTS
from bolsa_analytics.optimize.grid_is_metrics import finalize_grid_is_metrics
from bolsa_analytics.optimize.rules_grid import _simulate_rules_strategy
from bolsa_analytics.optimize.sma_grid import _simulate_sma_crossover

COSTS_42_BPS = BacktestCostModel(commission_bps=10, slippage_bps=8, spread_bps=6)


def _trend_bars(n: int) -> list[BacktestBarInput]:
    start = datetime(2014, 1, 1, tzinfo=UTC)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + 0.1 * i + (3.0 if i % 19 < 9 else -1.5),
        )
        for i in range(n)
    ]


def test_round_trip_cost_bps_matches_repo_convention() -> None:
    # 2 × (10 + 8) + 6 = 42 bps.
    assert round_trip_cost_bps(COSTS_42_BPS) == 42.0
    assert round_trip_cost_bps(BacktestCostModel()) == 0.0


def test_gross_grid_declares_the_gap_instead_of_zero() -> None:
    metrics = _simulate_sma_crossover(_trend_bars(240), 8, 21, 10_000.0)
    assert metrics["returnBasis"] == "gross"
    assert metrics["scoreBasis"] == "gross"
    assert metrics["netReturnPct"] is None
    assert metrics["excessReturnPct"] is None
    assert metrics["roundTripCostBps"] is None


def test_costs_make_the_grid_net_and_change_the_score_basis() -> None:
    bars = _trend_bars(240)
    gross = _simulate_sma_crossover(bars, 8, 21, 10_000.0)
    net = _simulate_sma_crossover(bars, 8, 21, 10_000.0, costs=COSTS_42_BPS)

    assert gross["tradeCount"] > 0 and net["tradeCount"] > 0
    assert net["returnBasis"] == "net"
    assert net["scoreBasis"] == "net"
    assert net["netReturnPct"] == net["totalReturnPct"]
    assert net["roundTripCostBps"] == 42.0
    # La fricción no puede mejorar el resultado.
    assert float(net["totalReturnPct"]) < float(gross["totalReturnPct"])
    assert net["totalCommission"] > 0


def test_score_is_computed_on_the_declared_basis() -> None:
    bars = _trend_bars(240)
    gross = _simulate_sma_crossover(bars, 8, 21, 10_000.0)
    net = _simulate_sma_crossover(bars, 8, 21, 10_000.0, costs=COSTS_42_BPS)

    assert gross["score"] == round(
        float(gross["totalReturnPct"]) - float(gross["maxDrawdownPct"]) * 0.25, 6
    )
    assert net["score"] == round(
        float(net["netReturnPct"]) - float(net["maxDrawdownPct"]) * 0.25, 6
    )


def test_round_trip_pnls_are_net_of_commissions() -> None:
    bars = _trend_bars(240)
    net = _simulate_sma_crossover(
        bars, 8, 21, 10_000.0, costs=COSTS_42_BPS, attach_round_trips=True
    )
    assert net["roundTripPnls"]
    # PnL medio por operación = suma / nº operaciones cerradas (neto declarado).
    mean_pnl = sum(net["roundTripPnls"]) / len(net["roundTripPnls"])
    assert abs(float(net["expectancyCurrency"]) - mean_pnl) < 1e-6


def test_expectancy_pct_present_but_expectancy_r_never_fabricated() -> None:
    net = _simulate_sma_crossover(_trend_bars(240), 8, 21, 10_000.0, costs=COSTS_42_BPS)
    assert net["expectancyPct"] is not None
    # Sin unidad de riesgo declarada (stop/ATR) no se emite R.
    assert net["expectancyR"] is None


def _sma_definition(fast: int, slow: int) -> dict:
    fast_spec = {"definitionId": "sma", "parameters": {"period": fast}}
    slow_spec = {"definitionId": "sma", "parameters": {"period": slow}}
    return {
        "presetKey": "sma_crossover",
        "indicatorSpecs": [fast_spec, slow_spec],
        "entries": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_cross",
                    "leftSpec": fast_spec,
                    "rightSpec": slow_spec,
                    "direction": "bullish",
                    "signalKind": "entry_long",
                }
            ],
        },
        "exits": {
            "operator": "all",
            "rules": [
                {
                    "type": "indicator_cross",
                    "leftSpec": fast_spec,
                    "rightSpec": slow_spec,
                    "direction": "bearish",
                    "signalKind": "exit",
                }
            ],
        },
    }


def test_rules_grid_applies_costs_and_benchmark() -> None:
    bars = _trend_bars(240)
    metrics = _simulate_rules_strategy(
        bars, _sma_definition(8, 21), initial_cash=10_000.0, costs=COSTS_42_BPS
    )
    assert metrics["returnBasis"] == "net"
    assert metrics["buyHoldReturnPct"] is not None
    assert metrics["excessReturnPct"] == round(
        float(metrics["netReturnPct"]) - float(metrics["buyHoldReturnPct"]), 6
    )


def test_buy_hold_benchmark_pays_the_same_friction() -> None:
    frictionless = compute_buy_hold_return_pct(100.0, 110.0)
    with_costs = compute_buy_hold_return_pct(100.0, 110.0, costs=COSTS_42_BPS)
    assert frictionless > with_costs
    # El exceso solo es comparable si el benchmark paga lo mismo que la estrategia.
    assert with_costs < frictionless - 0.3


def test_run_backtest_exposes_net_and_expectancy_keys() -> None:
    bars = _trend_bars(240)
    result = run_backtest(bars, "sma_crossover", 10_000.0, costs=COSTS_42_BPS)
    metrics = result.is_metrics
    assert metrics["returnBasis"] == "net"
    assert metrics["netReturnPct"] == metrics["totalReturnPct"]
    assert metrics["netTradeCount"] == metrics["closedTrades"]
    assert metrics["roundTripCostBps"] == 42.0
    assert metrics["expectancyR"] is None


def test_finalize_is_identity_when_no_trades_and_no_costs() -> None:
    metrics = finalize_grid_is_metrics(
        equity_values=[10_000.0, 10_000.0],
        initial_cash=10_000.0,
        max_drawdown_pct=0.0,
        trade_count=0,
        round_trip_pnls=[],
    )
    assert metrics["score"] == 0.0
    assert metrics["scoreBasis"] == "gross"
    assert metrics["expectancyCurrency"] is None
    assert metrics["expectancyPct"] is None


def _chop_bars(n: int = 360) -> list[BacktestBarInput]:
    """Tendencia suave + ruido: el bruto gana, la fricción de referencia se lo come."""
    start = datetime(2014, 1, 1, tzinfo=UTC)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0
            * (
                1
                + 0.0008 * i
                + 0.012 * sin(i / 2.7)
                + 0.002 * sin(i / 6.3)
            ),
        )
        for i in range(n)
    ]


def test_reference_costs_are_the_32_bps_product_default() -> None:
    assert round_trip_cost_bps(REFERENCE_COSTS) == 32.0


def test_gross_winner_is_a_net_loser_without_relaxing_anything() -> None:
    """§4.3 de la auditoría: el campeón bruto no es el campeón neto.

    Sin mirar el neto, esta rejilla elegiría (8/21) por su score bruto; con los 32 bps
    de referencia ese mismo par pierde dinero. El gate P1 no puede promocionarlo.
    """
    bars = _chop_bars()
    gross = _simulate_sma_crossover(bars, 8, 21, 10_000.0)
    net = _simulate_sma_crossover(bars, 8, 21, 10_000.0, costs=REFERENCE_COSTS)

    assert float(gross["totalReturnPct"]) > 0
    assert net["returnBasis"] == "net"
    assert net["roundTripCostBps"] == 32.0
    assert float(net["netReturnPct"]) < 0
    # Hay muestra suficiente para que el hueco no sea «pocas operaciones».
    assert int(net["netTradeCount"]) >= 10
    # Y el score deja de premiar lo que pierde.
    assert float(net["score"]) < float(gross["score"])
