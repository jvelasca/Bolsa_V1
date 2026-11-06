"""S8 (auditoría .183) — sin OHLCV completo, la ACTIVE no abre: HOLD ``insufficient_data``.

El hallazgo: ``signal_feature_context`` sintetiza ``open = high = low = close`` y
``volume = 0`` cuando la barra llega close-only. Para SMA/EMA/RSI da igual (solo usan el
cierre), pero ATR, CCI, Stochastic, Donchian, ADX, SuperTrend, Ichimoku, VWAP, OBV y MFI
**no tienen dato**: rango cero y volumen cero producen un número con la forma correcta y el
significado inventado (ATR 0, Stochastic 50 constante, VWAP inexistente).

Lo que se fija aquí:

1. Con una definición que exige rango o volumen y una ventana close-only, el decisor
   devuelve HOLD con ``hold_reason == "insufficient_data"`` (no ``no_signal``: no es que se
   evaluara y no hubiera nada, es que no había dato con el que evaluar).
2. El ``memo`` declara QUÉ falta (``rango``/``volume``), y la procedencia sigue declarándose.
3. Una estrategia de cierres (SMA) NO paga la guarda: se sigue evaluando como ayer.
4. La guarda veta ENTRAR, no REDUCIR: con posición abierta la salida se emite.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_application.active_strategy_signal_evaluator import make_active_strategy_decider
from bolsa_application.auto_reason_codes import ACTIVE_INSUFFICIENT_DATA
from bolsa_application.signal_feature_context import missing_bar_fields
from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

SYMBOL = "AAA"


@dataclass(frozen=True)
class _CloseOnlyBar:
    """Barra como la entrega un proveedor de solo cierres: no hay OHLCV que leer."""

    timestamp: str
    close: float


@dataclass(frozen=True)
class _NoVolumeBar:
    """Barra con rango real y sin volumen declarado."""

    timestamp: str
    close: float
    high: float
    low: float


def _close_only(step: float = 0.1, count: int = 80) -> list[_CloseOnlyBar]:
    return [
        _CloseOnlyBar(timestamp=f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}",
                      close=100.0 + step * index)
        for index in range(count)
    ]


def _no_volume(step: float = 0.1, count: int = 80) -> list[_NoVolumeBar]:
    return [
        _NoVolumeBar(
            timestamp=f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}",
            close=100.0 + step * index,
            high=100.5 + step * index,
            low=99.5 + step * index,
        )
        for index in range(count)
    ]


@dataclass(frozen=True)
class _FullBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def _full(count: int = 80) -> list[_FullBar]:
    return [
        _FullBar(
            timestamp=f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}",
            open=100.0 + 0.1 * index - 0.2,
            high=100.0 + 0.1 * index + 0.5,
            low=100.0 + 0.1 * index - 0.5,
            close=100.0 + 0.1 * index,
            volume=1000.0,
        )
        for index in range(count)
    ]


def _active(executable: dict[str, Any] | None) -> ActiveStrategy:
    definition: dict[str, Any] = {"lot_qty": 100.0, "watch": [SYMBOL]}
    if executable is not None:
        definition["executable"] = executable
    return ActiveStrategy(
        version_id="ver-s8",
        candidate_id="cand-s8",
        instrument_id=SYMBOL,
        name="s8",
        definition=definition,
    )


def _preset(preset: str) -> dict[str, Any]:
    return strategy_definition_from_preset(preset, [SYMBOL])


def _decide(
    executable: dict[str, Any],
    bars: list[Any],
    *,
    long: bool = False,
) -> Any:
    decider = make_active_strategy_decider(
        active=_active(executable),
        watch=(SYMBOL,),
        bars_by_symbol=lambda _symbol: bars,
        long_by_symbol=lambda _symbol: long,
    )
    return decider(SYMBOL)


# ── la guarda ───────────────────────────────────────────────────────────────────────────


def test_a_range_indicator_on_a_close_only_window_holds_with_insufficient_data() -> None:
    decision = _decide(_preset("stoch_oversold"), _close_only())

    assert decision.action == "HOLD"
    assert decision.quantity == 0
    assert decision.hold_reason == ACTIVE_INSUFFICIENT_DATA
    # El detalle dice QUÉ falta, y la procedencia sigue declarándose (O-6).
    assert decision.memo.startswith("insufficient_data:")
    assert "high_low" in decision.memo
    assert decision.feature_source == "synthetic"
    assert decision.signal_window_bars == 80


def test_a_volume_indicator_without_declared_volume_holds_with_insufficient_data() -> None:
    decision = _decide(_preset("vwap_reclaim"), _no_volume())

    assert decision.hold_reason == ACTIVE_INSUFFICIENT_DATA
    assert "volume" in decision.memo
    assert "high_low" not in decision.memo


def test_a_window_with_zero_volume_is_not_a_volume_measurement() -> None:
    bars = [replace(bar, volume=0.0) for bar in _full()]

    decision = _decide(_preset("vwap_reclaim"), bars)

    # ``volume = 0`` es un valor, pero no un flujo: VWAP no tendría nada que medir.
    assert decision.hold_reason == ACTIVE_INSUFFICIENT_DATA
    assert "volume" in decision.memo


def test_a_close_only_definition_does_not_pay_the_guard() -> None:
    """SMA/EMA/RSI solo usan el cierre: la ventana close-only SÍ les sirve."""
    decision = _decide(_preset("sma_crossover"), _close_only())

    assert decision.hold_reason != ACTIVE_INSUFFICIENT_DATA


def test_a_full_ohlcv_window_does_not_trigger_the_guard() -> None:
    decision = _decide(_preset("vwap_reclaim"), _full())

    assert decision.hold_reason != ACTIVE_INSUFFICIENT_DATA
    assert decision.feature_source == "real"


def test_the_guard_vetoes_openings_and_never_blocks_a_reduce(monkeypatch: Any) -> None:
    """Reducir riesgo no se veta por datos degradados (misma regla que M7).

    Se fija la DECISIÓN de la guarda (no la señal del preset): con la misma ventana
    close-only y la misma definición que exige rango, un ``entry_long`` se convierte en HOLD
    y un ``exit`` se emite. Así la prueba no depende de que un indicador fabricado produzca
    exactamente la señal que se quiere observar.
    """
    import bolsa_application.active_strategy_signal_evaluator as evaluator_module

    executable = _preset("stoch_oversold")

    monkeypatch.setattr(
        evaluator_module, "_evaluate_last_signal", lambda *a, **k: ("entry_long", None)
    )
    opening = _decide(executable, _close_only())
    assert opening.action == "HOLD"
    assert opening.hold_reason == ACTIVE_INSUFFICIENT_DATA

    monkeypatch.setattr(
        evaluator_module, "_evaluate_last_signal", lambda *a, **k: ("exit", None)
    )
    exiting = _decide(executable, _close_only(), long=True)
    assert exiting.action == "SELL"
    assert exiting.hold_reason is None


# ── el dueño de la tabla indicador → campos (sin drift con el motor) ────────────────────


def test_missing_bar_fields_only_demands_what_the_definition_uses() -> None:
    assert missing_bar_fields(_close_only(), {"indicatorSpecs": []}) == frozenset()
    assert missing_bar_fields(
        _close_only(), {"indicatorSpecs": [{"definitionId": "sma"}]}
    ) == frozenset()
    assert missing_bar_fields(
        _close_only(), {"indicatorSpecs": [{"definitionId": "atr"}]}
    ) == {"high_low"}
    assert missing_bar_fields(
        _full(), {"indicatorSpecs": [{"definitionId": "atr"}, {"definitionId": "vwap"}]}
    ) == frozenset()
    # Sin barras no se declara nada: no se evaluó, y esto no es "synthetic".
    assert missing_bar_fields([], {"indicatorSpecs": [{"definitionId": "atr"}]}) == frozenset()
