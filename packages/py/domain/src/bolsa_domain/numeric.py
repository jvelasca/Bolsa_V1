"""Normalización numérica **finita** para el camino de dinero (auditoría P9).

El patrón que había repartido por ``bolsa_analytics`` era::

    def _finite(x: float) -> bool:
        return x == x and x not in (float("inf"), float("-inf"))

o, peor, solo ``x == x`` (que únicamente descarta ``NaN``). ``inf`` atravesaba el
filtro y llegaba a precios, cantidades, marcas y ratios: una división por cero daba
``inf``, el ``inf`` pasaba ``> 0`` y el motor operaba con él.

Este módulo es la única respuesta canónica. Regla:

* ``bool`` no es número (``True`` se colaría como 1.0).
* ``str`` vacío, ``"-"``, unitarios raros y cualquier cosa no convertible ⇒ ``None``.
* ``NaN``, ``+inf`` y ``-inf`` ⇒ ``None``.
* Cantidades y precios además exigen ``> 0``.

Devolver ``None`` es la señal de "no medido"; el llamador decide si eso veta, degrada o
usa un default explícito. Nunca se devuelve un valor inventado.
"""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Final

#: Banda superior de cordura para precios/cantidades. No es un límite de negocio: es el
#: punto por encima del cual un valor solo puede ser un error de origen (overflow,
#: ``inf`` encubierto, basura de parser).
_SANE_MAX: Final[float] = 1e18


def finite_float(value: object) -> float | None:
    """``float`` finito o ``None``. Rechaza ``bool``, texto no numérico y ``NaN``/``inf``."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        if not value.is_finite():
            return None
        number = float(value)
    elif isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return None
    else:
        return None
    if not math.isfinite(number) or abs(number) > _SANE_MAX:
        return None
    return number


def finite_positive(value: object) -> float | None:
    """``float`` finito y estrictamente positivo, o ``None``."""
    number = finite_float(value)
    if number is None or number <= 0:
        return None
    return number


def positive_price(value: object) -> float | None:
    """Precio utilizable: finito y ``> 0``."""
    return finite_positive(value)


def positive_quantity(value: object) -> Decimal | None:
    """Cantidad utilizable como ``Decimal``: finita y ``> 0``.

    La cantidad viaja en ``Decimal`` para no perder precisión en el notional; el filtro
    se hace antes de construirla para que ``Decimal("NaN")``/``Decimal("Infinity")`` no
    lleguen al libro.
    """
    number = finite_positive(value)
    if number is None:
        return None
    try:
        quantity = Decimal(str(number))
    except (InvalidOperation, ValueError):
        return None
    if not quantity.is_finite() or quantity <= 0:
        return None
    return quantity


def finite_range(low: object, high: object) -> tuple[float, float] | None:
    """Rango ``low <= high`` con ambos extremos finitos, o ``None``.

    Se usa para barras ``high/low``: un rango invertido o no finito es un dato corrupto,
    no una señal.
    """
    lo = finite_float(low)
    hi = finite_float(high)
    if lo is None or hi is None or lo > hi:
        return None
    return (lo, hi)


__all__ = [
    "finite_float",
    "finite_positive",
    "finite_range",
    "positive_price",
    "positive_quantity",
]
