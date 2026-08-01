"""Walk-forward fold helpers for optimize."""

from datetime import UTC, datetime, timedelta

import pytest

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.walk_forward import (
    aggregate_oos_scores,
    aggregate_walk_forward_metrics,
    fold_walk_forward_efficiency,
    normalize_walk_forward_folds,
    split_walk_forward_bars,
)


def _bars(n: int) -> list[BacktestBarInput]:
    start = datetime(2018, 1, 1, tzinfo=UTC)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + i * 0.05,
        )
        for i in range(n)
    ]


def test_normalize_walk_forward_folds_off() -> None:
    assert normalize_walk_forward_folds(None) is None
    assert normalize_walk_forward_folds(0) is None
    assert normalize_walk_forward_folds(-1) is None


def test_normalize_walk_forward_folds_clamps() -> None:
    assert normalize_walk_forward_folds(1) == 2
    assert normalize_walk_forward_folds(3) == 3
    assert normalize_walk_forward_folds(9) == 5


def test_split_walk_forward_expanding() -> None:
    folds = split_walk_forward_bars(_bars(400), 3)
    assert len(folds) == 3
    # Expanding train
    assert folds[0].train_bar_count < folds[1].train_bar_count < folds[2].train_bar_count
    assert folds[0].test_bars[0].timestamp > folds[0].train_bars[-1].timestamp
    # Last fold absorbs leftovers
    total_covered = folds[-1].train_bar_count + folds[-1].test_bar_count
    assert total_covered == 400
    assert all(f.test_start_timestamp for f in folds)


def test_split_walk_forward_too_short() -> None:
    with pytest.raises(ValueError, match="Walk-forward"):
        split_walk_forward_bars(_bars(100), 4)


def test_aggregate_oos_scores() -> None:
    summary = aggregate_oos_scores([10.0, 12.0, 8.0])
    assert summary["foldCount"] == 3
    assert summary["meanOosScore"] == 10.0
    assert summary["stdOosScore"] > 0
    assert summary["foldScores"] == [10.0, 12.0, 8.0]
    assert summary["walkForwardEfficiency"] is None


def test_fold_walk_forward_efficiency() -> None:
    assert fold_walk_forward_efficiency(10.0, 7.0) == 0.7
    assert fold_walk_forward_efficiency(0.0, 5.0) is None
    assert fold_walk_forward_efficiency(-2.0, 1.0) is None


def test_aggregate_walk_forward_metrics_wfe_and_stability() -> None:
    summary = aggregate_walk_forward_metrics(
        is_scores=[10.0, 12.0, 8.0],
        oos_scores=[7.0, 6.0, 5.0],
    )
    assert summary["meanOosScore"] == 6.0
    assert summary["meanIsScore"] == 10.0
    assert summary["walkForwardEfficiency"] == 0.6
    assert summary["positiveOosFoldShare"] == 1.0
    assert summary["oosCv"] is not None
    assert summary["oosCv"] > 0


def test_aggregate_walk_forward_metrics_wfe_undefined_when_is_non_positive() -> None:
    summary = aggregate_walk_forward_metrics(
        is_scores=[-1.0, -2.0],
        oos_scores=[1.0, 2.0],
    )
    assert summary["walkForwardEfficiency"] is None
    assert summary["positiveOosFoldShare"] == 1.0


def test_aggregate_walk_forward_metrics_few_positive_folds() -> None:
    summary = aggregate_walk_forward_metrics(
        is_scores=[10.0, 10.0, 10.0, 10.0],
        oos_scores=[2.0, -1.0, -3.0, -4.0],
    )
    assert summary["positiveOosFoldShare"] == 0.25
    assert summary["walkForwardEfficiency"] < 0.5
