"""Tests de validación del payload coach de batería."""

from __future__ import annotations

from bolsa_ai.schemas import validate_backtest_coach_payload


def test_coach_payload_ok() -> None:
    errors = validate_backtest_coach_payload(
        {
            "headline": "ok",
            "analysis": ["a"],
            "outlook": ["o"],
            "audit": {"findings": [{"strategyType": "sma_crossover", "action": "veto"}]},
        },
    )
    assert errors == []


def test_coach_payload_rejects_bad_types() -> None:
    errors = validate_backtest_coach_payload(
        {
            "headline": 12,
            "analysis": "no-list",
            "audit": {"findings": [{"action": "explode"}]},
        },
    )
    assert any("headline" in e for e in errors)
    assert any("analysis" in e for e in errors)
    assert any("action" in e for e in errors)


def test_coach_payload_none_ok() -> None:
    assert validate_backtest_coach_payload(None) == []
