"""Ciclo 5.1 — Protect / T1 mapper (Golden E thin)."""

from __future__ import annotations

from bolsa_analytics.cognitive.protect_plan import map_protect_plan


def test_golden_e_long_mfe_ge_1r_is_protect_hint() -> None:
    out = map_protect_plan(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=110.0,
    )
    assert out["status"] == "protect_hint"
    assert out["target1"] == 110.0
    assert out["suggestedProtectStop"] == 100.0
    assert out["rMultiple"] == 1.0
    assert "mfe_ge_1r" in out["why"]


def test_long_below_1r_is_none() -> None:
    out = map_protect_plan(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=105.0,
    )
    assert out["status"] == "none"
    assert out["target1"] == 110.0
    assert out["suggestedProtectStop"] is None


def test_short_mfe_ge_1r_is_protect_hint() -> None:
    out = map_protect_plan(
        direction="short",
        entry=100.0,
        structural_stop=110.0,
        last_close=90.0,
    )
    assert out["status"] == "protect_hint"
    assert out["target1"] == 90.0
    assert out["suggestedProtectStop"] == 100.0


def test_missing_stop_is_none() -> None:
    out = map_protect_plan(
        direction="long",
        entry=100.0,
        structural_stop=None,
        last_close=110.0,
    )
    assert out["status"] == "none"
    assert "missing_inputs" in out["why"]
