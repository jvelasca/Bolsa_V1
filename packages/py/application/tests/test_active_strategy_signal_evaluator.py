"""V2.29 / A10 · V2.31/A11 — SignalEvaluator real de la ACTIVE (tests herméticos).

Certifica que la ACTIVE evalúa su propia señal cuando hay snapshot de barras, y que
ante ausencia de datos/definición ejecutable/error queda en **HOLD (NO TRADE)**: el
contrato V2.31/A11 es fail-closed y NUNCA hereda la acción de otra estrategia.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from bolsa_application.active_strategy_signal_evaluator import (
    make_active_strategy_decider,
    make_bar_snapshot_loader,
)
from bolsa_application.decision_contract import DecisionPackage
from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy


@dataclass
class _Bar:
    timestamp: str
    close: float


def _should_not_be_called(symbol: str) -> DecisionPackage:  # pragma: no cover
    raise AssertionError("el fallback al spine ya no debe existir (V2.31/A11)")


def _active_with_executable() -> ActiveStrategy:
    return ActiveStrategy(
        version_id="ver-1",
        candidate_id="cand-1",
        instrument_id="AAA",
        name="SMA",
        definition={
            "lot_qty": 100.0,
            "watch": ["AAA"],
            "executable": {
                "presetKey": "sma_crossover",
                "indicatorSpecs": [
                    {"definitionId": "sma", "parameters": {"period": 2}},
                    {"definitionId": "sma", "parameters": {"period": 4}},
                ],
                "entries": {
                    "operator": "all",
                    "rules": [
                        {
                            "type": "indicator_cross",
                            "leftSpec": {"definitionId": "sma", "parameters": {"period": 2}},
                            "rightSpec": {"definitionId": "sma", "parameters": {"period": 4}},
                            "direction": "bullish",
                            "signalKind": "entry_long",
                        }
                    ],
                },
                "exits": {
                    "operator": "all",
                    "rules": [
                        {
                            "type": "indicator_cross",
                            "leftSpec": {"definitionId": "sma", "parameters": {"period": 2}},
                            "rightSpec": {"definitionId": "sma", "parameters": {"period": 4}},
                            "direction": "bearish",
                            "signalKind": "exit",
                        }
                    ],
                },
            },
        },
    )


def _closes(values: list[float]) -> list[_Bar]:
    return [_Bar(timestamp=f"2026-01-{i + 1:02d}", close=v) for i, v in enumerate(values)]


def test_no_signal_on_last_bar_holds_instead_of_falling_back() -> None:
    """Sin señal en la última barra (serie plana) ⇒ HOLD, no se opera."""
    bars = _closes([10.0] * 10)
    decider = make_active_strategy_decider(
        active=_active_with_executable(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
    )
    proposal = decider("AAA")
    assert proposal.action == "HOLD"
    assert proposal.quantity == 0
    assert proposal.source == "active-strategy:ver-1"


def test_signal_evaluator_emits_entry_on_bullish_cross() -> None:
    # Serie plana y un último salto: la SMA corta cruza al alza la larga EN la última
    # barra (``evaluate_strategy_last_bar`` solo evalúa la última).
    bars = _closes([10.0] * 7 + [20.0])
    decider = make_active_strategy_decider(
        active=_active_with_executable(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
    )
    proposal = decider("AAA")
    assert proposal.action == "BUY"
    assert proposal.quantity == 100.0
    assert proposal.source == "active-strategy:ver-1"


def test_signal_evaluator_holds_without_bars() -> None:
    decider = make_active_strategy_decider(
        active=_active_with_executable(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: [],
    )
    assert decider("AAA").action == "HOLD"


def test_signal_evaluator_holds_without_executable() -> None:
    active = ActiveStrategy(
        version_id="ver-1",
        candidate_id="cand-1",
        instrument_id="AAA",
        name="SMA",
        definition={"lot_qty": 100.0, "watch": ["AAA"]},
    )
    decider = make_active_strategy_decider(
        active=active,
        watch=("AAA",),
        bars_by_symbol=lambda symbol: _closes([1.0, 2.0]),
    )
    assert decider("AAA").action == "HOLD"


def test_signal_evaluator_holds_outside_watch() -> None:
    decider = make_active_strategy_decider(
        active=_active_with_executable(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: _closes([1.0, 2.0]),
    )
    assert decider("BBB").action == "HOLD"


def test_signal_evaluator_holds_on_evaluation_error() -> None:
    """Una definición ejecutable corrupta no rompe el motor: HOLD (nunca otra estrategia)."""

    def _boom(symbol: str) -> list[_Bar]:
        raise RuntimeError("snapshot roto")

    decider = make_active_strategy_decider(
        active=_active_with_executable(),
        watch=("AAA",),
        bars_by_symbol=_boom,
    )
    assert decider("AAA").action == "HOLD"


def test_signal_evaluator_holds_without_snapshot_loader() -> None:
    decider = make_active_strategy_decider(
        active=_active_with_executable(),
        watch=("AAA",),
        bars_by_symbol=None,
    )
    assert decider("AAA").action == "HOLD"


# ── Snapshot loader ─────────────────────────────────────────────────────────────


class _FakeOhlcv:
    def __init__(self, bars_by_symbol: dict[str, list[_Bar]], *, raise_for: set[str] = frozenset()) -> None:
        self._bars = bars_by_symbol
        self._raise_for = raise_for
        self.calls: list[str] = []

    async def get_bars(self, instrument_id: str, *, timeframe=None, limit=None):  # type: ignore[no-untyped-def]
        self.calls.append(instrument_id)
        if instrument_id in self._raise_for:
            raise RuntimeError("sin datos")
        return self._bars.get(instrument_id, [])


@pytest.mark.asyncio
async def test_snapshot_loader_collects_bars_and_skips_failures() -> None:
    ohlcv = _FakeOhlcv(
        {"AAA": _closes([1.0, 2.0]), "BBB": []},
        raise_for={"CCC"},
    )
    refresh = make_bar_snapshot_loader(ohlcv, ["AAA", "BBB", "CCC"], limit=30)
    snapshot = await refresh()
    assert set(snapshot) == {"AAA"}
    assert ohlcv.calls == ["AAA", "BBB", "CCC"]
