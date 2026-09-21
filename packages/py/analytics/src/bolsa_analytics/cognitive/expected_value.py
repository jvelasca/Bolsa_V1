"""Valor esperado ECONÓMICO de una oportunidad (AUTO-4 · V2.44 · `1.69.0-beta`).

Hasta `V2.43.3` la decisión comparaba **heurísticas**: `OpportunityScore` es una suma
ponderada de componentes normalizados a `[0, 1]` (`opportunity_ranker.py`), y el
`edge` que entra en ella es una confianza declarada, no dinero. Este módulo aporta la
magnitud que faltaba para comparar operaciones por **economía**: cuánto se espera ganar,
en R y en moneda, con qué probabilidad y a qué coste.

    Expected R     = p·avg_win_r + (1 − p)·avg_loss_r        (con avg_loss_r <= 0)
    Expected €     = Expected R × risk_amount                (1R en dinero)
    Expected € neto = Expected € − coste de ida y vuelta

**La dirección es un parámetro, nunca una suposición.** La geometría de riesgo de una
oportunidad **corta** es la espejo de la larga: el stop válido está *por encima* de la
entrada (``stop > entry``) y el 1R en dinero es ``(stop − entry) × qty``. Un módulo que
asumiera geometría larga (``stop < entry``) declararía toda oportunidad corta como
"geometría no medible" y, peor, calcularía su coste con el modelo de la dirección
equivocada. Aquí ``direction`` entra explícito (``"long"`` / ``"short"``) y un valor que no
es una dirección conocida **degrada** la medición (``EV_DIRECTION_UNSUPPORTED``): fail-closed,
nunca "asumimos larga".

**Disciplina de medición (la del repo, no una nueva).** Un dato ininterpretable **no**
se convierte en `0` ni en un default plausible: `p_win` fuera de `[0, 1]`, una media
de la que no se sabe el signo, o una geometría invertida **degradan** la medición
(`UNKNOWN`) y lo declaran en `notes`. Un `Expected R` de `0.0` "calculado" a partir de
una probabilidad inventada es exactamente el `0.0` que este repositorio ya declaró
como "la forma que toma un dato ininterpretable" (traspaso de `v2.43.2` §4).

Módulo **puro**: sin I/O, sin reloj, sin red. El coste se delega en `TradingCostModel`
(la casa única del coste de ida y vuelta), no se recalcula aquí.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)
from bolsa_analytics.cognitive.portfolio_reservation import (
    TradingCostModel,
    estimate_trading_cost,
)

#: Motivos de degradación (vocabulario del journal; nunca se lanza por un dato sucio).
EV_GEOMETRY_UNMEASURED = "geometry_unmeasured"
EV_P_WIN_OUT_OF_RANGE = "p_win_out_of_range"
EV_WIN_MEAN_MISSING = "avg_win_r_missing"
EV_LOSS_MEAN_MISSING = "avg_loss_r_missing"
EV_WIN_MEAN_NEGATIVE = "avg_win_r_negative"
EV_LOSS_MEAN_POSITIVE = "avg_loss_r_positive"
EV_COST_UNMEASURED = "cost_unmeasured"
EV_WIN_DERIVED_FROM_TARGET = "avg_win_r_derived_from_target"
EV_DIRECTION_UNSUPPORTED = "direction_unsupported"

#: Las dos direcciones que este módulo sabe leer. Cualquier otra cosa NO se interpreta
#: como larga por defecto: degrada y lo declara (``EV_DIRECTION_UNSUPPORTED``).
_LONG = "long"
_SHORT = "short"


def _coerce_direction(value: Any) -> str | None:
    """``"long"``/``"short"`` (normalizado) o ``None`` si no es una dirección conocida."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in (_LONG, _SHORT):
        return normalized
    return None


