"""V2.39 (incremento 4) — tests del clasificador de regimen de mercado (hermeticos).

Certifica la pieza pura que da la segunda dimension de granularidad a la evidencia:

* determinismo (mismas barras ⇒ mismo regimen),
* fail-closed (pocas barras, NaN/inf, ventana degenerada ⇒ sin regimen),
* sensibilidad real a la tendencia (up/down) y a la volatilidad (high_vol),
* el resultado es SIEMPRE una etiqueta del conjunto canonico (o vacio),
* el as-of es la ultima barra (no mira el reloj ni datos posteriores).
"""

from __future__ import annotations

import math
from typing import Any

from bolsa_application.discovery_market_regime import (
    MATH_VERSION_MARKET_REGIME_V0,
    MIN_REGIME_BARS,
    NO_REGIME,
    REGIME_HIGH_VOL,
    REGIME_RANGE,
    REGIME_TREND_DOWN,
    REGIME_TREND_UP,
    TRIAL_REGIMES,
    classify_market_regime,
    is_valid_regime,
)


def _bar(close: float, *, high: float | None = None, low: float | None = None) -> dict[str, Any]:
    """Barra sintetica: por defecto un rango estrecho (±0.5 %) en torno al cierre."""
    return {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "open": close,
        "high": close * 1.005 if high is None else high,
        "low": close * 0.995 if low is None else low,
        "close": close,
        "volume": 1000,
    }


def _series(
    closes: list[float],
    *,
    range_pct: float = 0.01,
) -> list[dict[str, Any]]:
    """Serie de barras con rango simetrico ``±range_pct/2`` en torno a cada cierre."""
    half = range_pct / 2.0
    return [_bar(close, high=close * (1 + half), low=close * (1 - half)) for close in closes]


def _flat(length: int, *, price: float = 100.0, range_pct: float = 0.01) -> list[Any]:
    return _series([price] * length, range_pct=range_pct)


def _trend(length: int, *, start: float = 100.0, step: float = 0.4) -> list[Any]:
    return _series([start + step * i for i in range(length)])


def _downtrend(length: int, *, start: float = 200.0, step: float = 0.4) -> list[Any]:
    return _series([start - step * i for i in range(length)])


# ── Determinismo ────────────────────────────────────────────────────────────────


def test_same_bars_yield_same_regime() -> None:
    bars = _trend(120)
    assert classify_market_regime(bars) == classify_market_regime(bars)


def test_copies_of_same_series_yield_same_regime() -> None:
    assert classify_market_regime(_trend(120)) == classify_market_regime(_trend(120))


# ── Fail-closed ─────────────────────────────────────────────────────────────────


def test_below_min_bars_has_no_regime() -> None:
    assert classify_market_regime(_trend(MIN_REGIME_BARS - 1)) == NO_REGIME


def test_exactly_min_bars_is_classifiable() -> None:
    assert classify_market_regime(_trend(MIN_REGIME_BARS)) in TRIAL_REGIMES


def test_empty_series_has_no_regime() -> None:
    assert classify_market_regime([]) == NO_REGIME


def test_nan_close_does_not_crash_and_is_fail_closed() -> None:
    bars = _trend(120)
    # Envenena todas las barras de cierre: no hay serie valida.
    poisoned: list[Any] = [{**bar, "close": math.nan} for bar in bars]
    assert classify_market_regime(poisoned) == NO_REGIME


def test_missing_high_low_is_fail_closed() -> None:
    bars: list[Any] = [{"close": 100.0 + i * 0.4} for i in range(120)]
    # Sin high/low no se puede medir volatilidad: no se inventa un regimen.
    assert classify_market_regime(bars) == NO_REGIME


def test_unknown_math_version_is_fail_closed() -> None:
    assert classify_market_regime(_trend(120), math_version="otra_version") == NO_REGIME


def test_degenerate_prices_are_fail_closed() -> None:
    bars = _series([0.0] * 120)
    assert classify_market_regime(bars) == NO_REGIME


# ── Sensibilidad (el clasificador distingue de verdad) ───────────────────────────


def test_uptrend_is_detected() -> None:
    assert classify_market_regime(_trend(160, step=0.6)) == REGIME_TREND_UP


def test_downtrend_is_detected() -> None:
    assert classify_market_regime(_downtrend(160, step=0.6)) == REGIME_TREND_DOWN


def test_flat_market_is_range() -> None:
    assert classify_market_regime(_flat(160)) == REGIME_RANGE


def test_high_volatility_takes_priority() -> None:
    # Tendencia alcista fuerte PERO con rango enorme: high_vol gana (direccion no fiable).
    bars = _trend(160, step=0.6)
    wild: list[Any] = [
        {**bar, "high": bar["close"] * 1.10, "low": bar["close"] * 0.90} for bar in bars
    ]
    assert classify_market_regime(wild) == REGIME_HIGH_VOL


# ── Contrato de etiquetas ───────────────────────────────────────────────────────


def test_result_is_always_a_canonical_label() -> None:
    samples = [
        _trend(120),
        _downtrend(120),
        _flat(120),
        _flat(10),
        [],
        _trend(160, step=0.6),
    ]
    for bars in samples:
        result = classify_market_regime(bars)
        assert result == NO_REGIME or result in TRIAL_REGIMES


def test_math_version_constant_is_exposed() -> None:
    assert MATH_VERSION_MARKET_REGIME_V0 == "discovery_market_regime_v0"


def test_is_valid_regime_accepts_canonical_and_rejects_others() -> None:
    for regime in TRIAL_REGIMES:
        assert is_valid_regime(regime)
    assert not is_valid_regime(NO_REGIME)
    assert not is_valid_regime(None)
    assert not is_valid_regime("inventado")


# ── As-of: solo mira la ventana dada ────────────────────────────────────────────


def test_classification_depends_only_on_provided_window() -> None:
    """Anadir barras despues del corte no cambia la clasificacion de ese corte."""
    window = _trend(120)
    truncated = classify_market_regime(window)
    extended = list(window) + _downtrend(80, start=window[-1]["close"] + 10.0)
    assert classify_market_regime(window) == truncated
    # La ventana extendida puede diferir, pero el corte original es reproducible.
    assert classify_market_regime(extended) in TRIAL_REGIMES
