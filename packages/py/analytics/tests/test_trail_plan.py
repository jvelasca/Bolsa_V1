"""Ciclo 8.1 — trail plan thin mapper."""

from __future__ import annotations

from bolsa_analytics.cognitive.trail_plan import map_trail_plan


def test_missing_inputs_none() -> None:
    out = map_trail_plan()
    assert out["status"] == "none"
    assert out["why"] == ["missing_inputs"]
    assert out["suggestedTrailStop"] is None


def test_peak_below_1_5r_none() -> None:
    out = map_trail_plan(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        peak_mfe_r=1.2,
    )
    assert out["status"] == "none"
    assert out["peakMfeR"] == 1.2
    assert "mfe_lt_1_5r" in out["why"]
    assert "not_permission" in out["why"]
    assert "hint_only" in out["why"]


def test_tip_aligned_exit_radar_at_1_5r() -> None:
    out = map_trail_plan(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        peak_mfe_r=1.5,
        current_r=1.2,
    )
    assert out["status"] == "tip"
    assert out["lockedR"] == 0.5
    assert out["suggestedTrailStop"] == 105.0
    assert out["trailDistanceR"] == 1.0
    assert "aligned_exit_radar_tip" in out["why"]
    assert "hint_only" in out["why"]


def test_ratchet_at_2_5r() -> None:
    out = map_trail_plan(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        peak_mfe_r=2.5,
    )
    assert out["status"] == "ratchet"
    assert out["lockedR"] == 1.5
    assert out["suggestedTrailStop"] == 115.0
    assert "ratchet_lock" in out["why"]


def test_short_ratchet() -> None:
    out = map_trail_plan(
        direction="short",
        entry=100.0,
        structural_stop=110.0,
        peak_mfe_r=2.0,
    )
    assert out["status"] == "ratchet"
    assert out["lockedR"] == 1.0
    assert out["suggestedTrailStop"] == 90.0


def test_current_r_fallback_peak() -> None:
    out = map_trail_plan(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        current_r=1.8,
    )
    assert out["status"] == "tip"
    assert out["peakMfeR"] == 1.8
    assert out["lockedR"] == 0.8
    assert out["suggestedTrailStop"] == 108.0


def test_v129_tight_trail_width() -> None:
    out = map_trail_plan(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        peak_mfe_r=2.0,
        trail_width="tight",
    )
    assert out["trailDistanceR"] == 0.75
    assert out["lockedR"] == 1.25
    assert out["suggestedTrailStop"] == 112.5


def test_v129_clamp_not_worsen() -> None:
    out = map_trail_plan(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        peak_mfe_r=1.5,
        current_stop=108.0,
    )
    assert out["suggestedTrailStop"] == 108.0
    assert "clamped_not_worsen" in out["why"]
