"""Shared IS metric finalization for H0 parameter grids (SMA / RSI / MACD / rules).

Convención de costes (RD-1, auditoría LAB 2026-11-16): igual que ``run_backtest``. El
simulador aplica deslizamiento y media horquilla al precio de ejecución y comisión al
nocional; el resultado se entrega aquí **ya neto**. Con ``costs=None`` la simulación es
bruta y el payload lo declara (``returnBasis: "gross"``, ``netReturnPct: None``): un hueco
declarado, nunca un cero que aparente medición.
"""

from __future__ import annotations

from typing import Any

from bolsa_analytics.backtest import (
    BacktestCostModel,
    compute_buy_hold_return_pct,
    compute_is_metrics,
)


def finalize_grid_is_metrics(
    *,
    equity_values: list[float],
    initial_cash: float,
    max_drawdown_pct: float,
    trade_count: int,
    round_trip_pnls: list[float],
    attach_round_trips: bool = False,
    costs: BacktestCostModel | None = None,
    total_commission: float = 0.0,
    round_trip_entry_costs: list[float] | None = None,
    buy_hold_return_pct: float | None = None,
) -> dict[str, Any]:
    """Same IS keys as human `RunAndSaveBacktest`, plus ranking `score` (not Discovery Score).

    ``score`` conserva su fórmula (retorno − 0,25 × DD) pero declara su **base** en
    ``scoreBasis``: con costes aplicados la serie ya es neta y el score es neto; sin costes
    es bruto y así se rotula. El peso 0,25 no se toca aquí a propósito: cambiarlo a la vez
    que la base impediría atribuir un cambio de resultados a una sola causa.
    """
    final_equity = equity_values[-1] if equity_values else initial_cash
    metrics = compute_is_metrics(
        equity_values=equity_values,
        initial_cash=initial_cash,
        final_equity=final_equity,
        max_drawdown_pct=max_drawdown_pct,
        trade_count=trade_count,
        round_trip_pnls=round_trip_pnls,
        total_commission=total_commission,
        costs=costs,
        round_trip_entry_costs=round_trip_entry_costs,
        buy_hold_return_pct=buy_hold_return_pct,
    )
    net_return = metrics.get("netReturnPct")
    basis = "net" if net_return is not None else "gross"
    ranking_return = float(net_return) if net_return is not None else float(metrics["totalReturnPct"])
    score = ranking_return - float(metrics["maxDrawdownPct"]) * 0.25
    out: dict[str, Any] = {"score": round(score, 6), "scoreBasis": basis, **metrics}
    if attach_round_trips:
        # Cash PnL per closed round-trip (for lab EdgeReport / MC). Not for ledger bloat.
        out["roundTripPnls"] = [round(float(p), 6) for p in round_trip_pnls]
    return out


def grid_buy_hold_return_pct(
    bars: list[Any],
    *,
    start: int,
    costs: BacktestCostModel | None = None,
) -> float | None:
    """Buy & hold comparable de la ventana de trading (``bars[start]`` → último cierre).

    Devuelve ``None`` si no hay ventana o precios válidos: es un hueco, no un 0.
    """
    if not bars or start < 0 or start >= len(bars):
        return None
    first_close = float(bars[start].close)
    last_close = float(bars[-1].close)
    if first_close <= 0:
        return None
    return compute_buy_hold_return_pct(first_close, last_close, costs=costs)
