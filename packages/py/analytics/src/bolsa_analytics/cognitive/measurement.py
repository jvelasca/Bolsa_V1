"""Estado de MEDICIÓN de una magnitud agregada (AUTO 2.0 · V2.40.4 · P1).

Un agregado que solo suma lo que **sabe** medir no es "el total": es un **suelo**. El
caso que motivó este módulo (auditoría de v2.40.2-beta):

    Position A → risk_amount = 100
    Position B → risk_amount = UNKNOWN
    ⇒ ``risk_used`` se publicaba como 100

cuando la verdad es ``risk_used >= 100`` y el total es **desconocido**. Lo mismo con la
exposición (``aggregate_exposure`` salta las posiciones sin valor de mercado) y con el
libro de órdenes (una orden en vuelo cuyo capital/riesgo no se puede cuantificar).

El tri-estado es *fail-closed*: solo ``COMPLETE`` autoriza a decidir contra el número.
El ``PortfolioDecisionEngine`` veta la entrada cuando no lo es, de modo que "sé 100" no
puede volver a leerse como "el total es 100".

Módulo puro y determinista (sin I/O, sin reloj), compartido por
``auto_portfolio_snapshot`` y ``open_order`` para no crear una dependencia circular.
"""

from __future__ import annotations

from typing import Any, Literal, cast

MeasurementStatus = Literal["COMPLETE", "PARTIAL", "UNKNOWN"]

MEASUREMENT_COMPLETE: MeasurementStatus = "COMPLETE"
MEASUREMENT_PARTIAL: MeasurementStatus = "PARTIAL"
MEASUREMENT_UNKNOWN: MeasurementStatus = "UNKNOWN"

_MEASUREMENT_VALUES: frozenset[str] = frozenset(
    {MEASUREMENT_COMPLETE, MEASUREMENT_PARTIAL, MEASUREMENT_UNKNOWN}
)


def coerce_measurement(value: Any) -> MeasurementStatus | None:
    """Normaliza un estado de medición; ``None`` si no es uno de los tres canónicos."""
    if isinstance(value, str) and value.strip().upper() in _MEASUREMENT_VALUES:
        return cast(MeasurementStatus, value.strip().upper())
    return None


def measurement_from_counts(*, valued: int, unvalued: int) -> MeasurementStatus:
    """Estado de medición a partir de cuántas partidas se pudieron valorar.

    Cero partidas ⇒ ``COMPLETE`` (no hay nada que medir: un agregado vacío es exacto).
    Alguna sin valorar y ninguna valorada ⇒ ``UNKNOWN``.
    """
    if unvalued <= 0:
        return MEASUREMENT_COMPLETE
    if valued > 0:
        return MEASUREMENT_PARTIAL
    return MEASUREMENT_UNKNOWN


def is_complete(status: Any) -> bool:
    """Predicado canónico: solo ``COMPLETE`` habilita decidir contra el agregado."""
    return coerce_measurement(status) == MEASUREMENT_COMPLETE


# Severidad creciente: un agregado es tan fiable como su parte MENOS fiable.
_MEASUREMENT_SEVERITY: dict[MeasurementStatus, int] = {
    MEASUREMENT_COMPLETE: 0,
    MEASUREMENT_PARTIAL: 1,
    MEASUREMENT_UNKNOWN: 2,
}


def combine_measurements(*statuses: Any) -> MeasurementStatus:
    """Peor estado de los aportados (``COMPLETE`` < ``PARTIAL`` < ``UNKNOWN``).

    Se usa para componer un agregado de varias fuentes (p.ej. el libro de órdenes: lo
    que se pudo LEER y lo que se pudo CUANTIFICAR de lo leído). Un estado no canónico
    se trata como ``UNKNOWN``: no se puede confiar en lo que no se entiende.
    """
    worst = MEASUREMENT_COMPLETE
    for status in statuses:
        coerced = coerce_measurement(status)
        if coerced is None:
            return MEASUREMENT_UNKNOWN
        if _MEASUREMENT_SEVERITY[coerced] > _MEASUREMENT_SEVERITY[worst]:
            worst = coerced
    return worst


__all__ = [
    "MEASUREMENT_COMPLETE",
    "MEASUREMENT_PARTIAL",
    "MEASUREMENT_UNKNOWN",
    "MeasurementStatus",
    "coerce_measurement",
    "combine_measurements",
    "is_complete",
    "measurement_from_counts",
]
