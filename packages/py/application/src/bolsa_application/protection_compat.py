"""AUTO-2 / V2.42 — dueño único de la política de protección y su modo de distancia.

Antes de AUTO-2 había **dos motores** de protección que no hablaban entre sí: la
``ProtectionConfig`` del worker (umbrales porcentuales, sólo con ``AUTO_ENGINE_SIM_V2``
OFF) y el ``PositionManager``/``ExitPlan`` + ``PositionState.current_stop`` (geometría por
operación, sólo con V2 ON). El mismo hecho ("el precio retrocedió desde el máximo")
existía como ``trailing_stop`` en un motor y como ``TRAIL`` en el otro, sin traducción.

Este módulo es la casa única de la política legacy y de su **traducción al vocabulario
del FSM** (``bolsa_analytics.cognitive.position_lifecycle``). Los dos modos de distancia
declarados:

* ``pct`` — ``PROTECTION_DISTANCE_MODE_LEGACY``: los umbrales porcentuales de la política
  legacy (``stop_pct``/``t1_pct``/``trailing_pct``). Es lo que se usa con
  ``AUTO_ENGINE_SIM_V2`` OFF, y debe reproducir el comportamiento ``v2.39.x`` exacto
  (freeze §9: el flag sin definir conserva el comportamiento anterior).
* ``r`` — ``PROTECTION_DISTANCE_MODE_LIFECYCLE``: distancias en R sobre ``initial_risk``,
  dueño único en ``bolsa_analytics.cognitive.position_lifecycle.compute_trail_stop``
  (el camino V2). Aquí NO se reimplementa.

Puro: sin I/O, sin reloj y sin importar el worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

#: Motivos de protección legacy (dueño único del literal).
ProtectionReason = Literal["protective_stop", "t1_exit", "trailing_stop", "session_close"]

PROTECTIVE_STOP: ProtectionReason = "protective_stop"
T1_EXIT: ProtectionReason = "t1_exit"
TRAILING_STOP: ProtectionReason = "trailing_stop"
SESSION_CLOSE: ProtectionReason = "session_close"

PROTECTION_REASONS: frozenset[str] = frozenset(
    {PROTECTIVE_STOP, T1_EXIT, TRAILING_STOP, SESSION_CLOSE}
)

#: Modos de distancia declarados (uno por camino; nunca los dos a la vez).
PROTECTION_DISTANCE_MODE_LEGACY = "pct"
PROTECTION_DISTANCE_MODE_LIFECYCLE = "r"
ProtectionDistanceMode = Literal["pct", "r"]

#: Traducción de la decisión legacy al vocabulario del FSM. Un ``t1_exit`` parcial es
#: ``T1_HIT``; ``trailing_stop`` implica que el máximo retrocedió ⇒ toca ratchet del stop
#: (``PROTECT_APPLIED``); el resto de salidas son una PETICIÓN de salida (que el FSM
#: decide si puede cerrar).
_LEGACY_EVENT_BY_REASON: dict[str, str] = {
    PROTECTIVE_STOP: "EXIT_REQUESTED",
    T1_EXIT: "T1_HIT",
    TRAILING_STOP: "PROTECT_APPLIED",
    SESSION_CLOSE: "EXIT_REQUESTED",
}


@dataclass(frozen=True, slots=True)
class ProtectionPolicy:
    """Política de protección legacy: umbrales + fracción de T1. Value object puro.

    ``enabled`` es fail-closed: sin activar, ninguna salida automática. ``exit_reason`` y
    ``exit_fraction`` delegan en las funciones del módulo (implementación única).
    """

    stop_pct: float = 0.02  # SL: cae >=2% desde la entrada => salir.
    t1_pct: float = 0.02  # T1: sube >=2% desde la entrada => tomar beneficio.
    trailing_pct: float = 0.015  # Trailing: retrocede >=1.5% desde el maximo => salir.
    session_end_minute: int = 0  # >0 => cierre por fin de sesion (minuto simulado).
    t1_fraction: float = 1.0  # Fraccion tomada en T1 (1.0 = cierre total).
    enabled: bool = False

    def exit_reason(
        self, *, held: bool, entry: Decimal, high: Decimal, price: Decimal, minute: int
    ) -> ProtectionReason | None:
        """Razón de salida legacy (o ``None``). Delega en ``protection_exit_reason``."""
        return protection_exit_reason(
            self, held=held, entry=entry, high=high, price=price, minute=minute
        )

    def exit_fraction(self, reason: str | None) -> float:
        """Fracción de la posición a vender. Delega en ``protection_exit_fraction``."""
        return protection_exit_fraction(self, reason)


def protection_exit_reason(
    policy: ProtectionPolicy,
    *,
    held: bool,
    entry: Decimal,
    high: Decimal,
    price: Decimal,
    minute: int,
) -> ProtectionReason | None:
    """Razón de salida de protección (o ``None`` si no procede). Sólo con posición.

    V2.24 / A9.1 (P2-06): el ORDEN importa. Si el máximo ya superó el umbral T1
    (``high > entry*(1+t1_pct)``) el precio actual puede seguir por encima de T1 y haber
    retrocedido desde el máximo: eso es un ``trailing_stop`` real, no un ``t1_exit``.
    Antes se comprobaba T1 primero y se etiquetaba mal el motivo (misma acción, distinta
    historia en el journal). Ahora se evalúa el trailing antes que T1 cuando el máximo
    rebasó T1.
    """
    if not policy.enabled or not held:
        return None
    if entry <= 0 or price <= 0:
        return None
    if policy.session_end_minute and minute >= policy.session_end_minute:
        return SESSION_CLOSE
    if policy.stop_pct > 0 and price <= entry * (Decimal(1) - Decimal(str(policy.stop_pct))):
        return PROTECTIVE_STOP
    high_above_t1 = policy.t1_pct > 0 and high > entry * (
        Decimal(1) + Decimal(str(policy.t1_pct))
    )
    trailing_hit = (
        policy.trailing_pct > 0
        and high > entry
        and price <= high * (Decimal(1) - Decimal(str(policy.trailing_pct)))
    )
    # Trailing tiene prioridad sobre T1 cuando el máximo ya rebasó T1 (un retroceso desde
    # un máximo alto es un trailing real, no una toma en T1).
    if trailing_hit and high_above_t1:
        return TRAILING_STOP
    if policy.t1_pct > 0 and price >= entry * (Decimal(1) + Decimal(str(policy.t1_pct))):
        return T1_EXIT
    if trailing_hit:
        return TRAILING_STOP
    return None


def protection_exit_fraction(policy: ProtectionPolicy, reason: str | None) -> float:
    """Fracción de la posición a vender para una razón T1 (parcial) / resto 1.0."""
    if reason == T1_EXIT and 0 < policy.t1_fraction < 1:
        return policy.t1_fraction
    return 1.0


def lifecycle_event_for_protection_reason(reason: str | None) -> str | None:
    """Traduce el motivo legacy al evento del FSM (vocabulario único, sin re-decidir)."""
    if reason is None:
        return None
    return _LEGACY_EVENT_BY_REASON.get(reason)


def protection_reason_is_partial(reason: str | None) -> bool:
    """``True`` sólo si el motivo legacy reparte la salida (T1 parcial)."""
    return reason == T1_EXIT
