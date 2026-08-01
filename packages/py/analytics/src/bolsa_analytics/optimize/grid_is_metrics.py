"""Shared IS metric finalization for H0 parameter grids (SMA / RSI / MACD)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.backtest import compute_is_metrics


def finalize_grid_is_metrics(
    *,
    equity_values: list[float],
    initial_cash: float,
    max_drawdown_pct: float,
    trade_count: int,
    round_trip_pnls: list[float],
    attach_round_trips: bool = False,
) -> dict[str, Any]:
    """Same IS keys as human `RunAndSaveBacktest`, plus ranking `score` (not Discovery Score)."""
    final_equity = equity_values[-1] if equity_values else initial_cash
    metrics = compute_is_metrics(
        equity_values=equity_values,
        initial_cash=initial_cash,
        final_equity=final_equity,
        max_drawdown_pct=max_drawdown_pct,
        trade_count=trade_count,
        round_trip_pnls=round_trip_pnls,
    )
    score = float(metrics["totalReturnPct"]) - float(metrics["maxDrawdownPct"]) * 0.25
    out: dict[str, Any] = {**metrics, "score": round(score, 6)}
    if attach_round_trips:
        # Cash PnL per closed round-trip (for lab EdgeReport / MC). Not for ledger bloat.
        out["roundTripPnls"] = [round(float(p), 6) for p in round_trip_pnls]
    return out
