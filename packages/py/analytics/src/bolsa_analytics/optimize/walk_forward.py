"""Anchored expanding walk-forward folds for optimize (not CPCV / PBO)."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.holdout import MIN_IS_BARS, MIN_OOS_BARS

WF_FOLDS_MIN = 2
WF_FOLDS_MAX = 5


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    """Partición / fold: Walk Forward Fold."""
    index: int
    train_bars: list[BacktestBarInput]
    test_bars: list[BacktestBarInput]
    train_bar_count: int
    test_bar_count: int
    test_start_timestamp: str | None


def normalize_walk_forward_folds(n_folds: int | None) -> int | None:
    """Return None when off; otherwise clamp to [2, 5]."""
    if n_folds is None:
        return None
    value = int(n_folds)
    if value <= 0:
        return None
    return max(WF_FOLDS_MIN, min(WF_FOLDS_MAX, value))


def _ts(bar: BacktestBarInput) -> str:
    ts = bar.timestamp
    return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)


def split_walk_forward_bars(
    bars: list[BacktestBarInput],
    n_folds: int | None,
) -> list[WalkForwardFold]:
    """Expanding WF: (n+1) equal segments; fold i trains on 0..i, tests on segment i+1."""
    resolved = normalize_walk_forward_folds(n_folds)
    if resolved is None:
        return []

    n = len(bars)
    segments = resolved + 1
    seg = n // segments
    if seg < MIN_OOS_BARS:
        raise ValueError(
            f"Walk-forward {resolved} pliegues: cada tramo necesita ≥{MIN_OOS_BARS} barras "
            f"(hay {n}; sube barLimit o baja walkForwardFolds)"
        )
    if seg < MIN_IS_BARS and resolved >= 1:
        # First train is 1 segment; must meet IS minimum.
        pass
    if seg < MIN_IS_BARS:
        raise ValueError(
            f"Walk-forward: tramo de entrenamiento demasiado corto "
            f"({seg} < {MIN_IS_BARS}). Sube barLimit o baja walkForwardFolds."
        )

    folds: list[WalkForwardFold] = []
    for i in range(resolved):
        train_end = seg * (i + 1)
        test_end = seg * (i + 2)
        if i == resolved - 1:
            # Absorb leftover bars into the last test window.
            test_end = n
        train_bars = bars[:train_end]
        test_bars = bars[train_end:test_end]
        if len(train_bars) < MIN_IS_BARS or len(test_bars) < MIN_OOS_BARS:
            raise ValueError(
                f"Walk-forward pliegue {i + 1}: train={len(train_bars)} test={len(test_bars)} "
                f"(mín. {MIN_IS_BARS}/{MIN_OOS_BARS})"
            )
        folds.append(
            WalkForwardFold(
                index=i + 1,
                train_bars=train_bars,
                test_bars=test_bars,
                train_bar_count=len(train_bars),
                test_bar_count=len(test_bars),
                test_start_timestamp=_ts(test_bars[0]) if test_bars else None,
            )
        )
    return folds


_EPS = 1e-9


def fold_walk_forward_efficiency(is_score: float, oos_score: float) -> float | None:
    """Per-fold WFE = OOS score / IS score when IS > 0; else None."""
    if is_score > _EPS:
        return round(float(oos_score) / float(is_score), 4)
    return None


def aggregate_oos_scores(scores: list[float]) -> dict[str, Any]:
    """Mean / std of fold OOS scores (population std; 0 when single fold)."""
    return aggregate_walk_forward_metrics(is_scores=[], oos_scores=scores)


def aggregate_walk_forward_metrics(
    *,
    is_scores: list[float],
    oos_scores: list[float],
) -> dict[str, Any]:
    """Aggregate OOS + WFE / stability when paired IS scores are provided.

    WFE (lab): mean(OOS score) / mean(IS score) when mean(IS) > 0.
    Not CPCV/PBO; score = return% − 0.25×maxDD% (same lab objective).
    """
    if not oos_scores:
        return {
            "meanOosScore": 0.0,
            "stdOosScore": 0.0,
            "foldCount": 0,
            "foldScores": [],
            "meanIsScore": None,
            "walkForwardEfficiency": None,
            "positiveOosFoldShare": None,
            "oosCv": None,
        }

    mean_oos = float(mean(oos_scores))
    std_oos = float(pstdev(oos_scores)) if len(oos_scores) > 1 else 0.0
    positive_share = sum(1 for s in oos_scores if s >= 0.0) / len(oos_scores)
    oos_cv = round(std_oos / abs(mean_oos), 4) if abs(mean_oos) > _EPS else None

    mean_is: float | None = None
    wfe: float | None = None
    if is_scores and len(is_scores) == len(oos_scores):
        mean_is = float(mean(is_scores))
        if mean_is > _EPS:
            wfe = round(mean_oos / mean_is, 4)

    return {
        "meanOosScore": round(mean_oos, 4),
        "stdOosScore": round(std_oos, 4),
        "foldCount": len(oos_scores),
        "foldScores": [round(float(s), 4) for s in oos_scores],
        "meanIsScore": round(mean_is, 4) if mean_is is not None else None,
        "walkForwardEfficiency": wfe,
        "positiveOosFoldShare": round(positive_share, 4),
        "oosCv": oos_cv,
    }
