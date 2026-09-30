"""Política de granularidad operativa AUTO: entorno -> value object (fail-closed).

Único punto del motor que decide la **cadencia de decisión**. Con esto,
``signal_timeframe`` deja de ser un literal suelto y pasa a **derivarse** del
``DecisionClock`` de la granularidad resuelta, validada por su gate.

Precedencia de resolución (de mayor a menor):

#. ``AUTO_ENGINE_OPERATIVE_GRANULARITY`` (knob nuevo y explícito);
#. ``fallback_timeframe`` (la configuración histórica del worker,
   ``V2Tunables.signal_timeframe`` / ``AUTO_ENGINE_SIM_V2_TIMEFRAME``);
#. ``"1d"`` (default del sistema).

**Fail-closed:** una granularidad conocida pero **no habilitada** (``1wk``) o
**desconocida** se rechaza con ``UnsupportedGranularityError``; nunca se degrada en
silencio a ``1d``.

Diseño v2: ``docs/engineering/rethink-granularidad-operativa-auto-v2-2026-09-30.md``.
"""

from __future__ import annotations

import os

from bolsa_domain.errors import UnsupportedGranularityError
from bolsa_domain.operative_granularity import (
    DAILY_GRANULARITY,
    WEEKLY_GRANULARITY,
    GranularityRejection,
    OperativeGranularity,
)

#: Knob explícito de la granularidad operativa (valor: ``1d`` | ``1wk``).
OPERATIVE_GRANULARITY_ENV = "AUTO_ENGINE_OPERATIVE_GRANULARITY"

#: Granularidades **declaradas**. ``1wk`` está declarada pero no habilitada: su gate
#: la rechaza con motivo tipado (el gap del lunes no tiene pruebas temporales).
_KNOWN_GRANULARITIES: dict[str, OperativeGranularity] = {
    "1d": DAILY_GRANULARITY,
    "1wk": WEEKLY_GRANULARITY,
}


def resolve_operative_granularity(
    fallback_timeframe: str | None = None,
) -> OperativeGranularity:
    """Resuelve y **exige habilitada** la granularidad operativa.

    ``fallback_timeframe`` es la configuración previa del worker (p. ej.
    ``V2Tunables.signal_timeframe``); se usa solo cuando el knob explícito está vacío,
    de modo que la semántica existente se conserva y el knob nuevo manda.
    """
    raw = (os.getenv(OPERATIVE_GRANULARITY_ENV) or "").strip()
    value = raw or (fallback_timeframe or "").strip() or "1d"

    granularity = _KNOWN_GRANULARITIES.get(value)
    if granularity is None:
        raise UnsupportedGranularityError(
            GranularityRejection.UNKNOWN_GRANULARITY,
            f"granularidad desconocida {value!r}; declaradas: "
            f"{', '.join(sorted(_KNOWN_GRANULARITIES))}",
        )
    return granularity.require_supported()


def operative_signal_timeframe(granularity: OperativeGranularity) -> str:
    """``signal_timeframe`` derivado del ``DecisionClock`` de la granularidad."""
    return granularity.decision.timeframe


__all__ = [
    "OPERATIVE_GRANULARITY_ENV",
    "operative_signal_timeframe",
    "resolve_operative_granularity",
]
