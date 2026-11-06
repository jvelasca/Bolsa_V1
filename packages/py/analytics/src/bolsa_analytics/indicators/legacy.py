"""Indicadores legacy (SMA/EMA/RSI) usados por grids H0.

S9 (auditoría .183) — estas tres series alimentan los grids de optimización, es decir, la
elección de parámetros con la que después se opera. Se endurecen con una sola regla:

* ``period`` sin ventana (≤ 0, no entero) ⇒ ``[None] * n`` en vez de ``ZeroDivisionError``.
  Antes ``sma(values, 0)`` dividía por cero y ``ema(values, -1)`` reventaba en el propio
  ``k``: un parámetro basura del grid tumbaba el turno en vez de producir "sin indicador".
* Un valor no finito (``NaN``/``inf``) no es un dato ⇒ ese punto es ``None``. En ``ema``,
  además, un valor no finito **invalida la recursión** (la serie se re-siembra con la
  siguiente ventana completa de valores finitos): arrastrar un ``NaN`` dejaría el resto de
  la serie apagada para siempre, y sustituirlo por el último bueno sería inventar precios.
  En ``rsi`` ocurre lo mismo con los promedios de Wilder.
"""

from dataclasses import dataclass
from typing import Literal

from bolsa_analytics.indicators.validation import (
    invalid_period,
    is_finite,
    none_if_non_finite,
)

__all__ = [
    "IndicatorPoint",
    "IndicatorSignals",
    "build_indicator_series",
    "ema",
    "latest_indicator_signals",
    "rsi",
    "sma",
]


def sma(values: list[float], period: int) -> list[float | None]:

    """Indicador legacy ``sma``."""
    if invalid_period(period):
        return [None] * len(values)

    result: list[float | None] = []

    for i in range(len(values)):

        if i < period - 1:

            result.append(None)

            continue

        window = values[i - period + 1 : i + 1]
        if not all(is_finite(value) for value in window):
            # Una sola barra no finita contamina la media de TODA la ventana: la media de
            # (1, 2, NaN) no es 1.5 ni 3, es "no medible".
            result.append(None)
            continue

        result.append(none_if_non_finite(sum(window) / period))

    return result


def ema(values: list[float], period: int) -> list[float | None]:

    """Indicador legacy ``ema``."""
    if invalid_period(period):
        return [None] * len(values)

    result: list[float | None] = []

    k = 2 / (period + 1)

    prev_ema: float | None = None

    for i in range(len(values)):

        if i < period - 1:

            result.append(None)

            continue

        if prev_ema is None:
            window = values[i - period + 1 : i + 1]
            if not all(is_finite(value) for value in window):
                result.append(None)

                continue

            seed = none_if_non_finite(sum(window) / period)
            if seed is None:
                result.append(None)

                continue

            prev_ema = seed

            result.append(seed)

            continue

        close = values[i]
        if not is_finite(close):
            # El valor no es un dato: se declara el hueco y se invalida el estado para que
            # la serie se re-siembre con datos finitos en vez de arrastrar el ``NaN``.
            prev_ema = None

            result.append(None)

            continue

        prev_ema = none_if_non_finite(close * k + prev_ema * (1 - k))

        result.append(prev_ema)

    return result


def _rsi_value(avg_gain: float, avg_loss: float) -> float | None:
    if avg_loss == 0:
        return 100.0
    return none_if_non_finite(100 - 100 / (1 + avg_gain / avg_loss))


def rsi(values: list[float], period: int = 14) -> list[float | None]:

    """Indicador legacy ``rsi``.

    ``period <= 0`` no tiene ventana (antes: ``ZeroDivisionError`` en ``avg_gain /= period``).
    Un cambio entre valores no finitos no se mide: se declara ``None`` y se re-siembran los
    promedios con los siguientes ``period`` cambios finitos.
    """
    if invalid_period(period) or len(values) < period + 1:

        return [None] * len(values)

    result: list[float | None] = [None] * len(values)

    seed_gains: list[float] = []
    seed_losses: list[float] = []
    avg_gain = 0.0
    avg_loss = 0.0
    seeded = False

    for i in range(1, len(values)):

        prev = values[i - 1]
        curr = values[i]
        if not (is_finite(prev) and is_finite(curr)):
            seed_gains.clear()
            seed_losses.clear()
            seeded = False
            continue

        change = curr - prev
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0

        if not seeded:
            seed_gains.append(gain)
            seed_losses.append(loss)
            if len(seed_gains) < period:
                continue
            avg_gain = sum(seed_gains) / period
            avg_loss = sum(seed_losses) / period
            seed_gains.clear()
            seed_losses.clear()
            seeded = True
        else:
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

        result[i] = _rsi_value(avg_gain, avg_loss)

    return result


@dataclass(frozen=True, slots=True)
class IndicatorPoint:

    """Serie / evento: Indicator Point."""

    timestamp: str

    sma20: float | None

    sma50: float | None

    ema20: float | None

    rsi14: float | None


@dataclass(frozen=True, slots=True)
class IndicatorSignals:

    """Tipo analytics: Indicator Signals."""

    rsi_zone: Literal["overbought", "oversold", "neutral"]

    sma_cross: Literal["bullish", "bearish"] | None


def build_indicator_series(timestamps: list[str], closes: list[float]) -> list[IndicatorPoint]:

    """Construye ``indicator_series``."""
    sma20 = sma(closes, 20)

    sma50 = sma(closes, 50)

    ema20 = ema(closes, 20)

    rsi14 = rsi(closes, 14)

    return [

        IndicatorPoint(

            timestamp=timestamps[i],

            sma20=sma20[i],

            sma50=sma50[i],

            ema20=ema20[i],

            rsi14=rsi14[i],

        )

        for i in range(len(timestamps))

    ]


def latest_indicator_signals(points: list[IndicatorPoint]) -> IndicatorSignals:

    """Función pública ``latest_indicator_signals``."""
    if len(points) < 2:

        return IndicatorSignals(rsi_zone="neutral", sma_cross=None)

    last = points[-1]

    prev = points[-2]

    rsi_zone: Literal["overbought", "oversold", "neutral"] = "neutral"

    if last.rsi14 is not None:

        if last.rsi14 >= 70:

            rsi_zone = "overbought"

        elif last.rsi14 <= 30:

            rsi_zone = "oversold"

    sma_cross: Literal["bullish", "bearish"] | None = None

    if (

        last.sma20 is not None

        and last.sma50 is not None

        and prev.sma20 is not None

        and prev.sma50 is not None

    ):

        was_below = prev.sma20 < prev.sma50

        is_above = last.sma20 > last.sma50

        if was_below and is_above:

            sma_cross = "bullish"

        if not was_below and not is_above and prev.sma20 > prev.sma50 and last.sma20 < last.sma50:

            sma_cross = "bearish"

    return IndicatorSignals(rsi_zone=rsi_zone, sma_cross=sma_cross)
