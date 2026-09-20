"""HardKillSwitch — parada DURA latcheada por encima del gobernador (AUTO-3 slice 2).

El ``OperationalGovernor`` ya sabe leer un ``halted`` booleano y forzar ``HALTED``
(``resolve_operational_state``), pero nadie se lo pasaba: era un parámetro muerto. Este
módulo es el PRODUCTOR de ese hecho y el dueño de su semántica.

Propiedades que el diseño garantiza:

* **Tipificado**: no se puede activar con un motivo arbitrario. Un halt sin motivo
  canónico no es auditable, así que se rechaza en vez de guardarse como string suelto.
* **Latcheado**: una vez activado NO se auto-libera. Que el tick siguiente "parezca"
  normal no desactiva la parada; liberarla exige una acción explícita de reconciliación.
  Es la diferencia entre "no vi el problema" y "el problema ya no está".
* **Independiente**: no depende del juicio del gobernador ni de sus umbrales. El halt se
  aplica ANTES de la tabla y no puede ser "compensado" por un eje benigno.
* **Reintentos contados**: reavisar el mismo problema no reinicia el latch; se cuenta
  (``reengagements``) para distinguir "un fallo" de "un fallo recurrente".

Módulo puro y determinista (sin I/O, sin reloj): el ``at`` es opaco y lo aporta el
llamante.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

#: Motivos canónicos del kill switch (contrato con el journal).
KillSwitchReason = Literal[
    "DATA_CORRUPTION",
    "BROKER_DESYNC",
    "RECONCILIATION_FAILURE",
    "DUPLICATE_EXECUTION",
    "RISK_BREACH",
    "STALE_DATA",
    "MANUAL_KILL",
    "SYSTEM_ERROR",
]

ENCODED_KILL_SWITCH_REASONS: tuple[KillSwitchReason, ...] = (
    "DATA_CORRUPTION",
    "BROKER_DESYNC",
    "RECONCILIATION_FAILURE",
    "DUPLICATE_EXECUTION",
    "RISK_BREACH",
    "STALE_DATA",
    "MANUAL_KILL",
    "SYSTEM_ERROR",
)

_VALID_REASONS: frozenset[str] = frozenset(ENCODED_KILL_SWITCH_REASONS)


def coerce_kill_switch_reason(value: Any) -> KillSwitchReason | None:
    """Normaliza el motivo a un literal canónico; ``None`` si no lo es.

    ``None`` ⇒ el llamante NO puede activar la parada (no se inventa un motivo): un halt
    sin causa tipificada es indistinguible de un bug.
    """
    text = value.strip().upper() if isinstance(value, str) else ""
    if text in _VALID_REASONS:
        return cast(KillSwitchReason, text)
    return None


@dataclass(slots=True)
class HardKillSwitch:
    """Estado latcheado de la parada dura (en memoria; el llamante lo persiste si quiere).

    ``force_protective_exits`` es la política configurable de la casa: con la parada
    activa las ENTRADAS quedan vetadas SIEMPRE y, por defecto, las salidas PROTECTORAS
    siguen permitidas (el invariante de oro: la reconciliación veta aperturas, nunca una
    salida que reduce riesgo). Ponerlo en ``False`` congelaría también las salidas, cosa
    que solo tiene sentido en un parón manual total.
    """

    engaged: bool = False
    reason: KillSwitchReason | None = None
    engaged_at: str | None = None
    reengagements: int = 0
    force_protective_exits: bool = True

    def engage(self, reason: Any, *, at: str | None = None) -> bool:
        """Activa la parada con un motivo tipificado. Devuelve True si CAMBIÓ el estado.

        Un motivo no canónico levanta ``ValueError``: no se puede parar el sistema "de
        cualquier manera" y dejar el journal sin poder explicar por qué. Reavisar con la
        parada ya activa NO reinicia el latch: cuenta el reintento y conserva el motivo
        original (el primero es el que originó la parada).
        """
        coerced = coerce_kill_switch_reason(reason)
        if coerced is None:
            raise ValueError(
                f"kill switch reason must be one of {ENCODED_KILL_SWITCH_REASONS}, "
                f"got {reason!r}"
            )
        if self.engaged:
            self.reengagements += 1
            return False
        self.engaged = True
        self.reason = coerced
        self.engaged_at = at
        return True

    def release(self, *, reconciliation_ok: bool, at: str | None = None) -> bool:
        """Libera la parada SOLO con reconciliación explícita y correcta.

        No existe auto-liberación: sin ``reconciliation_ok=True`` la parada sigue latcheada
        aunque el tick parezca normal. Devuelve True si se liberó.
        """
        if not self.engaged or not reconciliation_ok:
            return False
        self.engaged = False
        self.reason = None
        self.engaged_at = None
        return True

    @property
    def blocks_new_entry(self) -> bool:
        """Con la parada activa NO se abre riesgo nuevo, sin excepción."""
        return self.engaged

    def to_dict(self) -> dict[str, Any]:
        return {
            "engaged": self.engaged,
            "reason": self.reason,
            "engagedAt": self.engaged_at,
            "reengagements": self.reengagements,
            "forceProtectiveExits": self.force_protective_exits,
            "blocksNewEntry": self.blocks_new_entry,
        }


__all__ = [
    "ENCODED_KILL_SWITCH_REASONS",
    "HardKillSwitch",
    "KillSwitchReason",
    "coerce_kill_switch_reason",
]
