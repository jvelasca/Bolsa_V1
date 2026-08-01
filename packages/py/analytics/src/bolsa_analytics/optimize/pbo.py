"""Probability of Backtest Overfitting (PBO) — CSCV lab lite.

Bailey / Borwein / López de Prado / Zhu style combinatorially symmetric CV
on a (S × N) score matrix. Not full event-based CPCV; score = lab objective.
"""

from __future__ import annotations

from itertools import combinations
from math import comb, log
from typing import Any

import numpy as np

# Soft thresholds for UI / checklist (not production gates).
PBO_WARN = 0.5
PBO_BAD = 0.7


def pbo_segment_count(n_groups: int) -> int:
    """CSCV needs an even number of segments; drop one if odd (5 → 4)."""
    n = int(n_groups)
    if n < 4:
        return 0
    return n if n % 2 == 0 else n - 1


def equal_segment_ranges(n_bars: int, n_segments: int) -> list[tuple[int, int]]:
    """Contiguous [start, end) ranges covering all bars (last segment absorbs remainder)."""
    if n_segments < 1 or n_bars < n_segments:
        return []
    seg = n_bars // n_segments
    ranges: list[tuple[int, int]] = []
    for g in range(n_segments):
        start = g * seg
        end = n_bars if g == n_segments - 1 else (g + 1) * seg
        ranges.append((start, end))
    return ranges


def estimate_pbo_cscv(score_matrix: np.ndarray | list[list[float]]) -> dict[str, Any]:
    """Estimate PBO from score matrix shape (S, N).

    For each way to split S segments into equal IS/OOS halves:
    IS winner = argmax mean score on IS; ω = relative OOS rank among N;
    λ = logit(ω); PBO = fraction of splits with λ ≤ 0.
    """
    matrix = np.asarray(score_matrix, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("score_matrix must be 2-D (S × N)")
    s_count, n_strats = matrix.shape
    if s_count < 4 or s_count % 2 != 0:
        raise ValueError(f"CSCV needs even S≥4 (got S={s_count})")
    if n_strats < 2:
        raise ValueError("CSCV needs N≥2 strategies")

    half = s_count // 2
    splits = list(combinations(range(s_count), half))
    logits: list[float] = []
    below_median = 0

    for is_idx in splits:
        is_set = set(is_idx)
        oos_idx = [i for i in range(s_count) if i not in is_set]
        is_scores = matrix[list(is_idx), :].mean(axis=0)
        oos_scores = matrix[oos_idx, :].mean(axis=0)
        winner = int(np.argmax(is_scores))
        winner_oos = float(oos_scores[winner])
        # Rank 1 = worst … N = best (higher score better).
        rank = int(np.sum(oos_scores <= winner_oos))
        omega = rank / (n_strats + 1.0)
        omega = min(max(omega, 1e-6), 1.0 - 1e-6)
        logit = log(omega / (1.0 - omega))
        logits.append(logit)
        if logit <= 0.0:
            below_median += 1

    split_count = len(splits)
    assert split_count == comb(s_count, half)
    pbo = below_median / split_count
    arr = np.asarray(logits, dtype=float)
    return {
        "pbo": round(float(pbo), 4),
        "splitCount": split_count,
        "segmentCount": s_count,
        "strategyCount": n_strats,
        "meanLogit": round(float(arr.mean()), 4),
        "stdLogit": round(float(arr.std(ddof=0)), 4) if split_count > 1 else 0.0,
        "belowMedianCount": below_median,
        "mode": "cscv_lab",
        "warnThreshold": PBO_WARN,
        "badThreshold": PBO_BAD,
    }


def classify_pbo(pbo: float | None) -> str:
    """UI band: low / elevated / high / n/d."""
    if pbo is None:
        return "n/d"
    if pbo < PBO_WARN:
        return "low"
    if pbo < PBO_BAD:
        return "elevated"
    return "high"