def _finite(value: Any) -> float | None:
    """Número finito o ``None``. Un `bool` NO es un número aquí (evita `True == 1`)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


@dataclass(frozen=True, slots=True)
class ExpectedValue:
    """Valor esperado económico de UNA oportunidad, con su estado de medición.

    ``expected_r`` es la magnitud **adimensional** (comparable entre instrumentos y
    precios); ``net_expected_currency`` es la magnitud **económica** (la que ordena la
    cartera). ``measurement`` declara hasta dónde se pudo medir:

    * ``COMPLETE`` — hay `expected_r`, `expected_currency` y coste ⇒ el neto es cerrado.
    * ``PARTIAL`` — hay `expected_r` (adimensional) pero el neto no es cerrado (falta
      coste o falta el `1R` en dinero).
    * ``UNKNOWN`` — no se pudo derivar ni `expected_r`: el dato que falta es la
      probabilidad o una de las medias, no el coste.
    """

    p_win: float | None = None
    avg_win_r: float | None = None
    avg_loss_r: float | None = None
    expected_r: float | None = None
    risk_amount: float | None = None
    expected_currency: float | None = None
    cost_currency: float | None = None
    net_expected_currency: float | None = None
    measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
    notes: tuple[str, ...] = ()

    @property
    def is_measurable(self) -> bool:
        """¿Se puede comparar económicamente contra otras oportunidades?"""
        return self.net_expected_currency is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pWin": self.p_win,
            "avgWinR": self.avg_win_r,
            "avgLossR": self.avg_loss_r,
            "expectedR": self.expected_r,
            "riskAmount": self.risk_amount,
            "expectedCurrency": self.expected_currency,
            "costCurrency": self.cost_currency,
            "netExpectedCurrency": self.net_expected_currency,
            "measurement": self.measurement,
            "notes": list(self.notes),
        }


def build_expected_value(
    *,
    entry: Any = None,
    stop: Any = None,
    target: Any = None,
    quantity: Any = None,
    p_win: Any = None,
    avg_win_r: Any = None,
    avg_loss_r: Any = None,
    direction: Any = "long",
    cost_model: TradingCostModel | None = None,
) -> ExpectedValue:
    """Valor esperado económico a partir de la geometría, las medias, la dirección y el coste.

    ``direction`` es ``"long"`` o ``"short"`` y entra en las tres piezas direccionales: el
    ``1R`` en dinero, el ``R`` derivado del target y el modelo de coste. Una dirección que
    no es ninguna de las dos **degrada** la medición (``EV_DIRECTION_UNSUPPORTED``): no se
    asume larga por defecto.

    ``avg_win_r`` puede **derivarse** del target si la estrategia no declara media
    histórica: es una media *declarada como derivada* (va en ``notes``), no una
    invención. Todo lo demás se degrada, nunca se rellena.
    """
    notes: list[str] = []

    p = _finite(p_win)
    if p is None or not (0.0 <= p <= 1.0):
        notes.append(EV_P_WIN_OUT_OF_RANGE)
        return ExpectedValue(
            p_win=None,
            avg_win_r=_finite(avg_win_r),
            avg_loss_r=_finite(avg_loss_r),
            measurement=MEASUREMENT_UNKNOWN,
            notes=tuple(notes),
        )

    resolved_direction = _coerce_direction(direction)
    if resolved_direction is None:
        notes.append(EV_DIRECTION_UNSUPPORTED)
        return ExpectedValue(
            p_win=p,
            avg_win_r=_finite(avg_win_r),
            avg_loss_r=_finite(avg_loss_r),
            measurement=MEASUREMENT_UNKNOWN,
            notes=tuple(notes),
        )

    win_mean = _finite(avg_win_r)
    loss_mean = _finite(avg_loss_r)
    risk_geometry = _risk_geometry(
        entry=entry, stop=stop, quantity=quantity, direction=resolved_direction
    )

    if win_mean is None:
        derived = _target_r(
            entry=entry, stop=stop, target=target, direction=resolved_direction
        )
        if derived is not None and p > 0.0:
            win_mean = derived
            notes.append(EV_WIN_DERIVED_FROM_TARGET)

    if p > 0.0 and win_mean is None:
        notes.append(EV_WIN_MEAN_MISSING)
        return ExpectedValue(
            p_win=p,
            avg_win_r=None,
            avg_loss_r=loss_mean,
            measurement=MEASUREMENT_UNKNOWN,
            notes=tuple(notes),
        )
    if p < 1.0 and loss_mean is None:
        notes.append(EV_LOSS_MEAN_MISSING)
        return ExpectedValue(
            p_win=p,
            avg_win_r=win_mean,
            avg_loss_r=None,
            measurement=MEASUREMENT_UNKNOWN,
            notes=tuple(notes),
        )
    if win_mean is not None and win_mean < 0.0:
        notes.append(EV_WIN_MEAN_NEGATIVE)
        return ExpectedValue(
            p_win=p,
            avg_win_r=win_mean,
            avg_loss_r=loss_mean,
            measurement=MEASUREMENT_UNKNOWN,
            notes=tuple(notes),
        )
    if loss_mean is not None and loss_mean > 0.0:
        notes.append(EV_LOSS_MEAN_POSITIVE)
        return ExpectedValue(
            p_win=p,
            avg_win_r=win_mean,
            avg_loss_r=loss_mean,
            measurement=MEASUREMENT_UNKNOWN,
            notes=tuple(notes),
        )

    win_term = p * (win_mean or 0.0)
    loss_term = (1.0 - p) * (loss_mean or 0.0)
    expected_r = _round4(win_term + loss_term)

    risk_amount, risk_note = risk_geometry
    if risk_note is not None:
        notes.append(risk_note)
    expected_currency = _round4(expected_r * risk_amount) if risk_amount is not None else None

    cost_currency: float | None = None
    if expected_currency is not None:
        cost = estimate_trading_cost(
            entry=entry,
            stop=stop,
            quantity=quantity,
            direction=resolved_direction,
            model=cost_model,
        )
        if cost.total is None:
            notes.append(EV_COST_UNMEASURED)
        else:
            cost_currency = cost.total

    net: float | None = None
    if expected_currency is not None and cost_currency is not None:
        net = _round4(expected_currency - cost_currency)

    if net is not None:
        measurement: MeasurementStatus = MEASUREMENT_COMPLETE
    else:
        # El `Expected R` puede estar medido aunque el neto no sea cerrado: degradar a
        # `PARTIAL` (no a `UNKNOWN`) es lo honesto — hay una magnitud medida, no cero.
        measurement = MEASUREMENT_PARTIAL

    return ExpectedValue(
        p_win=p,
        avg_win_r=win_mean,
        avg_loss_r=loss_mean,
        expected_r=expected_r,
        risk_amount=risk_amount,
        expected_currency=expected_currency,
        cost_currency=cost_currency,
        net_expected_currency=net,
        measurement=measurement,
        notes=tuple(notes),
    )


def _risk_geometry(
    *, entry: Any, stop: Any, quantity: Any, direction: str = _LONG
) -> tuple[float | None, str | None]:
    """`1R` en dinero (`distancia × qty`) o `None` con su motivo, según la dirección.

    Long exige ``stop < entry`` (riesgo = ``(entry − stop) × qty``); short exige
    ``stop > entry`` (riesgo = ``(stop − entry) × qty``). Un stop del **lado
    equivocado** (o igual al precio de entrada) no es "riesgo cero": es una geometría que
    no se puede medir. Es la misma lección de `H3` en `v2.43.2` (un `max(0.0, …)`
    convertía un stop mal puesto en un riesgo medido de `0.0`), ahora también con la
    dirección como parte del contrato y no como suposición.
    """
    resolved = _coerce_direction(direction)
    if resolved is None:
        return None, EV_DIRECTION_UNSUPPORTED
    e = _finite(entry)
    s = _finite(stop)
    q = _finite(quantity)
    if e is None or e <= 0.0 or s is None or s <= 0.0 or q is None or q <= 0.0:
        return None, EV_GEOMETRY_UNMEASURED
    if resolved == _SHORT:
        if s <= e:
            return None, EV_GEOMETRY_UNMEASURED
        return _round4((s - e) * q), None
    if s >= e:
        return None, EV_GEOMETRY_UNMEASURED
    return _round4((e - s) * q), None


def _target_r(
    *, entry: Any, stop: Any, target: Any, direction: str = _LONG
) -> float | None:
    """R que representa alcanzar el target (``None`` si la geometría no es medible).

    También direccional: en una corta el premio es que el precio **baje** hasta el target
    (``entry − target``) sobre una distancia de riesgo ``stop − entry``.
    """
    resolved = _coerce_direction(direction)
    if resolved is None:
        return None
    e = _finite(entry)
    s = _finite(stop)
    t = _finite(target)
    if e is None or s is None or t is None:
        return None
    if resolved == _SHORT:
        distance = s - e
        if distance <= 0.0:
            return None
        reward = e - t
    else:
        distance = e - s
        if distance <= 0.0:
            return None
        reward = t - e
    if reward < 0.0:
        return None
    return _round4(reward / distance)


__all__ = [
    "EV_COST_UNMEASURED",
    "EV_DIRECTION_UNSUPPORTED",
    "EV_GEOMETRY_UNMEASURED",
    "EV_LOSS_MEAN_MISSING",
    "EV_LOSS_MEAN_POSITIVE",
    "EV_P_WIN_OUT_OF_RANGE",
    "EV_WIN_DERIVED_FROM_TARGET",
    "EV_WIN_MEAN_MISSING",
    "EV_WIN_MEAN_NEGATIVE",
    "ExpectedValue",
    "build_expected_value",
]
