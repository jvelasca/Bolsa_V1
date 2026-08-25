"""Ciclo 5.2 — Exit Radar mapper thin."""

from __future__ import annotations

from bolsa_analytics.cognitive.exit_radar import map_exit_radar


def test_exit_hint_beats_trail_on_thesis_exit() -> None:
    out = map_exit_radar(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=120.0,
        thesis_hint="exit",
        r_multiple=2.0,
    )
    assert out["status"] == "exit_hint"
    assert "thesis_exit" in out["why"]
    assert "mfe_ge_1_5r" in out["why"]


def test_beyond_target1_is_exit_hint() -> None:
    out = map_exit_radar(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=110.0,
        target1=110.0,
    )
    assert out["status"] == "exit_hint"
    assert "beyond_target1" in out["why"]


def test_expired_is_time_stop_hint() -> None:
    out = map_exit_radar(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=101.0,
        expires_at="2026-08-01T00:00:00Z",
        now_iso="2026-08-25T00:00:00Z",
    )
    assert out["status"] == "time_stop_hint"
    assert "expired" in out["why"]


def test_mfe_ge_1_5r_is_trail_hint() -> None:
    out = map_exit_radar(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=115.0,
    )
    assert out["status"] == "trail_hint"
    assert out["suggestedTrailStop"] == 105.0
    assert "mfe_ge_1_5r" in out["why"]


def test_below_thresholds_is_none() -> None:
    out = map_exit_radar(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=105.0,
    )
    assert out["status"] == "none"
    assert out["suggestedTrailStop"] is None
