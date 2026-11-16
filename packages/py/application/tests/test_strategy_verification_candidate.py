"""Tests de la candidata point-in-time y del shadow forward (Fase 4, ADR-050)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from bolsa_analytics.backtest import BacktestBarInput
from bolsa_application.dia_d_as_run import AsRunLeg
from bolsa_application.strategy_verification_candidate import (
    GAP_DEFINITION_UNAVAILABLE,
    GAP_NO_FORWARD_BARS,
    GAP_NOT_POINT_IN_TIME,
    GAP_NOT_PROVIDED,
    GAP_VERSION_UNAVAILABLE,
    CandidateSnapshot,
    candidate_gap_reason,
    load_candidate_snapshot,
    run_candidate_shadow_forward,
)

DAY = "2026-01-01"
UNIVERSE = ("AAA", "BBB")


def _snapshot(**overrides: object) -> CandidateSnapshot:
    base: dict[str, object] = {
        "candidate_id": "cand-1",
        "as_of": "2025-12-15",
        "strategy_version": "v7",
        "instrument_id": "AAA",
        "legs": (
            AsRunLeg(
                instrument_id="AAA",
                direction="long",
                quantity=10.0,
                entry=100.0,
                structural_stop=95.0,
            ),
        ),
    }
    base.update(overrides)
    return CandidateSnapshot(**base)  # type: ignore[arg-type]


def test_missing_candidate_declares_the_gap() -> None:
    assert (
        candidate_gap_reason(None, day=DAY, universe_instruments=UNIVERSE) == GAP_NOT_PROVIDED
    )


def test_candidate_built_after_d_is_not_measurable() -> None:
    snapshot = _snapshot(as_of="2026-01-02")
    assert (
        candidate_gap_reason(snapshot, day=DAY, universe_instruments=UNIVERSE)
        == GAP_NOT_POINT_IN_TIME
    )


def test_candidate_without_version_declares_the_gap() -> None:
    snapshot = _snapshot(strategy_version=None)
    assert (
        candidate_gap_reason(snapshot, day=DAY, universe_instruments=UNIVERSE)
        == GAP_VERSION_UNAVAILABLE
    )


def test_candidate_outside_the_declared_universe_is_rejected() -> None:
    snapshot = _snapshot()
    reason = candidate_gap_reason(snapshot, day=DAY, universe_instruments=("BBB",))
    assert reason is not None and reason.startswith("candidate_outside_universe")


def test_candidate_on_the_same_day_is_point_in_time() -> None:
    assert candidate_gap_reason(_snapshot(as_of=DAY), day=DAY, universe_instruments=UNIVERSE) is None


def test_loader_round_trips_the_declared_json() -> None:
    payload = {
        "candidateId": "cand-9",
        "asOf": "2025-12-20",
        "strategyVersion": "v3",
        "instrumentId": "AAA",
        "legs": [
            {
                "instrumentId": "AAA",
                "direction": "long",
                "quantity": 5,
                "entry": 50.0,
                "structuralStop": 47.5,
            }
        ],
        "definition": {"presetKey": "x"},
    }
    snapshot = load_candidate_snapshot(payload)
    assert snapshot.candidate_id == "cand-9"
    assert snapshot.legs[0].structural_stop == 47.5
    assert snapshot.to_dict()["definitionHash"]


def _rising_bars(total: int = 120, *, start: str = "2026-01-02") -> list[BacktestBarInput]:
    origin = datetime.fromisoformat(start).replace(tzinfo=UTC)
    bars: list[BacktestBarInput] = []
    for day in range(total):
        price = Decimal(str(10 + day * 0.1))
        bars.append(
            BacktestBarInput(
                timestamp=(origin + timedelta(days=day)).isoformat(),
                open=price,
                high=price + Decimal("0.5"),
                low=price - Decimal("0.5"),
                close=price,
                volume=Decimal("1000"),
            )
        )
    return bars


def _operable_definition() -> dict[str, object]:
    from bolsa_application.discovery_grammar import COMPONENT_TRIGGER, enumerate_grammar_plans

    components = {
        component.name: component
        for plan in enumerate_grammar_plans()
        for component in plan.components
        if component.kind == COMPONENT_TRIGGER
    }
    trigger = components["trigger_dc20_break"]
    rules = trigger.build_rules()
    return {
        "presetKey": "verification_probe",
        "indicatorSpecs": trigger.build_specs(),
        "entries": {"operator": "all", "rules": rules},
        "exits": {
            "operator": "all",
            "rules": [
                {
                    "type": "price_compare",
                    "operator": "lt",
                    "value": 0.0,
                    "signalKind": "exit",
                }
            ],
        },
    }


def test_shadow_forward_without_definition_declares_the_gap() -> None:
    result = run_candidate_shadow_forward(
        _snapshot(), _rising_bars(), day=DAY
    )
    assert result.measured is False
    assert result.reason == GAP_DEFINITION_UNAVAILABLE


def test_shadow_forward_without_forward_bars_declares_the_gap() -> None:
    result = run_candidate_shadow_forward(
        _snapshot(definition=_operable_definition()),
        _rising_bars(total=5, start="2026-01-02"),
        day="2026-06-01",
    )
    assert result.measured is False
    assert result.reason == GAP_NO_FORWARD_BARS


def test_shadow_forward_measures_the_candidate_only_after_d() -> None:
    bars = _rising_bars()
    result = run_candidate_shadow_forward(
        _snapshot(definition=_operable_definition()),
        bars,
        day=DAY,
        window_bars=60,
    )
    assert result.measured is True
    assert result.bars_used == 60
    assert result.first_bar is not None and result.first_bar[:10] > DAY
    assert result.trades >= 1
    assert result.bars_hash


def test_shadow_forward_without_snapshot_declares_the_gap() -> None:
    result = run_candidate_shadow_forward(None, _rising_bars(), day=DAY)
    assert result.measured is False
    assert result.reason == GAP_NOT_PROVIDED
