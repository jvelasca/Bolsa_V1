"""Ciclo 5.3 — MFE/MAE mapper thin."""

from __future__ import annotations

from bolsa_analytics.cognitive.mfe_mae import map_mfe_mae


def test_peak_from_bars_favorable() -> None:
    out = map_mfe_mae(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=108.0,
        bars=[{"high": 105.0, "low": 98.0}, {"high": 118.0, "low": 99.0}],
    )
    assert out["status"] == "favorable"
    assert out["mfeR"] == 1.8
    assert out["maeR"] == 0.2
    assert out["currentR"] == 0.8
    assert "peak_from_bars" in out["why"]
    assert "mfe_ge_1_5r" in out["why"]
    assert out["source"] == "bars"


def test_adverse_when_mae_ge_1r() -> None:
    out = map_mfe_mae(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=101.0,
        bars=[{"high": 102.0, "low": 88.0}],
    )
    assert out["status"] == "adverse"
    assert out["maeR"] == 1.2
    assert "mae_ge_1r" in out["why"]
    assert out["source"] == "bars"


def test_close_proxy_without_bars() -> None:
    out = map_mfe_mae(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=105.0,
    )
    assert out["status"] == "observe"
    assert out["mfeR"] == 0.5
    assert out["maeR"] == 0.0
    assert "close_proxy" in out["why"]
    assert out["source"] == "close_proxy"


def test_short_peak_from_bars() -> None:
    out = map_mfe_mae(
        direction="short",
        entry=100.0,
        structural_stop=110.0,
        last_close=95.0,
        bars=[{"high": 103.0, "low": 90.0}, {"high": 101.0, "low": 85.0}],
    )
    assert out["mfeR"] == 1.5
    assert out["maeR"] == 0.3
    assert out["status"] == "favorable"
    assert "peak_from_bars" in out["why"]
    assert out["source"] == "bars"


def test_missing_inputs_is_none() -> None:
    out = map_mfe_mae(direction="long", entry=100.0)
    assert out["status"] == "none"
    assert "missing_inputs" in out["why"]
    assert out["source"] == "none"
