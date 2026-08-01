"""CPCV ligero helpers for optimize lab."""

from datetime import UTC, datetime, timedelta

import pytest

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.cpcv import (
    aggregate_cpcv_metrics,
    estimate_cpcv_path_count,
    normalize_cpcv_groups,
    split_cpcv_paths,
)


def _bars(n: int) -> list[BacktestBarInput]:
    start = datetime(2016, 1, 1, tzinfo=UTC)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + i * 0.04,
        )
        for i in range(n)
    ]


def test_normalize_cpcv_groups() -> None:
    assert normalize_cpcv_groups(None) is None
    assert normalize_cpcv_groups(0) is None
    assert normalize_cpcv_groups(3) == 4
    assert normalize_cpcv_groups(5) == 5
    assert normalize_cpcv_groups(9) == 6


def test_estimate_cpcv_path_count() -> None:
    assert estimate_cpcv_path_count(5) == 10
    assert estimate_cpcv_path_count(4) == 6
    assert estimate_cpcv_path_count(6) == 15


def test_split_cpcv_paths_combinatorial() -> None:
    paths = split_cpcv_paths(_bars(600), 5, purge_bars=5, embargo_bars=5)
    assert len(paths) == 10
    assert paths[0].test_group_indices == (1, 2)
    # Train and test disjoint
    train_ts = {b.timestamp for b in paths[0].train_bars}
    test_ts = {b.timestamp for b in paths[0].test_bars}
    assert train_ts.isdisjoint(test_ts)
    assert paths[0].train_bar_count >= 50
    assert paths[0].test_bar_count >= 30


def test_split_cpcv_purge_reduces_train() -> None:
    no_gap = split_cpcv_paths(_bars(600), 5, purge_bars=0, embargo_bars=0)
    with_gap = split_cpcv_paths(_bars(600), 5, purge_bars=10, embargo_bars=10)
    assert with_gap[0].train_bar_count < no_gap[0].train_bar_count


def test_split_cpcv_too_short() -> None:
    with pytest.raises(ValueError, match="CPCV"):
        split_cpcv_paths(_bars(120), 5)


def test_aggregate_cpcv_metrics_wfe() -> None:
    summary = aggregate_cpcv_metrics(
        is_scores=[10.0, 10.0],
        oos_scores=[7.0, 5.0],
    )
    assert summary["walkForwardEfficiency"] == 0.6
    assert summary["positiveOosFoldShare"] == 1.0
