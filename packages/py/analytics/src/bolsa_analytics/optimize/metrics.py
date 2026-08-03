"""Métricas compartidas RD-3."""

from __future__ import annotations


def trial_score(total_return_pct: float, max_drawdown_pct: float) -> float:
    """Función pública ``trial_score``."""
    return round(total_return_pct - (max_drawdown_pct * 0.25), 4)


def vectorbt_freq(timeframe: str) -> str:
    """Función pública ``vectorbt_freq``."""
    return {
        "1d": "1D",
        "1h": "1H",
        "4h": "4H",
        "1wk": "1W",
    }.get(timeframe, "1D")
