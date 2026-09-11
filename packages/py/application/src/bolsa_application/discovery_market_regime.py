"""V2.39 (incremento 4) — Regimen de mercado del LAB (clasificador determinista, as-of).

La evidencia adaptativa de V2.36-V2.38 se agrega por familia H0 (``preset_key``) y, desde
V2.38, por **region de parametros** (``familia|region``). Este modulo anade la segunda
dimension de granularidad que el relevo de V2.38 dejo apuntada: el **regimen de mercado**
bajo el que se evaluo cada trial.

Por que un regimen DERIVADO DE LAS BARRAS del trial (y no el regimen macro cognitivo):

* **El regimen macro NO es calculable as-of.** ``bolsa_analytics.cognitive.market_state``
  se alimenta de ``bolsa_market.macro_snapshot.fetch_macro_snapshot_dict``, que toma
  valores *live* de Yahoo (``date.today()``, ``closes[-1]``) y **no persiste serie
  historica**. Etiquetar un trial pasado con el regimen de hoy seria inventar dato
  (exactamente lo que V2.38 evito deliberadamente).
* **El regimen de barras SI es derivable y as-of.** En el punto del trial el LAB ya tiene
  las barras completas con las que evaluo (``RunSmaGridOptimize.execute``), y el corte
  as-of es la ultima barra de esa ventana. El clasificador es aritmetica pura sobre esas
  barras: determinista, reproducible y sin dependencias externas.

Invariantes del modulo:

* **Determinista y versionado**: mismas barras ⇒ mismo regimen, siempre. La formula lleva
  ``math_version`` para poder reproducir clasificaciones historicas.
* **Fail-closed**: barras insuficientes, valores no finitos o ventana degenerada NO
  reciben regimen (``""``); no se aproxima con la ventana parcial.
* **Un solo eje**: el clasificador emite exactamente una de cuatro etiquetas
  (``trend_up`` / ``trend_down`` / ``range`` / ``high_vol``), no una combinacion.
* **Sin LLM, sin red, sin BD**: aritmetica pura sobre la serie OHLC.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

# Version de la matematica del clasificador (separada del esquema persistido): permite
# auditar con que formula se derivo un regimen y reproducirlo. Analoga a
# ``MATH_VERSION_PARAM_REGION_V0``.
MATH_VERSION_MARKET_REGIME_V0 = "discovery_market_regime_v0"

# Etiquetas del unico eje de regimen. El orden es el canonico (y el de la documentacion).
REGIME_TREND_UP = "trend_up"
REGIME_TREND_DOWN = "trend_down"
REGIME_RANGE = "range"
REGIME_HIGH_VOL = "high_vol"

TRIAL_REGIMES: tuple[str, ...] = (
    REGIME_TREND_UP,
    REGIME_TREND_DOWN,
    REGIME_RANGE,
    REGIME_HIGH_VOL,
)

# Sin regimen: fail-closed (barras insuficientes o degeneradas). Compatibilidad con la
# agregacion historica: la clave de evidencia no cambia cuando no hay regimen.
NO_REGIME = ""

# --- Parametros del clasificador (deterministas y conservadores) --------------------
#
# Ventanas cortas a proposito: el objetivo es clasificar el tramo que el trial realmente
# evaluo, no estimar un ciclo macro. Valores fijos y documentados; cualquier cambio exige
# un nuevo ``math_version``.

# Minimo de barras para clasificar. Por debajo, fail-closed.
MIN_REGIME_BARS = 60
# Ventana larga (tendencia) y corta (confirmacion), en barras.
_LONG_WINDOW = 40
_SHORT_WINDOW = 10
# Ventana de volatilidad (rango verdadero medio), en barras.
_VOL_WINDOW = 14
# Umbral de pendiente normalizada para declarar tendencia (|slope| / vol).
_TREND_SLOPE_THRESHOLD = 0.5
# Umbral de volatilidad relativa (rango medio / precio) para declarar ``high_vol``.
_HIGH_VOL_RATIO_THRESHOLD = 0.045


def _as_finite(value: Any) -> float | None:
    """Convierte a float finito; ``None``/no numerico/NaN/inf ⇒ ``None`` (ausente)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or math.isinf(number):
        return None
    return number


