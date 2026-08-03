"""Combinatorial Purged Cross-Validation (ligero) for optimize lab.

Bar-level Lopez-de-Prado-style paths: N contiguous groups, C(N,k) test combos,
purge before each test block + embargo after. Not full PBO / event CPCV.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Any

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.holdout import MIN_IS_BARS, MIN_OOS_BARS
from bolsa_analytics.optimize.walk_forward import aggregate_walk_forward_metrics

CPCV_GROUPS_MIN = 4
CPCV_GROUPS_MAX = 6
CPCV_TEST_GROUPS = 2
CPCV_PURGE_DEFAULT = 5
CPCV_EMBARGO_DEFAULT = 5
CPCV_PURGE_MAX = 20
CPCV_EMBARGO_MAX = 20


@dataclass(frozen=True, slots=True)
class CpcvPath:
    """Partición / fold: Cpcv Path."""
    index: int
    test_group_indices: tuple[int, ...]
    train_bars: list[BacktestBarInput]
    test_bars: list[BacktestBarInput]
    train_bar_count: int
    test_bar_count: int
    test_start_timestamp: str | None


def normalize_cpcv_groups(n_groups: int | None) -> int | None:
    """Return None when off; otherwise clamp to [4, 6]."""
    if n_groups is None:
        return None
    value = int(n_groups)
    if value <= 0:
        return None
    return max(CPCV_GROUPS_MIN, min(CPCV_GROUPS_MAX, value))


def normalize_cpcv_gap(bars: int | None, *, default: int, upper: int) -> int:
    """Normaliza ``cpcv_gap``."""
    if bars is None:
        return default
    return max(0, min(upper, int(bars)))


def estimate_cpcv_path_count(n_groups: int, n_test_groups: int = CPCV_TEST_GROUPS) -> int:
    """Estima ``cpcv_path_count``."""
    resolved = normalize_cpcv_groups(n_groups)
    if resolved is None:
        return 0
    return comb(resolved, n_test_groups)


def _ts(bar: BacktestBarInput) -> str:
    ts = bar.timestamp
    return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)


def _group_ranges(n: int, n_groups: int) -> list[tuple[int, int]]:
    seg = n // n_groups
    ranges: list[tuple[int, int]] = []
    for g in range(n_groups):
        start = g * seg
        end = n if g == n_groups - 1 else (g + 1) * seg
        ranges.append((start, end))
    return ranges


def split_cpcv_paths(
    bars: list[BacktestBarInput],
    n_groups: int | None,
    *,
    purge_bars: int | None = None,
    embargo_bars: int | None = None,
    n_test_groups: int = CPCV_TEST_GROUPS,
) -> list[CpcvPath]:
    """Build combinatorial purged paths (train/test bar lists per combo)."""
    resolved = normalize_cpcv_groups(n_groups)
    if resolved is None:
        return []

    purge = normalize_cpcv_gap(
        purge_bars, default=CPCV_PURGE_DEFAULT, upper=CPCV_PURGE_MAX
    )
    embargo = normalize_cpcv_gap(
        embargo_bars, default=CPCV_EMBARGO_DEFAULT, upper=CPCV_EMBARGO_MAX
    )
    if n_test_groups != CPCV_TEST_GROUPS:
        raise ValueError(f"CPCV ligero solo soporta n_test_groups={CPCV_TEST_GROUPS}")

    n = len(bars)
    seg = n // resolved
    if seg < MIN_OOS_BARS:
        raise ValueError(
            f"CPCV {resolved} grupos: cada grupo necesita ≥{MIN_OOS_BARS} barras "
            f"(hay {n}; sube barLimit o baja cpcvGroups)"
        )
    if seg * (resolved - n_test_groups) < MIN_IS_BARS:
        raise ValueError(
            "CPCV: train estimado demasiado corto. Sube barLimit o baja cpcvGroups."
        )

    ranges = _group_ranges(n, resolved)
    paths: list[CpcvPath] = []
    path_index = 0
    for test_combo in combinations(range(resolved), n_test_groups):
        path_index += 1
        test_mask = [False] * n
        for g in test_combo:
            start, end = ranges[g]
            for i in range(start, end):
                test_mask[i] = True

        train_mask = [not t for t in test_mask]
        for g in test_combo:
            start, end = ranges[g]
            for i in range(max(0, start - purge), start):
                train_mask[i] = False
            for i in range(end, min(n, end + max(purge, embargo))):
                # After test: purge neighborhood + embargo gap (bar-level ligero).
                train_mask[i] = False
            # Never keep test bars in train.
            for i in range(start, end):
                train_mask[i] = False

        train_bars = [bars[i] for i in range(n) if train_mask[i]]
        test_bars = [bars[i] for i in range(n) if test_mask[i]]
        if len(train_bars) < MIN_IS_BARS or len(test_bars) < MIN_OOS_BARS:
            raise ValueError(
                f"CPCV path {path_index}: train={len(train_bars)} test={len(test_bars)} "
                f"(mín. {MIN_IS_BARS}/{MIN_OOS_BARS}) tras purge/embargo"
            )
        paths.append(
            CpcvPath(
                index=path_index,
                test_group_indices=tuple(g + 1 for g in test_combo),
                train_bars=train_bars,
                test_bars=test_bars,
                train_bar_count=len(train_bars),
                test_bar_count=len(test_bars),
                test_start_timestamp=_ts(test_bars[0]) if test_bars else None,
            )
        )
    return paths


def aggregate_cpcv_metrics(
    *,
    is_scores: list[float],
    oos_scores: list[float],
) -> dict[str, Any]:
    """Reuse WF aggregate keys (mean/std/WFE/CV/share) for CPCV paths."""
    return aggregate_walk_forward_metrics(is_scores=is_scores, oos_scores=oos_scores)
