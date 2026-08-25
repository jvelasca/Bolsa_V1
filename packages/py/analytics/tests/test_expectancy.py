"""Ciclo 8.0 — expectancy thin mapper."""

from __future__ import annotations

from bolsa_analytics.cognitive.expectancy import map_expectancy


def test_missing_inputs_none() -> None:
    out = map_expectancy()
    assert out["status"] == "none"
    assert out["n"] == 0
    assert out["why"] == ["missing_inputs"]


def test_live_proxy_thin_sample() -> None:
    out = map_expectancy(
        samples=[{"entrySetup": "breakout", "rMultiple": 0.8}],
        focus_setup="breakout",
        current_r=0.8,
    )
    assert out["status"] == "thin"
    assert out["n"] == 1
    assert out["expectancyR"] == 0.8
    assert out["winRate"] == 1.0
    assert out["avgWinR"] == 0.8
    assert out["avgLossR"] is None
    assert out["entrySetup"] == "breakout"
    assert "live_proxy" in out["why"]
    assert "thin_sample" in out["why"]
    assert "not_permission" in out["why"]


def test_aggregate_mean_r_and_ready() -> None:
    samples = [
        {"entrySetup": "pullback", "rMultiple": 1.0},
        {"entrySetup": "pullback", "rMultiple": -0.5},
        {"entrySetup": "pullback", "rMultiple": 2.0},
        {"entrySetup": "pullback", "rMultiple": -1.0},
        {"entrySetup": "pullback", "rMultiple": 0.5},
        {"entrySetup": "breakout", "rMultiple": 9.0},  # other setup ignored
    ]
    out = map_expectancy(samples=samples, focus_setup="pullback")
    assert out["status"] == "ready"
    assert out["n"] == 5
    assert out["expectancyR"] == 0.4  # (1 -0.5 +2 -1 +0.5) / 5
    assert out["winRate"] == 0.6
    assert out["avgWinR"] == round((1.0 + 2.0 + 0.5) / 3, 4)
    assert out["avgLossR"] == round((-0.5 + -1.0) / 2, 4)
    assert "aggregated" in out["why"]
    assert "not_permission" in out["why"]
    assert "thin_sample" not in out["why"]


def test_focus_none_setup_ignored() -> None:
    out = map_expectancy(
        samples=[{"entrySetup": "none", "rMultiple": 1.0}],
        focus_setup="none",
        current_r=1.0,
    )
    assert out["status"] == "none"
    assert out["why"] == ["missing_inputs"]


def test_snake_keys_accepted() -> None:
    out = map_expectancy(
        samples=[{"entry_setup": "wyckoff", "r_multiple": -0.2}],
        focus_setup="wyckoff",
        current_r=-0.2,
    )
    assert out["status"] == "thin"
    assert out["expectancyR"] == -0.2
    assert out["winRate"] == 0.0
    assert out["avgLossR"] == -0.2
