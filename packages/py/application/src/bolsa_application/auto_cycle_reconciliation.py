"""AUTO-11 — reconciliación del rastro de ciclo: capital reservado vs traza de régimen.

Qué cierra: la ventana que ``AUTO-10`` aceptó y declaró, y que nadie comprobaba. El orden de la
fase es deliberado —primero el compromiso de capital, después la traza de régimen— y eso deja un
hueco real:

    RESERVATION COMMITTED  →  CRASH  →  NO JOURNAL

Aceptarlo es correcto (no se bloquea la gestión de riesgo por un fallo de observabilidad), pero
**no comprobarlo** convierte el hueco en una propiedad invisible: el ciclo existe, tiene dinero
comprometido y nadie sabrá nunca en qué régimen se abrió. Este módulo es la comprobación: cruza
los ciclos que tienen reserva durable con los que el lector de ``AUTO-10`` **confirma**, y declara
cada desajuste con su motivo, en las dos direcciones.

Los cuatro desajustes NO son el mismo hecho (misma disciplina que los tres huecos del lector):

* ``missing`` — hay capital comprometido y el lector **no** confirmó régimen. Es el hueco del
  crash entre el commit y la traza; ``missing_reasons`` dice si la fila **no estaba** (``absent``)
  o **no se pudo creer** (``unconfirmed``).
* ``unrequested`` — hay capital comprometido y **ni siquiera se preguntó** por ese ciclo: un hueco
  operativo (la lista de ciclos del informe no cubría el ciclo reservado), no un hueco del journal.
* ``not_derivable`` — hay capital y el ``cycle_id`` no tiene forma ``cyc-``: la lectura por índice
  **no lo alcanza**, así que la ausencia de régimen es estructural y no un fallo de escritura.
* ``orphan`` — hay traza confirmada y **ninguna** reserva: el caso inverso (una traza sin capital).
  También se declara: o sobra la traza o falta la reserva, y ninguna de las dos cosas es normal.

Read-only y puro sobre las filas que le pasan: no consulta nada ni escribe nada.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "CYCLE_TRACE_MISSING",
    "CYCLE_TRACE_NOT_DERIVABLE",
    "CYCLE_TRACE_ORPHAN",
    "CYCLE_TRACE_UNREQUESTED",
    "CycleTraceReconciliation",
    "reconcile_cycle_trace",
]

#: Hay capital comprometido por el ciclo y el lector no confirmó su régimen.
CYCLE_TRACE_MISSING = "cycle_trace_missing"
#: Hay capital comprometido y el ``cycle_id`` no es alcanzable por el índice (no derivable).
CYCLE_TRACE_NOT_DERIVABLE = "cycle_trace_not_derivable"
#: Hay capital comprometido por el ciclo y no se llegó a preguntar por él.
CYCLE_TRACE_UNREQUESTED = "cycle_trace_unrequested"
#: Hay traza de régimen confirmada y ninguna reserva: el capital que la traza supone no está.
CYCLE_TRACE_ORPHAN = "cycle_trace_orphan"


def _clean(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _keys(values: Iterable[Any]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for raw in values:
        key = _clean(raw)
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _set_of(holder: Any, name: str) -> set[str]:
    raw = getattr(holder, name, None)
    return (
        set(_keys(raw))
        if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes))
        else set()
    )


@dataclass(frozen=True, slots=True)
class CycleTraceReconciliation:
    """El cruce entre capital comprometido y traza de régimen, con cada desajuste declarado."""

    missing: tuple[str, ...] = ()
    unrequested: tuple[str, ...] = ()
    not_derivable: tuple[str, ...] = ()
    orphan: tuple[str, ...] = ()
    #: Motivo por ciclo de ``missing`` (``regime_absent`` / ``regime_unconfirmed``).
    missing_reasons: Mapping[str, str] = field(default_factory=dict)
    #: Ciclos con reserva durable que entraron al cruce (el denominador de la lectura).
    reserved: int = 0

    @property
    def gaps(self) -> int:
        return (
            len(self.missing) + len(self.unrequested) + len(self.not_derivable) + len(self.orphan)
        )

    @property
    def clean(self) -> bool:
        """True solo si NINGÚN ciclo con capital quedó sin traza confirmada (ni al revés)."""
        return self.gaps == 0

    def as_dict(self) -> dict[str, Any]:
        """Resumen para el log del arranque: declara cada desajuste con su nombre."""
        return {
            "reserved": self.reserved,
            "missing": list(self.missing),
            "missingReasons": dict(sorted(self.missing_reasons.items())),
            "unrequested": list(self.unrequested),
            "notDerivable": list(self.not_derivable),
            "orphan": list(self.orphan),
            "gaps": self.gaps,
        }


def reconcile_cycle_trace(
    *,
    reservation_cycle_ids: Iterable[Any],
    reading: Any,
) -> CycleTraceReconciliation:
    """(PURA) los ciclos con reserva sin traza confirmada (y los que tienen traza sin reserva).

    ``reading`` es el ``CycleRegimeReading`` de ``AUTO-10``: se lee por su contrato público
    (``regime_by_cycle``, ``absent``, ``unconfirmed``, ``not_derivable``) para poder cruzar los
    motivos, no solo el resultado. Un ciclo con reserva que no aparece en NINGUNO de los cuatro
    conjuntos no se cuenta como ``missing``: no se preguntó por él, y eso es un hecho distinto
    (``unrequested``) que no debe disfrazarse de journal roto.
    """
    reserved = _keys(reservation_cycle_ids)
    reserved_set = set(reserved)
    confirmed = set(_keys(getattr(reading, "regime_by_cycle", {}) or {}))
    absent = _set_of(reading, "absent")
    unconfirmed = _set_of(reading, "unconfirmed")
    not_derivable_reading = _set_of(reading, "not_derivable")
    asked = confirmed | absent | unconfirmed | not_derivable_reading

    missing: list[str] = []
    reasons: dict[str, str] = {}
    unrequested: list[str] = []
    not_derivable: list[str] = []
    for cycle_id in reserved:
        if cycle_id in confirmed:
            continue
        if cycle_id in not_derivable_reading:
            not_derivable.append(cycle_id)
            continue
        if cycle_id not in asked:
            unrequested.append(cycle_id)
            continue
        missing.append(cycle_id)
        reasons[cycle_id] = "regime_unconfirmed" if cycle_id in unconfirmed else "regime_absent"

    orphan = sorted(cycle_id for cycle_id in confirmed if cycle_id not in reserved_set)
    return CycleTraceReconciliation(
        missing=tuple(missing),
        unrequested=tuple(unrequested),
        not_derivable=tuple(not_derivable),
        orphan=tuple(orphan),
        missing_reasons=reasons,
        reserved=len(reserved),
    )


def _cycle_of(row: Any) -> Any:
    """``cycle_id`` de una reserva, acepte el modelo puro, un mapping o un registro."""
    value = getattr(row, "cycle_id", None)
    if value is None and isinstance(row, Mapping):
        value = row.get("cycleId") or row.get("cycle_id")
    return value


def cycle_ids_with_reservations(
    reservations: Sequence[Any],
) -> tuple[str, ...]:
    """Ciclos declarados por una lista de reservas, sin duplicados y en orden de aparición.

    Una reserva sin ``cycle_id`` (anterior a ``2.47``) **no** aporta un ciclo vacío: "anterior a
    2.47" no es un ciclo y contarlo ensuciaría el cruce con un hueco que no existe.
    """
    return tuple(_keys(_cycle_of(row) for row in reservations))
