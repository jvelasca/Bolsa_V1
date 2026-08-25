"""Ciclo 8.2 — bracket plan thin mapper."""

from __future__ import annotations

from bolsa_analytics.cognitive.bracket_plan import map_bracket_plan
from bolsa_analytics.cognitive.protect_plan import map_protect_plan


def test_missing_inputs_none() -> None:
    out = map_bracket_plan()
    assert out["status"] == "none"
    assert out["why"] == ["missing_inputs"]
    assert out["target1"] is None
    assert out["legT1QtyFrac"] is None


def test_zero_r_none() -> None:
    out = map_bracket_plan(direction="long", entry=100.0, structural_stop=100.0)
    assert out["status"] == "none"
    assert out["why"] == ["missing_inputs"]


def test_long_picture_aligns_protect_t1() -> None:
    out = map_bracket_plan(direction="long", entry=100.0, structural_stop=90.0)
    assert out["status"] == "picture"
    assert out["entry"] == 100.0
    assert out["stop"] == 90.0
    assert out["target1"] == 110.0
    assert out["target2"] == 120.0
    assert out["target1R"] == 1.0
    assert out["target2R"] == 2.0
    assert out["legT1QtyFrac"] == 0.5
    assert out["legT2QtyFrac"] == 0.5
    assert "aligned_protect_t1" in out["why"]
    assert "display_only" in out["why"]
    assert "not_permission" in out["why"]
    assert "hint_only" in out["why"]
    assert "no_broker_oco" in out["why"]

    protect = map_protect_plan(
        direction="long",
        entry=100.0,
        structural_stop=90.0,
        last_close=105.0,
    )
    assert out["target1"] == protect["target1"]


def test_short_picture() -> None:
    out = map_bracket_plan(direction="short", entry=100.0, structural_stop=110.0)
    assert out["status"] == "picture"
    assert out["target1"] == 90.0
    assert out["target2"] == 80.0
