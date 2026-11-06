"""Qué campos de la barra EXIGE cada indicador (S8 de la auditoría .183).

Contexto del hallazgo: cuando la ventana llega *close-only*, ``signal_feature_context``
fabrica ``open = high = low = close`` y ``volume = 0`` para poder alimentar al motor
declarativo. Para SMA/EMA/RSI esa síntesis es inofensiva (sólo usan el cierre), pero para
ATR, CCI, Stochastic, Donchian, ADX, SuperTrend, Ichimoku, VWAP, OBV o MFI **no hay dato
que calcular**: el rango es cero y el volumen también, así que el indicador devuelve un
número con la forma correcta y el significado equivocado (un ATR de 0, un VWAP que
desaparece porque ``cum_vol = 0``). Una señal emitida sobre ese número es una señal
inventada.

Este módulo es el dueño único de la tabla indicador → campos requeridos, para que el
decisor (que puede vetar) y el productor de features (que sintetiza) no puedan divergir.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

__all__ = [
    "OHLCV_DEPENDENT_DEFINITIONS",
    "RANGE_DEPENDENT_DEFINITIONS",
    "RANGE_FIELD",
    "VOLUME_DEPENDENT_DEFINITIONS",
    "VOLUME_FIELD",
    "required_bar_fields",
]

#: La serie necesita el RANGO de la barra (``high``/``low``, y con ellos el cierre previo
#: para el true range). Sin rango real el indicador no mide volatilidad: mide cero.
RANGE_DEPENDENT_DEFINITIONS: frozenset[str] = frozenset(
    {
        "adx",
        "aroon",
        "atr",
        "bears",
        "bulls",
        "cci",
        "dc",
        "ich",
        "sar",
        "st",
        "stoch",
        "willr",
    }
)

#: La serie necesita el VOLUMEN de la barra. Sin él, VWAP no existe (``cum_vol = 0``) y
#: OBV/MFI miden un flujo de cero.
VOLUME_DEPENDENT_DEFINITIONS: frozenset[str] = frozenset({"mfi", "obv", "vwap"})

#: Unión: cualquier serie de este conjunto queda fabricada con barras close-only.
OHLCV_DEPENDENT_DEFINITIONS: frozenset[str] = (
    RANGE_DEPENDENT_DEFINITIONS | VOLUME_DEPENDENT_DEFINITIONS
)

#: Nombres de los requisitos (los usa quien lee las barras para declarar QUÉ falta).
RANGE_FIELD = "high_low"
VOLUME_FIELD = "volume"

_REQUIREMENTS_BY_DEFINITION: dict[str, frozenset[str]] = {
    **{definition: frozenset({RANGE_FIELD}) for definition in RANGE_DEPENDENT_DEFINITIONS},
    **{definition: frozenset({VOLUME_FIELD}) for definition in VOLUME_DEPENDENT_DEFINITIONS},
}


def required_bar_fields(indicator_specs: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    """Campos de barra que exigen los ``indicatorSpecs`` de una definición.

    Sin specs no se exige nada: el camino de presets intrínsecos no consume
    ``indicator_context`` y no depende del rango ni del volumen. Un ``definitionId``
    desconocido tampoco exige nada (no hay serie que fabricar); el motor ya lo trata como
    "sin feature".
    """
    required: set[str] = set()
    for spec in indicator_specs:
        if not isinstance(spec, Mapping):
            continue
        definition_id = str(spec.get("definitionId") or "")
        required |= _REQUIREMENTS_BY_DEFINITION.get(definition_id, frozenset())
    return frozenset(required)