def _field(bar: Any, name: str) -> float | None:
    """Lee un campo de una barra (dataclass, Mapping o atributo); ``None`` si falta."""
    if bar is None:
        return None
    if isinstance(bar, dict):
        value = bar.get(name)
    else:
        value = getattr(bar, name, None)
    return _as_finite(value)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _range_ratio(bars: Sequence[Any]) -> float | None:
    """Volatilidad relativa: media de ``(high - low) / close`` en la ventana de volatilidad.

    ``None`` si no hay barras suficientes con high/low/close finitos. Fail-safe: se
    ignoran las barras incompletas, y si quedan menos de 2 no se clasifica.
    """
    window = bars[-_VOL_WINDOW:] if len(bars) >= _VOL_WINDOW else bars
    ratios: list[float] = []
    for bar in window:
        high = _field(bar, "high")
        low = _field(bar, "low")
        close = _field(bar, "close")
        if high is None or low is None or close is None or close <= 0:
            continue
        ratios.append((high - low) / close)
    if len(ratios) < 2:
        return None
    return _mean(ratios)


def _normalized_slope(closes: Sequence[float], *, vol_ratio: float) -> float | None:
    """Pendiente relativa de la tendencia, normalizada por la volatilidad.

    Compara la media corta con la larga y la escala por la volatilidad relativa, de modo
    que la misma deriva en precio no se lea igual en un mercado tranquilo que en uno
    revuelto. ``None`` si no hay barras suficientes.
    """
    if len(closes) < _LONG_WINDOW:
        return None
    short = _mean(closes[-_SHORT_WINDOW:])
    long = _mean(closes[-_LONG_WINDOW:])
    if long <= 0:
        return None
    scale = vol_ratio if vol_ratio > 0 else 1e-9
    return (short - long) / long / scale


def classify_market_regime(
    bars: Sequence[Any],
    *,
    math_version: str = MATH_VERSION_MARKET_REGIME_V0,
) -> str:
    """Clasifica el regimen de mercado del tramo cubierto por ``bars`` (as-of, puro).

    El as-of es la ultima barra de ``bars``: el clasificador solo mira la ventana dada,
    nunca datos posteriores ni el reloj. Devuelve una de ``TRIAL_REGIMES`` o ``NO_REGIME``.

    Reglas (un solo eje, en este orden):

    1. **Fail-closed**: menos de ``MIN_REGIME_BARS`` barras, o volatilidad/cierre no
       calculables ⇒ ``""``. No se aproxima con la ventana parcial.
    2. ``high_vol`` si la volatilidad relativa supera ``_HIGH_VOL_RATIO_THRESHOLD``.
       Tiene prioridad: en un mercado revuelto la direccion es poco fiable.
    3. ``trend_up`` / ``trend_down`` si la pendiente normalizada supera el umbral, con el
       signo correspondiente.
    4. ``range`` en cualquier otro caso.

    Determinista: la misma ``bars`` produce siempre el mismo resultado.
    """
    if math_version != MATH_VERSION_MARKET_REGIME_V0:
        # Version desconocida: fail-closed, no se inventa una clasificacion.
        return NO_REGIME
    series = list(bars or [])
    if len(series) < MIN_REGIME_BARS:
        return NO_REGIME
    closes = [c for c in (_field(bar, "close") for bar in series) if c is not None]
    if len(closes) < _LONG_WINDOW:
        return NO_REGIME
    vol_ratio = _range_ratio(series)
    if vol_ratio is None:
        return NO_REGIME
    if vol_ratio > _HIGH_VOL_RATIO_THRESHOLD:
        return REGIME_HIGH_VOL
    slope = _normalized_slope(closes, vol_ratio=vol_ratio)
    if slope is None:
        return NO_REGIME
    if slope >= _TREND_SLOPE_THRESHOLD:
        return REGIME_TREND_UP
    if slope <= -_TREND_SLOPE_THRESHOLD:
        return REGIME_TREND_DOWN
    return REGIME_RANGE


def is_valid_regime(regime: str | None) -> bool:
    """True si ``regime`` es una etiqueta del conjunto canonico (no vacio ni desconocido)."""
    return str(regime or "") in TRIAL_REGIMES
