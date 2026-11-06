"""Contrato scan ↔ decisor: misma feature, misma señal, distinta proyección.

El scan evalúa la estrategia con OHLCV real y ``indicator_context``; el decisor ACTIVE
evaluaba solo cierres, y el motor sintetizaba ``open = high = low = close`` con
``volume = 0``. Sobre las mismas barras, los presets de volumen y rango (VWAP, SuperTrend,
CCI, Stoch) daban respuestas distintas: medido en esta matriz, **5 de 16** pares cambian de
acción respecto al camino close-only — 4 de ``vwap_reclaim`` (depende del volumen) y 1 de
``supertrend_follow`` (depende del rango ``high``/``low`` que el motor sintetizaba) — y
**3 de 16** pares muestran ``raw ≠ gated`` sobre la misma feature (B-3).

Lo que se certifica aquí, y nada más:

1. **Misma feature.** El decisor construye ``indicator_context`` de las MISMAS barras OHLCV
   que el scan (``signal_feature_context``). Si no lo hiciera, el caso ``vwap_reclaim`` de
   ``flat_spike_up`` devolvería HOLD en vez de BUY.
2. **Proyección ``gated``.** El decisor consume el motor en modo ``gated`` (con estado de
   cartera dentro de la ventana), así que su acción es la proyección de la misma señal —
   no el ``raw`` del scan. La divergencia ``raw``/``gated`` es B-3 y **no** se arregla aquí;
   se caracteriza en ``test_raw_and_gated_diverge_on_a_sustained_trend``.

Las series son deterministas y viven en memoria: ninguna prueba toca base de datos, ficheros
ni el estado de la ventana.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_analytics.signals.strategy import StrategyBarInput, evaluate_strategy_last_bar
from bolsa_application.active_strategy_signal_evaluator import make_active_strategy_decider
from bolsa_application.signal_feature_context import (
    build_signal_indicator_context,
    to_ohlcv_bars,
)
from bolsa_domain.entities.strategy_lifecycle import ActiveStrategy

SYMBOL = "AAA"
PRESETS = ("vwap_reclaim", "supertrend_follow", "cci_oversold", "stoch_oversold")
_BARS = 120


def _bars_from_closes(closes: list[float], *, spread: float = 0.5, volume: float = 1500.0) -> list[OhlcvBar]:
    """Serie OHLCV determinista con rango y volumen reales (no close-only)."""
    return [
        OhlcvBar(
            timestamp=f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}",
            open=close - spread * 0.4,
            high=close + spread,
            low=close - spread,
            close=close,
            volume=volume,
        )
        for i, close in enumerate(closes)
    ]


def _closes(scenario: str) -> list[float]:
    """Cierres por escenario. El ÚLTIMO bar es el que decide (el scan mira la última barra)."""
    if scenario == "flat_spike_up":
        values = [100.0] * _BARS
        values[-1] = values[-2] + 8.0
    elif scenario == "up_crash":
        values = [100.0 + 0.15 * i for i in range(_BARS)]
        values[-1] = values[-2] - 15.0
    elif scenario == "down_spike":
        values = [120.0 - 0.15 * i for i in range(_BARS)]
        values[-1] = values[-2] + 15.0
    elif scenario == "sawtooth_crash":
        values = [100.0 + 2.0 * math.sin(i / 2.0) for i in range(_BARS)]
        values[-1] = values[-2] - 6.0
    else:  # pragma: no cover - protege contra un id mal escrito en la parametrización
        raise AssertionError(f"escenario desconocido: {scenario}")
    return values


SCENARIOS = ("flat_spike_up", "up_crash", "down_spike", "sawtooth_crash")


def _definition(preset: str) -> dict[str, Any]:
    return strategy_definition_from_preset(preset, [SYMBOL])


def _strategy_bars(bars: list[OhlcvBar]) -> list[StrategyBarInput]:
    return [StrategyBarInput(timestamp=bar.timestamp, close=bar.close) for bar in bars]


def _expected_action(kinds: set[str]) -> str:
    """Proyección de la señal gated a la acción del decisor (``exit`` gana)."""
    if "exit" in kinds:
        return "SELL"
    if "entry_long" in kinds:
        return "BUY"
    return "HOLD"


def _decider(preset: str, bars: list[OhlcvBar]):
    definition = _definition(preset)
    active = ActiveStrategy(
        version_id="ver-contract",
        candidate_id="cand-contract",
        instrument_id=SYMBOL,
        name=preset,
        definition={
            "lot_qty": 100.0,
            "watch": [SYMBOL],
            "executable": definition,
        },
    )
    return make_active_strategy_decider(
        active=active,
        watch=(SYMBOL,),
        bars_by_symbol=lambda symbol: bars,
    )


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_decider_matches_the_gated_projection_of_the_same_signal(
    scenario: str, preset: str
) -> None:
    """16 pares: la acción del decisor == la proyección ``gated`` con el MISMO contexto."""
    bars = _bars_from_closes(_closes(scenario))
    definition = _definition(preset)

    # Referencia: exactamente lo que hace el decisor, con la feature del scan.
    context = build_signal_indicator_context(bars, definition)
    reference = evaluate_strategy_last_bar(
        definition,
        _strategy_bars(bars),
        instrument_id=SYMBOL,
        mode="gated",
        indicator_context=context,
    )
    expected = _expected_action({event.kind for event in reference})

    decision = _decider(preset, bars)(SYMBOL)

    assert decision.action == expected, (
        f"{scenario}/{preset}: decisor={decision.action} referencia={expected} "
        f"eventos={[event.kind for event in reference]}"
    )


def test_the_sixteen_pairs_are_not_a_no_op() -> None:
    """Los 16 pares deben ejercer el contrato: sin señales, la coincidencia sería trivial."""
    outcomes: dict[str, set[str]] = {preset: set() for preset in PRESETS}
    fired = 0
    for scenario in SCENARIOS:
        bars = _bars_from_closes(_closes(scenario))
        for preset in PRESETS:
            action = _decider(preset, bars)(SYMBOL).action
            outcomes[preset].add(action)
            fired += int(action != "HOLD")

    assert fired >= 12, (fired, outcomes)
    for preset in PRESETS:
        assert "BUY" in outcomes[preset], f"{preset} no ejerce ninguna compra: {outcomes[preset]}"
        assert "SELL" in outcomes[preset], f"{preset} no ejerce ninguna venta: {outcomes[preset]}"


def test_a_close_only_context_would_change_the_answer() -> None:
    """Anti-no-op de la feature: sin OHLCV, ``vwap_reclaim`` no ve el VWAP y no compra.

    Es la prueba de que el fix no es cosmético: el contexto construido desde OHLCV no es
    equivalente al que el motor sintetiza con cierres (``volume = 0`` ⇒ VWAP ausente).
    """
    bars = _bars_from_closes(_closes("flat_spike_up"))
    definition = _definition("vwap_reclaim")
    strategy_bars = _strategy_bars(bars)

    with_ohlcv = evaluate_strategy_last_bar(
        definition,
        strategy_bars,
        instrument_id=SYMBOL,
        mode="gated",
        indicator_context=build_signal_indicator_context(bars, definition),
    )
    close_only = evaluate_strategy_last_bar(
        definition, strategy_bars, instrument_id=SYMBOL, mode="gated"
    )

    assert [event.kind for event in with_ohlcv] == ["entry_long"]
    assert close_only == []
    assert _decider("vwap_reclaim", bars)(SYMBOL).action == "BUY"


def test_the_context_of_a_range_indicator_depends_on_high_and_low() -> None:
    """SuperTrend usa ``high``/``low``: con barras sintéticas cambia de valor."""
    bars = _bars_from_closes(_closes("down_spike"), spread=2.5)
    definition = _definition("supertrend_follow")

    real = build_signal_indicator_context(bars, definition)
    synthetic_bars = to_ohlcv_bars(
        [StrategyBarInput(timestamp=bar.timestamp, close=bar.close) for bar in bars]
    )
    synthetic = build_signal_indicator_context(synthetic_bars, definition)

    assert real, "el contexto de SuperTrend no puede quedar vacío"
    assert real != synthetic


def test_the_delta_of_the_fix_is_measured_and_declared() -> None:
    """Caracteriza el Δ del fix: 5/16 acciones cambian (``vwap_reclaim`` y ``supertrend_follow``).

    Es el número que se publica en la verificación. Se fija para que un cambio de presets,
    de barras o del contexto no altere la evidencia en silencio.
    """
    changed: list[tuple[str, str]] = []
    raw_differs = 0
    for scenario in SCENARIOS:
        bars = _bars_from_closes(_closes(scenario))
        strategy_bars = _strategy_bars(bars)
        for preset in PRESETS:
            definition = _definition(preset)
            context = build_signal_indicator_context(bars, definition)
            raw = evaluate_strategy_last_bar(
                definition, strategy_bars, instrument_id=SYMBOL, mode="raw", indicator_context=context
            )
            gated = evaluate_strategy_last_bar(
                definition, strategy_bars, instrument_id=SYMBOL, mode="gated", indicator_context=context
            )
            legacy = evaluate_strategy_last_bar(
                definition, strategy_bars, instrument_id=SYMBOL, mode="gated"
            )
            if _expected_action({event.kind for event in legacy}) != _expected_action(
                {event.kind for event in gated}
            ):
                changed.append((scenario, preset))
            raw_differs += int(sorted(e.kind for e in raw) != sorted(e.kind for e in gated))

    assert len(changed) == 5, changed
    assert {preset for _, preset in changed} == {"vwap_reclaim", "supertrend_follow"}, changed
    assert raw_differs == 3, raw_differs


def test_raw_and_gated_diverge_on_a_sustained_trend() -> None:
    """Caracterización de B-3: la divergencia ``raw``/``gated`` es de contrato, no un bug.

    En una tendencia sostenida, el scan (``raw``) publica ``entry_long`` en la última barra
    porque la condición se cumple; el ``gated`` no, porque ya entró al principio de la
    ventana y sigue dentro. El decisor hereda esa asimetría: **no puede** comprar una señal
    que el scan ve, ni vender una posición abierta antes de la ventana. Este test la fija
    para que el día que se cambie el contrato el cambio sea deliberado.
    """
    bars = _bars_from_closes([100.0 + 0.5 * i for i in range(_BARS)])
    definition = _definition("supertrend_follow")
    strategy_bars = _strategy_bars(bars)
    context = build_signal_indicator_context(bars, definition)

    raw = evaluate_strategy_last_bar(
        definition, strategy_bars, instrument_id=SYMBOL, mode="raw", indicator_context=context
    )
    gated = evaluate_strategy_last_bar(
        definition, strategy_bars, instrument_id=SYMBOL, mode="gated", indicator_context=context
    )

    assert [event.kind for event in raw] == ["entry_long"]
    assert gated == []
    assert _decider("supertrend_follow", bars)(SYMBOL).action == "HOLD"
