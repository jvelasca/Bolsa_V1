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


def test_signal_evaluator_source_carries_preset_key() -> None:
    """H1: con identidad exacta la fuente añade ``::<preset_key>`` (sin preset: histórica)."""
    base = _active_with_executable()
    with_preset = ActiveStrategy(
        version_id=base.version_id,
        candidate_id=base.candidate_id,
        instrument_id=base.instrument_id,
        name=base.name,
        definition=base.definition,
        preset_key="sma_crossover",
    )
    decider = make_active_strategy_decider(
        active=with_preset,
        watch=("AAA",),
        bars_by_symbol=lambda symbol: _closes([10.0] * 7 + [20.0]),
    )
    proposal = decider("AAA")
    assert proposal.action == "BUY"
    assert proposal.source == "active-strategy:ver-1::sma_crossover"


def test_signal_evaluator_holds_without_bars() -> None:
    decider = make_active_strategy_decider(
        active=_active_with_executable(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: [],
    )
    assert decider("AAA").action == "HOLD"


@dataclass
class _OhlcvBar:
    """Barra con rango y volumen (lo que el decisor recibía como cierre pelado)."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def _vwap_active() -> ActiveStrategy:
    """ACTIVE ``vwap_reclaim``: su señal depende del VOLUMEN, no solo del cierre."""
    return ActiveStrategy(
        version_id="ver-vwap",
        candidate_id="cand-vwap",
        instrument_id="AAA",
        name="VWAP",
        definition={
            "lot_qty": 100.0,
            "watch": ["AAA"],
            "executable": {
                "presetKey": "vwap_reclaim",
                "indicatorSpecs": [{"definitionId": "vwap", "parameters": {}}],
                "entries": {
                    "operator": "all",
                    "rules": [
                        {
                            "type": "price_vs_indicator",
                            "indicatorSpec": {"definitionId": "vwap", "parameters": {}},
                            "operator": "gt",
                            "signalKind": "entry_long",
                        }
                    ],
                },
                "exits": {
                    "operator": "all",
                    "rules": [
                        {
                            "type": "price_vs_indicator",
                            "indicatorSpec": {"definitionId": "vwap", "parameters": {}},
                            "operator": "lt",
                            "signalKind": "exit",
                        }
                    ],
                },
            },
        },
    )


def test_signal_evaluator_uses_the_real_ohlcv_not_close_only() -> None:
    """Regresión de la procedencia: con volumen real el decisor ve el VWAP y compra.

    Con solo cierres el motor sintetiza ``volume = 0``, el VWAP no existe y el decisor
    devolvía HOLD sobre una barra que el scan publicaba como compra.
    """
    bars = [
        _OhlcvBar(
            timestamp=f"2026-01-{i + 1:02d}",
            open=99.8,
            high=100.5,
            low=99.5,
            close=100.0,
            volume=1500.0,
        )
        for i in range(10)
    ]
    bars[-1] = _OhlcvBar(
        timestamp="2026-01-10", open=99.8, high=108.5, low=99.5, close=108.0, volume=1500.0
    )
    decider = make_active_strategy_decider(
        active=_vwap_active(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
    )
    assert decider("AAA").action == "BUY"


def test_signal_evaluator_close_only_bars_still_hold_on_vwap() -> None:
    """Control negativo: sin volumen el VWAP es ausente ⇒ HOLD (fail-closed, no se inventa).

    Fija que el fix no relaja el fail-closed: la barra sin ``volume`` no produce una compra
    fantasma; simplemente deja de ver un indicador que no puede calcular.
    """
    bars = [_Bar(timestamp=f"2026-01-{i + 1:02d}", close=100.0) for i in range(9)]
    bars.append(_Bar(timestamp="2026-01-10", close=108.0))
    decider = make_active_strategy_decider(
        active=_vwap_active(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
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


# ── B-3: el estado ``gated`` sale del libro real, no de replayar la ventana ──────


def _below_vwap_bars(count: int = 10) -> list[_OhlcvBar]:
    """Toda la serie por DEBAJO del VWAP: la salida se cumple, la entrada nunca.

    Es el caso del portador: la posición se abrió antes de la ventana, así que el replay
    ``gated`` no ve ninguna entrada y la salida queda muda.
    """
    return [
        _OhlcvBar(
            timestamp=f"2026-02-{index + 1:02d}",
            open=110.0 - index,
            high=110.0 - index,
            low=110.0 - index,
            close=110.0 - index,
            volume=1000.0,
        )
        for index in range(count)
    ]


def _above_vwap_bars(count: int = 9, last_close: float = 108.0) -> list[_OhlcvBar]:
    """Serie plana por encima del VWAP y un último cierre que mantiene la entrada."""
    bars = [
        _OhlcvBar(
            timestamp=f"2026-03-{index + 1:02d}",
            open=99.8,
            high=100.5,
            low=99.5,
            close=100.0,
            volume=1500.0,
        )
        for index in range(count)
    ]
    bars.append(
        _OhlcvBar(
            timestamp="2026-03-10",
            open=99.8,
            high=last_close + 0.5,
            low=99.5,
            close=last_close,
            volume=1500.0,
        )
    )
    return bars


def test_held_position_exits_without_an_entry_in_the_window() -> None:
    """B-3: con posición en el libro, la salida es una pregunta de NIVEL en la última barra.

    Sin ``long_by_symbol`` el replay arranca plano, nunca ve la entrada y la venta se
    suprime: el portador se queda atrapado en una posición que su regla pide cerrar.
    """
    bars = _below_vwap_bars()
    assert bars[-1].close < sum(b.close for b in bars) / len(bars)
    baseline = make_active_strategy_decider(
        active=_vwap_active(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
    )
    with_book = make_active_strategy_decider(
        active=_vwap_active(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
        long_by_symbol=lambda symbol: True,
    )

    assert baseline("AAA").action == "HOLD"
    proposal = with_book("AAA")
    assert proposal.action == "SELL"
    assert proposal.quantity == 100.0
    assert proposal.source == "active-strategy:ver-vwap"


def test_held_position_does_not_buy_what_it_already_holds() -> None:
    """B-3: la entrada de la última barra no se convierte en una compra de más."""
    bars = _above_vwap_bars()
    baseline = make_active_strategy_decider(
        active=_vwap_active(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
    )
    with_book = make_active_strategy_decider(
        active=_vwap_active(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
        long_by_symbol=lambda symbol: True,
    )

    assert baseline("AAA").action == "BUY"
    assert with_book("AAA").action == "HOLD"


def test_flat_book_keeps_the_previous_behaviour() -> None:
    """Sin posición abierta el decisor se comporta como antes de B-3."""
    bars = _above_vwap_bars()
    decider = make_active_strategy_decider(
        active=_vwap_active(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
        long_by_symbol=lambda symbol: False,
    )

    assert decider("AAA").action == "BUY"


def test_holds_when_the_book_cannot_be_read() -> None:
    """Un libro ilegible no inventa una venta (fail-closed, igual que el resto)."""

    def _boom(symbol: str) -> bool:
        raise RuntimeError("libro roto")

    decider = make_active_strategy_decider(
        active=_vwap_active(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: _below_vwap_bars(),
        long_by_symbol=_boom,
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
