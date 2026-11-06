"""Validación de entradas de indicadores (S9 de la auditoría .183).

Regla única de este módulo, y motivo por el que existe:

* Un valor que **no es un número finito** no es un dato. ``NaN`` no falla: *apaga*.
  ``nan > 70`` y ``nan < 70`` son ambos ``False``, así que una serie contaminada no lanza
  nada — simplemente deja de disparar la regla, y la señal que se publica no es la que el
  operador cree estar leyendo. ``inf`` es peor: se propaga por sumas y comparaciones y
  convierte el indicador en un valor absurdo pero "numérico". Por eso un no finito se
  devuelve como ``None``: ausencia DECLARADA, que el motor ya sabe tratar (``None`` ⇒ la
  comparación no se cumple ⇒ no hay señal, que es el lado fail-closed).
* Un ``period`` que no define ventana (≤ 0, no entero o no finito) **no tiene serie**. Sin
  la guarda, ``sum(window) / period`` lanza ``ZeroDivisionError`` dentro del turno de un
  worker y tumba la evaluación entera de una señal; con la guarda devuelve ``[None] * n``:
  no hay indicador, y no hay señal.

Ninguna de las dos reglas inventa un valor: ni extrapola el último precio bueno ni recorta
la ventana a la medida. Se declara la ausencia.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

__all__ = [
    "invalid_period",
    "is_finite",
    "is_positive_finite",
    "none_if_non_finite",
    "sanitize_series",
]


def is_finite(value: object) -> bool:
    """True si ``value`` es un número real finito (``bool`` no es un número aquí)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:  # enteros gigantes que no caben en un float.
        return False


def none_if_non_finite(value: float | None) -> float | None:
    """``value`` si es finito; ``None`` si es ``NaN``/``inf`` o no es un número."""
    if value is None:
        return None
    return value if is_finite(value) else None


def sanitize_series(values: Iterable[float | None]) -> list[float | None]:
    """Serie con los no finitos convertidos en ``None`` (misma longitud, mismo orden)."""
    return [none_if_non_finite(value) for value in values]


def invalid_period(period: object) -> bool:
    """True si ``period`` no define una ventana: no numérico, no finito o ``< 1``.

    Es la guarda de TODOS los indicadores periódicos: sin ella un ``period`` 0 divide por
    cero y uno negativo produce una ventana invertida (una serie que "existe" pero que no
    corresponde a ninguna ventana real).
    """
    try:
        value = float(period)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    return not math.isfinite(value) or value < 1


def is_positive_finite(value: object) -> bool:
    """True si ``value`` es un número real finito y estrictamente positivo.

    La usan los parámetros que NO son periodos de ventana y sí admiten fracciones
    (``step``/``maxAf`` del PSAR, ``multiplier`` del SuperTrend): ``invalid_period`` no sirve
    ahí porque exige ``>= 1`` y rechazaría ``0.02``, que es el valor canónico.
    """
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and number > 0
