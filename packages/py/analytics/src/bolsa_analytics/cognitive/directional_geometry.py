"""Geometría direccional compartida — la **única casa** de la regla long/short.

La dirección entra **siempre** como parámetro explícito. Un valor que no sea ``"long"`` o
``"short"`` **no** se interpreta como largo por defecto (fail-closed): una posición corta
leída con geometría larga declararía su riesgo como ``0`` o como "no medible" y, peor, la
mediría con el modelo de la dirección equivocada.

Precedente que este módulo cierra: la economía de ``expected_value`` ya resolvió este mismo
defecto (``_risk_geometry``/``_target_r`` direccionales) y el scorer OOS
(``replay_oos._realized_r``) lo volvió a redescubrir —siempre en largo—. En vez de que cada
módulo nuevo reimplemente la regla, aquí vive **una sola vez** y los tres llamantes
(``expected_value``, ``portfolio_reservation.stop_distance``, ``position_state.signed_r_from_price``
y el scorer OOS) **delegan**.

Las primitivas se exponen **en crudo** (sin redondeo): cada llamante conserva su propio
``_round4`` de la casa, de modo que centralizar la *regla* no mueve ni un decimal de lo ya
sellado. Módulo **puro**: sin I/O, sin reloj, sin red.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = ["coerce_direction", "risk_distance", "signed_r", "target_r"]

_LONG = "long"
_SHORT = "short"
_DIRECTIONS = (_LONG, _SHORT)


def coerce_direction(value: Any) -> str | None:
    """``"long"``/``"short"`` normalizado, o ``None`` si no es una dirección conocida.

    Fail-closed: ``None`` **nunca** significa "larga". El llamante debe degradar la medición
    (declarar el hueco) en vez de asumir una geometría.
    """
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in _DIRECTIONS else None


def _finite(value: Any) -> float | None:
    """Número finito o ``None``. Un ``bool`` NO es un número aquí (evita ``True == 1``)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_positive(value: Any) -> float | None:
    number = _finite(value)
    if number is None or number <= 0:
        return None
    return number


def risk_distance(*, entry: Any, stop: Any, direction: Any = _LONG) -> float | None:
    """Distancia de riesgo **en crudo** entre entrada y stop, según la dirección.

    Long exige ``stop < entry`` (riesgo ``entry − stop``); short exige ``stop > entry``
    (riesgo ``stop − entry``). Un stop del **lado equivocado** (o igual al precio de entrada)
    no es "riesgo cero": es una geometría que no se puede medir. ``None`` también si la
    dirección no es reconocible o los precios no son finitos y positivos.
    """
    resolved = coerce_direction(direction)
    if resolved is None:
        return None
    e = _finite_positive(entry)
    s = _finite_positive(stop)
    if e is None or s is None:
        return None
    if resolved == _SHORT:
        return (s - e) if s > e else None
    return (e - s) if s < e else None


def signed_r(*, direction: Any, entry: Any, risk: Any, price: Any) -> float | None:
    """R firmado **en crudo**: ``(price − entry) / risk`` en largo; espejo en corto.

    ``risk`` es una distancia de riesgo **ya positiva** (``risk_distance``). ``None`` si la
    dirección es desconocida o si ``entry``/``risk``/``price`` no son medibles (``risk`` y
    ``price`` estrictamente positivos; ``entry`` solo tiene que ser finito).
    """
    resolved = coerce_direction(direction)
    if resolved is None:
        return None
    e = _finite(entry)
    r = _finite(risk)
    p = _finite(price)
    if e is None or r is None or r <= 0.0:
        return None
    if p is None or p <= 0.0:
        return None
    return (p - e) / r if resolved == _LONG else (e - p) / r


def target_r(*, entry: Any, stop: Any, target: Any, direction: Any = _LONG) -> float | None:
    """R **en crudo** que representa alcanzar ``target``, según la dirección.

    Short: premio ``entry − target`` sobre la distancia de riesgo ``stop − entry``. Long:
    premio ``target − entry`` sobre ``entry − stop``. ``None`` si la geometría no es medible
    o si el premio sale negativo (un target del lado equivocado).
    """
    resolved = coerce_direction(direction)
    if resolved is None:
        return None
    e = _finite(entry)
    s = _finite(stop)
    t = _finite(target)
    if e is None or s is None or t is None:
        return None
    if resolved == _SHORT:
        distance = s - e
        reward = e - t
    else:
        distance = e - s
        reward = t - e
    if distance <= 0.0 or reward < 0.0:
        return None
    return reward / distance
