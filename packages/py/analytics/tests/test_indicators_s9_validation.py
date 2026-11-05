"""S9 (auditoría .183) — un periodo sin ventana y un valor no finito NO entran al indicador.

Lo que se fija aquí, y por qué muerde:

* ``period`` 0 o negativo dividía por cero DENTRO del turno (``sma(values, 0)``,
  ``ema(values, -1)`` en el propio ``k``, ``rsi(..., 0)`` en ``avg_gain /= period``). El
  resultado no era "sin indicador": era una excepción que tumbaba la evaluación completa de
  la señal (y con ella el turno), por un parámetro basura del grid. Ahora esos periodos
  devuelven una serie de ``None``: no hay ventana, y por tanto no hay señal.
* ``NaN``/``inf`` no fallan: **apagan**. ``nan > 70`` y ``nan < 70`` son ambos ``False``, así
  que una serie contaminada deja de disparar la regla sin dejar rastro. Ahora el punto es
  ``None`` (ausencia declarada) y en ``ema``/``rsi`` el estado recursivo se invalida para que
  el ``NaN`` no deje apagada toda la cola de la serie.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import pytest

from bolsa_analytics.indicators.compute import (
    OhlcvBar,
    compute_adx,
    compute_aroon,
    compute_atr,
    compute_bears_power,
    compute_bollinger,
    compute_bulls_power,
    compute_cci,
    compute_donchian,
    compute_ema,
    compute_macd_line,
    compute_macd_signal_line,
    compute_mfi,
    compute_momentum,
    compute_roc,
    compute_rsi,
    compute_sma,
    compute_std_dev,
    compute_stoch_k,
    compute_stoch_rsi,
    compute_supertrend,
    compute_williams_r,
    compute_wma,
)
from bolsa_analytics.indicators.legacy import ema as legacy_ema
from bolsa_analytics.indicators.legacy import rsi as legacy_rsi
from bolsa_analytics.indicators.legacy import sma as legacy_sma
from bolsa_analytics.indicators.validation import (
    invalid_period,
    is_finite,
    sanitize_series,
)
from bolsa_analytics.signals.rules_engine import build_indicator_context

NAN = float("nan")
INF = float("inf")


def _bars(count: int = 60) -> list[OhlcvBar]:
    return [
        OhlcvBar(
            timestamp=f"2026-01-{1 + index % 28:02d}",
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1000.0 + index,
        )
        for index in range(count)
    ]


def _closes(count: int = 60) -> list[float]:
    return [100.5 + index for index in range(count)]


def _all_none(series: list[float | None]) -> bool:
    return all(value is None for value in series)


def _flat(result: Any) -> list[float | None]:
    """Aplana el resultado de los indicadores que devuelven varias líneas."""
    if isinstance(result, tuple):
        flattened: list[float | None] = []
        for line in result:
            flattened.extend(line)
        return flattened
    return list(result)


#: Cada indicador periódico del módulo ``compute`` con su llamada canónica. La lista es el
#: inventario: si mañana se añade uno y se olvida la guarda, basta con añadirlo aquí (y el
#: test falla con ``ZeroDivisionError`` en vez de «pasar» silenciosamente).
_PERIOD_CALLABLES: dict[str, Callable[[int], Any]] = {
    "sma": lambda p: compute_sma(_closes(), p),
    "ema": lambda p: compute_ema(_closes(), p),
    "wma": lambda p: compute_wma(_closes(), p),
    "rsi": lambda p: compute_rsi(_closes(), p),
    "momentum": lambda p: compute_momentum(_closes(), p),
    "std_dev": lambda p: compute_std_dev(_closes(), p),
    "roc": lambda p: compute_roc(_closes(), p),
    "atr": lambda p: compute_atr(_bars(), p),
    "cci": lambda p: compute_cci(_bars(), p),
    "stoch_k": lambda p: compute_stoch_k(_bars(), p),
    "williams_r": lambda p: compute_williams_r(_bars(), p),
    "mfi": lambda p: compute_mfi(_bars(), p),
    "bears": lambda p: compute_bears_power(_bars(), p),
    "bulls": lambda p: compute_bulls_power(_bars(), p),
    "donchian": lambda p: compute_donchian(_bars(), p),
    "adx": lambda p: compute_adx(_bars(), p),
    "aroon": lambda p: compute_aroon(_bars(), p),
    "bollinger": lambda p: compute_bollinger(_closes(), p, 2.0),
    "macd_line": lambda p: compute_macd_line(_closes(), p, 26),
    "macd_signal": lambda p: compute_macd_signal_line(_closes(), 12, 26, p),
    "supertrend": lambda p: compute_supertrend(_bars(), p, 3.0),
    "stoch_rsi": lambda p: compute_stoch_rsi(_closes(), 14, p, 3, 3),
}


@pytest.mark.parametrize("name", sorted(_PERIOD_CALLABLES))
@pytest.mark.parametrize("period", [0, -1, -14])
def test_a_period_without_a_window_returns_no_series_instead_of_raising(
    name: str, period: int
) -> None:
    """``period <= 0`` no tiene ventana: serie de ``None``, nunca ``ZeroDivisionError``."""
    result = _PERIOD_CALLABLES[name](period)

    assert _all_none(_flat(result)), f"{name} con period={period} inventó valores"


@pytest.mark.parametrize("name", sorted(_PERIOD_CALLABLES))
def test_a_valid_period_still_produces_values(name: str) -> None:
    """La guarda no puede convertir el indicador en inerte con parámetros válidos."""
    result = _PERIOD_CALLABLES[name](5)

    assert not _all_none(_flat(result)), f"{name} con period=5 no produce ningún valor"


def test_invalid_period_rejects_garbage_and_accepts_fractions_that_are_not_periods() -> None:
    for garbage in (0, -3, 0.5, "abc", None, NAN, INF):
        assert invalid_period(garbage) is True
    for valid in (1, 2, 14, 200, 14.0):
        assert invalid_period(valid) is False


def test_is_finite_rejects_nan_inf_and_bools() -> None:
    assert is_finite(1.0) is True
    assert is_finite(0) is True
    assert is_finite(NAN) is False
    assert is_finite(INF) is False
    assert is_finite(-INF) is False
    assert is_finite(True) is False
    assert is_finite("1.0") is False


# ── legacy (grids H0) ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("period", [0, -1])
def test_legacy_sma_ema_rsi_survive_a_period_without_a_window(period: int) -> None:
    values = [100.0, 101.0, 102.0, 103.0, 104.0]

    assert legacy_sma(values, period) == [None] * len(values)
    assert legacy_ema(values, period) == [None] * len(values)
    assert legacy_rsi(values, period) == [None] * len(values)


def test_legacy_sma_declares_a_window_with_a_non_finite_value_as_unmeasured() -> None:
    # Antes: ``nan`` se sumaba y la media de (1, 2, nan) salía ``nan`` (ni None ni número).
    assert legacy_sma([1.0, 2.0, NAN, 4.0, 5.0], 2) == [None, 1.5, None, None, 4.5]


def test_legacy_ema_reseeds_after_a_non_finite_value_instead_of_carrying_it() -> None:
    values = [10.0, 11.0, 12.0, NAN, 14.0, 15.0, 16.0]

    result = legacy_ema(values, 2)

    # seed en i=1 (media de 10,11), avance en i=2, hueco en i=3 (barra no finita) y re-siembra
    # con la ventana [14,15] en i=5: la cola NO queda contaminada.
    assert result[3] is None
    assert result[4] is None
    assert result[5] is not None
    assert result[6] is not None
    assert all(value is None or math.isfinite(value) for value in result)


def test_legacy_rsi_reseeds_after_a_non_finite_value() -> None:
    values = [10.0, 11.0, 12.0, NAN, 14.0, 15.0, 16.0]

    result = legacy_rsi(values, 2)

    assert result[2] is not None  # primer RSI medible
    assert result[3] is None  # el cambio toca un valor no finito
    assert result[6] is not None  # los promedios se re-sembraron
    assert all(value is None or math.isfinite(value) for value in result)


# ── el contexto de features (scan / alertas / decisor) no transporta NaN ────────────────


def test_build_indicator_context_sanitizes_a_non_finite_close() -> None:
    bars = [
        OhlcvBar(timestamp="t0", open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0),
        OhlcvBar(timestamp="t1", open=2.0, high=2.0, low=2.0, close=NAN, volume=1.0),
    ]

    context = build_indicator_context(
        bars, [{"definitionId": "sma", "parameters": {"period": 1}}]
    )

    series = context["sma::period=1"]
    assert series[0] == 1.0
    # Antes: ``nan`` llegaba al motor, que lo comparaba en silencio contra los umbrales.
    assert series[1] is None


def test_sanitize_series_keeps_length_and_only_replaces_non_finite() -> None:
    assert sanitize_series([1.0, NAN, None, INF, -INF, 0.0]) == [
        1.0,
        None,
        None,
        None,
        None,
        0.0,
    ]
