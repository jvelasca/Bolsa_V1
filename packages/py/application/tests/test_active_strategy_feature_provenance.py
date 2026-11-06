"""O-6 — procedencia de la feature y ventana declaradas por el decisor ACTIVE.

El journal sabía **qué** se decidió, no **con qué dato**. Estas pruebas fijan las dos
piezas del decisor: la clasificación pura ``real``/``synthetic`` de la ventana, y que el
``DecisionPackage`` la transporte —también en el ``HOLD``, que es la fila que hoy no se
puede distinguir de «no había señal»—.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bolsa_application.active_strategy_signal_evaluator import make_active_strategy_decider
from bolsa_application.signal_feature_context import (
    FEATURE_SOURCE_REAL,
    FEATURE_SOURCE_SYNTHETIC,
    feature_source,
)
from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy


@dataclass
class _CloseOnlyBar:
    """Barra sin OHLCV: el motor la sintetiza (``volume = 0``)."""

    timestamp: str
    close: float


@dataclass
class _OhlcvBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def _active() -> ActiveStrategy:
    return ActiveStrategy(
        version_id="ver-o6",
        candidate_id="cand-o6",
        instrument_id="AAA",
        name="RSI",
        definition={
            "lot_qty": 100.0,
            "watch": ["AAA"],
            "executable": {
                "presetKey": "rsi_mean_reversion",
                "indicatorSpecs": [{"definitionId": "rsi", "parameters": {"period": 14}}],
            },
        },
    )


def _real_bars(count: int = 30, *, last_close: float | None = None) -> list[_OhlcvBar]:
    bars = [
        _OhlcvBar(
            timestamp=f"2026-04-{i + 1:02d}",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
        for i in range(count)
    ]
    if last_close is not None:
        bars[-1] = _OhlcvBar(
            timestamp=bars[-1].timestamp,
            open=100.0,
            high=last_close + 1.0,
            low=99.0,
            close=last_close,
            volume=1_000.0,
        )
    return bars


def _decide(bars: list[Any], **kwargs: Any) -> Any:
    decider = make_active_strategy_decider(
        active=_active(),
        watch=("AAA",),
        bars_by_symbol=lambda symbol: bars,
        **kwargs,
    )
    return decider("AAA")


# ── Clasificación pura ──────────────────────────────────────────────────────────


def test_feature_source_is_real_with_full_ohlcv() -> None:
    assert feature_source(_real_bars()) == FEATURE_SOURCE_REAL


def test_feature_source_is_synthetic_with_close_only_bars() -> None:
    bars = [_CloseOnlyBar(timestamp=f"2026-04-{i + 1:02d}", close=100.0) for i in range(5)]
    assert feature_source(bars) == FEATURE_SOURCE_SYNTHETIC


def test_a_single_close_only_bar_taints_the_whole_window() -> None:
    """Los indicadores de rango/volumen se calculan sobre la ventana ENTERA.

    Una sola barra sin rango obliga a sintetizar esa barra, y el valor del indicador deja
    de ser el del dato. ``all`` y no ``any``: no se puede etiquetar de ``real`` una
    ventana que contiene una barra inventada.
    """
    bars: list[Any] = list(_real_bars())
    bars[3] = _CloseOnlyBar(timestamp="2026-04-04", close=100.0)
    assert feature_source(bars) == FEATURE_SOURCE_SYNTHETIC


def test_feature_source_is_none_without_bars() -> None:
    """No evaluado NO es ``synthetic``: sería afirmar una procedencia que no existió."""
    assert feature_source([]) is None


# ── El decisor declara en el paquete ────────────────────────────────────────────


def test_hold_declares_feature_source_and_window() -> None:
    """El HOLD es la fila que importa: sin esto no se distingue de «no había señal»."""
    bars = _real_bars()
    proposal = _decide(bars)
    assert proposal.action == "HOLD"
    assert proposal.feature_source == FEATURE_SOURCE_REAL
    assert proposal.signal_window_bars == len(bars)


def test_hold_on_close_only_bars_declares_synthetic() -> None:
    bars = [_CloseOnlyBar(timestamp=f"2026-04-{i + 1:02d}", close=100.0) for i in range(30)]
    proposal = _decide(bars)
    assert proposal.action == "HOLD"
    assert proposal.feature_source == FEATURE_SOURCE_SYNTHETIC
    assert proposal.signal_window_bars == 30


def test_warmup_hold_carries_both_the_reason_and_the_window() -> None:
    """B-1 + O-6: el motivo dice POR QUÉ y la ventana dice CON CUÁNTO se intentó."""
    from bolsa_analytics.research.manifest import strategy_definition_from_preset

    active = ActiveStrategy(
        version_id="ver-o6-warmup",
        candidate_id="cand-o6-warmup",
        instrument_id="AAA",
        name="golden_cross",
        definition={
            "lot_qty": 100.0,
            "watch": ["AAA"],
            "executable": strategy_definition_from_preset("golden_cross", ["AAA"]),
        },
    )
    bars = _real_bars(20)
    decider = make_active_strategy_decider(
        active=active, watch=("AAA",), bars_by_symbol=lambda symbol: bars
    )
    proposal = decider("AAA")
    assert proposal.action == "HOLD"
    assert "warmup_insufficient" in proposal.memo
    assert proposal.signal_window_bars == 20
    assert proposal.feature_source == FEATURE_SOURCE_REAL


def test_buy_also_declares_the_provenance() -> None:
    """No se declara solo cuando bloquea: cualquier decisión evaluada lleva el dato."""
    bars = _real_bars(last_close=60.0)
    proposal = _decide(bars)
    assert proposal.action == "BUY"
    assert proposal.feature_source == FEATURE_SOURCE_REAL
    assert proposal.signal_window_bars == len(bars)


def test_no_bars_publishes_no_provenance() -> None:
    """Sin ventana no hay procedencia que declarar: ``None``, no ``"synthetic"``."""
    decider = make_active_strategy_decider(
        active=_active(), watch=("AAA",), bars_by_symbol=lambda symbol: []
    )
    proposal = decider("AAA")
    assert proposal.action == "HOLD"
    assert proposal.feature_source is None
    assert proposal.signal_window_bars is None
