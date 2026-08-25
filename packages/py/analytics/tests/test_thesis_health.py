"""Ciclo 5.0 — Thesis Health mapper (Golden F thin)."""

from __future__ import annotations

from bolsa_analytics.cognitive.thesis_health import map_thesis_health


def test_golden_f_degraded_and_stop_intact_is_review() -> None:
    out = map_thesis_health(
        confidence=0.3,
        direction="long",
        last_close=100.0,
        structural_stop=90.0,
    )
    assert out["hint"] == "reduce"
    assert out["status"] == "review"
    assert "confidence_degraded" in out["why"]
    assert "stop_intact" in out["why"]


def test_degraded_but_stop_broken_is_ok() -> None:
    out = map_thesis_health(
        confidence=0.2,
        direction="long",
        last_close=85.0,
        structural_stop=90.0,
    )
    assert out["hint"] == "exit"
    assert out["status"] == "ok"
    assert "stop_intact" not in out["why"]


def test_hold_with_stop_intact_is_ok() -> None:
    out = map_thesis_health(
        confidence=0.8,
        direction="long",
        last_close=100.0,
        structural_stop=90.0,
    )
    assert out["hint"] == "hold"
    assert out["status"] == "ok"


def test_missing_stop_does_not_invent_review() -> None:
    out = map_thesis_health(
        confidence=0.2,
        direction="long",
        last_close=100.0,
        structural_stop=None,
    )
    assert out["status"] == "ok"
    assert out["hint"] == "exit"
