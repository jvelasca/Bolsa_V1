"""Hold-out split helpers for optimize IS/OOS."""

from datetime import UTC, datetime, timedelta

import pytest

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_analytics.optimize.holdout import normalize_oos_pct, split_holdout_bars


def _bars(n: int) -> list[BacktestBarInput]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        BacktestBarInput(
            timestamp=(start + timedelta(days=i)).isoformat(),
            close=100.0 + i * 0.1,
        )
        for i in range(n)
    ]


def test_normalize_oos_pct_off() -> None:
    assert normalize_oos_pct(None) is None
    assert normalize_oos_pct(0) is None
    assert normalize_oos_pct(-0.1) is None


def test_normalize_oos_pct_clamps() -> None:
    assert normalize_oos_pct(0.05) == 0.1
    assert normalize_oos_pct(0.2) == 0.2
    assert normalize_oos_pct(0.9) == 0.4


def test_split_holdout_chronological() -> None:
    split = split_holdout_bars(_bars(200), 0.2)
    assert split is not None
    assert split.is_bar_count + split.oos_bar_count == 200
    assert split.is_bars[-1].timestamp < split.oos_bars[0].timestamp
    assert split.oos_bar_count >= 30
    assert split.is_bar_count >= 50
    assert split.split_timestamp is not None
    assert isinstance(split.split_timestamp, str)


def test_split_holdout_too_short() -> None:
    with pytest.raises(ValueError, match="Hold-out"):
        split_holdout_bars(_bars(60), 0.4)
