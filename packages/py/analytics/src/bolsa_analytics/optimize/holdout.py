"""Single hold-out split for optimize (IS search → OOS evaluate). Not walk-forward."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bolsa_analytics.backtest import BacktestBarInput

# Minimum bars on each side of the split.
MIN_IS_BARS = 50
MIN_OOS_BARS = 30
# Allowed hold-out fraction when enabled.
OOS_PCT_MIN = 0.1
OOS_PCT_MAX = 0.4


@dataclass(frozen=True, slots=True)
class HoldoutSplit:
    """Partición / fold: Holdout Split."""
    is_bars: list[BacktestBarInput]
    oos_bars: list[BacktestBarInput]
    oos_pct: float
    is_bar_count: int
    oos_bar_count: int
    split_timestamp: str | None


def normalize_oos_pct(oos_pct: float | None) -> float | None:
    """Return None when hold-out is off; otherwise clamp to [0.1, 0.4]."""
    if oos_pct is None:
        return None
    value = float(oos_pct)
    if value <= 0:
        return None
    return max(OOS_PCT_MIN, min(OOS_PCT_MAX, value))


def split_holdout_bars(
    bars: list[BacktestBarInput],
    oos_pct: float | None,
) -> HoldoutSplit | None:
    """Chronological split: first (1-oos) = IS, last oos = OOS. None if disabled."""
    resolved = normalize_oos_pct(oos_pct)
    if resolved is None:
        return None
    n = len(bars)
    oos_n = max(MIN_OOS_BARS, int(round(n * resolved)))
    is_n = n - oos_n
    if is_n < MIN_IS_BARS:
        raise ValueError(
            f"Hold-out {resolved:.0%}: se necesitan ≥{MIN_IS_BARS} barras IS "
            f"y ≥{MIN_OOS_BARS} OOS (hay {n} barras; baja oosPct o sube barLimit)"
        )
    if oos_n < MIN_OOS_BARS:
        raise ValueError(
            f"Hold-out insuficiente: OOS={oos_n} barras (mínimo {MIN_OOS_BARS})"
        )
    is_bars = bars[:is_n]
    oos_bars = bars[is_n:]
    split_ts: str | None = None
    if oos_bars:
        ts = oos_bars[0].timestamp
        split_ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    actual_pct = len(oos_bars) / n
    return HoldoutSplit(
        is_bars=is_bars,
        oos_bars=oos_bars,
        oos_pct=round(actual_pct, 4),
        is_bar_count=len(is_bars),
        oos_bar_count=len(oos_bars),
        split_timestamp=split_ts,
    )


def metrics_to_oos_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    """Compact OOS payload from a simulator metrics dict."""
    return {
        "totalReturnPct": float(metrics["totalReturnPct"]),
        "maxDrawdownPct": float(metrics["maxDrawdownPct"]),
        "tradeCount": int(metrics["tradeCount"]),
        "score": float(metrics["score"]),
        "sharpeRatio": metrics.get("sharpeRatio"),
    }
