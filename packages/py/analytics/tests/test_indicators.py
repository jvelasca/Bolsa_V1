import pytest

from bolsa_analytics.indicators import build_indicator_series, latest_indicator_signals, rsi, sma


def test_sma_matches_reference_window() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = sma(values, 3)
    assert result == [None, None, 2.0, 3.0, 4.0]


def test_rsi_insufficient_data_returns_nulls() -> None:
    values = [10.0, 11.0, 12.0]
    assert rsi(values, 14) == [None, None, None]


def test_build_indicator_series_length() -> None:
    timestamps = ["2024-01-01", "2024-01-02", "2024-01-03"]
    closes = [100.0, 101.0, 102.0]
    series = build_indicator_series(timestamps, closes)
    assert len(series) == 3
    assert series[0].timestamp == "2024-01-01"


def test_latest_indicator_signals_neutral_when_short_series() -> None:
    points = build_indicator_series(["2024-01-01"], [100.0])
    signals = latest_indicator_signals(points)
    assert signals.rsi_zone == "neutral"
    assert signals.sma_cross is None
