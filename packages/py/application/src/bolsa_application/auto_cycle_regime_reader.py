"""AUTO-10 — LECTOR del régimen por ciclo desde el journal durable (paso 3).

El escritor de ``AUTO-10`` (``auto_cycle_journal``) deja una traza por ciclo abierto con
``cycleId`` + ``marketRegime`` en el ``payload``. Este módulo es la otra mitad: convertir esas
filas en ``regime_by_cycle``, el mapa que el productor de ``AUTO-9`` (``cycle_risk``) ya sabía
consumir, de modo que el hueco ``regime_not_durable`` deje de serlo.

**Cómo se lee, y por qué así.** La sonda de coste de ``AUTO-9``
(``apps/api-python/scripts/a9_cycle_regime_read_cost_probe.py``) midió las dos vías y esta pieza
usa la barata: el ``decision_id`` del ciclo se **deriva** por intercambio de prefijo
(``cyc-<x>`` → ``dec-<x>``, ``cycle_decision_id``) y se pregunta por él, que es un campo **con
índice**; preguntar por ``payload->>'cycleId'`` no tiene índice y obliga a recorrer la tabla.

Matiz MEDIDO y declarado (paso 3): con un solo id el índice se usa (0,03 ms frente a 0,13 ms del
recorrido), pero con una tanda grande sobre una tabla pequeña el planner prefiere recorrerla
—le sale más barato que N sondas— y la tanda cuesta <0,1 ms. A escala no está medido: si el
spine crece hasta hacer caro el recorrido, la decisión es un índice (parcial o de expresión),
nunca cambiar la identidad del ciclo.

**Confirmar, no confiar.** Que un ``decision_id`` se pueda derivar no prueba que la fila sea de
ese ciclo: el fallback aleatorio acuña un ``cycle_id`` con la MISMA forma (``cyc-`` + 12 hex), y
el ``decision_id`` de un ciclo lo comparte además su entrada de ventana (mismo ``key``). Por eso
una fila solo se cree si su ``event_type`` es el de la traza Y su ``payload['cycleId']`` es
**exactamente** el ciclo pedido. Sin confirmación, el ciclo no entra en el mapa: se declara.

**Dedupe en lectura, declarado (paso 4).** El journal es *append-only* y el tick puede reintentar,
así que un mismo ciclo puede tener varias filas. La lectura no rompe por eso: el mapa se queda con
la **confirmación más nueva** (``fetch`` sirve de nueva a vieja) y lo descartado se declara en DOS
cuentas que no significan lo mismo:

* ``duplicates`` — **trazas** del mismo ciclo de más (``_is_trace``): un reintento real de la traza
  de régimen. ``collapsed_rows`` es su suma.
* ``extra_rows`` — filas de más de cualquier clase, incluida la **entrada de la decisión aprobada**
  del mismo ``decision_id`` (``collapsed_rows`` no la cuenta): ``discarded_rows`` es su suma.

Separarlas es lo que hace útil la señal. La entrada de decisión y la traza de régimen comparten
``decision_id`` **por diseño** (misma clave, mismo digest), así que en el camino durable el grupo
tiene dos filas en TODO ciclo normal: contar todas como "duplicado" daría un baseline distinto de
cero y ahogaría el único caso que interesa vigilar (una traza escrita dos veces). Ojo también a la
frontera de "más nueva": se mide solo entre las filas que **confirman**, porque la entrada de
ventana del mismo ciclo es más nueva que la traza y no puede robarle el régimen.

**Triple declaración del hueco.** El resultado no es un mapa pelado sino un ``CycleRegimeReading``
que separa tres motivos distintos, porque un solo contador mentiría en alguno de los casos:

* ``unconfirmed`` — se leyó una fila con ese ``decision_id`` pero no es usable (otro evento, otro
  ``cycleId`` o régimen declarado ``None``).
* ``absent`` — no hay ninguna fila con ese ``decision_id``.
* ``not_derivable`` — el ``cycle_id`` no tiene la forma ``cyc-``: la lectura por índice **no lo
  alcanza** y no se adivina.

Read-only: no escribe nada. Puro sobre el puerto de lectura que se le inyecta (el llamante real
le pasa ``SqlAlchemyJournalRepository.list_by_decision_ids`` de la sesión del tick).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bolsa_application.auto_cycle_journal import (
    AUTO_CYCLE_REGIME_EVENT,
    cycle_decision_id,
)

__all__ = [
    "DEFAULT_REGIME_CHUNK",
    "REGIME_READ_ABSENT",
    "REGIME_READ_NOT_DERIVABLE",
    "REGIME_READ_UNCONFIRMED",
    "CycleRegimeReading",
    "read_cycle_regimes",
]

#: Motivos declarados de un ciclo que no aporta régimen. Se publican, nunca se silencian.
REGIME_READ_UNCONFIRMED = "regime_unconfirmed"
REGIME_READ_ABSENT = "regime_absent"
REGIME_READ_NOT_DERIVABLE = "regime_not_derivable"

#: Tamaño de tanda de ids por consulta: el ``IN`` no puede crecer sin límite.
DEFAULT_REGIME_CHUNK = 500

#: Puerto de lectura: recibe ``decision_id`` derivados y devuelve las filas que existan.
RegimeFetch = Callable[[Sequence[str]], Awaitable[Sequence[Any]]]


def _clean(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _payload_of(entry: Any) -> Mapping[str, Any]:
    payload = getattr(entry, "payload", None)
    return payload if isinstance(payload, Mapping) else {}


def _is_trace(entry: Any, cycle_id: str) -> bool:
    """True si la fila es la TRAZA de ese ciclo, declare régimen o lo declare ``UNKNOWN``.

    Es la ÚNICA puerta de identidad de una traza y exige las dos cosas: el ``event_type`` de la
    traza Y que ``payload['cycleId']`` sea **exactamente** el ciclo pedido. Una traza con
    ``marketRegime = None`` **sigue siendo una traza** (declaró su hueco), y dos trazas del mismo
    ciclo sí son un reintento aunque una de ellas no aporte valor: confundir "no usable" con "no
    es traza" haría que el reintento real pasara desapercibido.

    Vive en un solo sitio a propósito. La usan el recuento de trazas (``duplicates``) y la lectura
    del régimen (``_confirmed_regime``); con la comprobación de ``cycleId`` repetida en el camino
    de lectura —donde ``traces`` ya filtró— la segunda copia sería **inobservable**: la sonda de
    mutaciones no podría morderla y afirmaría una cobertura que no tiene.
    """
    if _clean(getattr(entry, "event_type", None)) != AUTO_CYCLE_REGIME_EVENT:
        return False
    return _clean(_payload_of(entry).get("cycleId")) == cycle_id


def _confirmed_regime(entry: Any, cycle_id: str) -> str | None:
    """Régimen de la fila **solo** si la fila confirma ser la traza de ESE ciclo."""
    if not _is_trace(entry, cycle_id):
        return None
    return _clean(_payload_of(entry).get("marketRegime")) or None


@dataclass(frozen=True, slots=True)
class CycleRegimeReading:
    """El régimen medido por ciclo + el motivo declarado de cada hueco.

    ``requested`` es lo pedido (no lo encontrado): sin él, "0 confirmados" no distingue "no
    había nada que leer" de "no se pudo leer nada", que son dos hechos distintos.
    """

    regime_by_cycle: Mapping[str, str] = field(default_factory=dict)
    unconfirmed: tuple[str, ...] = ()
    absent: tuple[str, ...] = ()
    not_derivable: tuple[str, ...] = ()
    requested: int = 0
    #: TRAZAS del mismo ciclo de más (reintento de la traza): la única señal de escritura doble.
    duplicates: Mapping[str, int] = field(default_factory=dict)
    #: Filas de más de cualquier clase (incluida la entrada de ventana del mismo ``decision_id``).
    #: Es el tamaño REAL del grupo que comparte identidad; ``duplicates`` es el subconjunto que
    #: de verdad significa "esta traza se escribió dos veces". Separarlos importa: un ciclo normal
    #: comparte ``decision_id`` con su decisión aprobada, así que contar todas las filas como
    #: duplicado daría un baseline distinto de cero y ahogaría la señal que se quiere vigilar.
    extra_rows: Mapping[str, int] = field(default_factory=dict)

    @property
    def confirmed(self) -> int:
        return len(self.regime_by_cycle)

    @property
    def gaps(self) -> int:
        return len(self.unconfirmed) + len(self.absent) + len(self.not_derivable)

    @property
    def collapsed_rows(self) -> int:
        """Trazas de más que la lectura descartó al quedarse con la confirmación más nueva."""
        return sum(self.duplicates.values())

    @property
    def discarded_rows(self) -> int:
        """Todas las filas de más del grupo (trazas duplicadas + filas de otra clase)."""
        return sum(self.extra_rows.values())

    def as_dict(self) -> dict[str, Any]:
        """Resumen para el log del llamante: cuenta lo medido y DECLARA cada hueco y duplicado."""
        return {
            "requested": self.requested,
            "confirmed": self.confirmed,
            "unconfirmed": list(self.unconfirmed),
            "absent": list(self.absent),
            "notDerivable": list(self.not_derivable),
            "duplicates": dict(self.duplicates),
            "collapsedRows": self.collapsed_rows,
            "extraRows": dict(self.extra_rows),
            "discardedRows": self.discarded_rows,
        }


async def read_cycle_regimes(
    fetch: RegimeFetch,
    cycle_ids: Sequence[str],
    *,
    chunk_size: int = DEFAULT_REGIME_CHUNK,
) -> CycleRegimeReading:
    """(PURA sobre el puerto) régimen durable de cada ciclo pedido, con sus huecos declarados.

    ``cycle_ids`` se deduplica conservando el orden. Los no derivables no se consultan (la
    consulta por índice no los alcanza) y quedan declarados. El resto se pregunta en tandas
    de ``chunk_size`` y, si un ciclo tiene varias filas (reintento del tick), gana la **más
    nueva**: ``fetch`` devuelve las filas de más nueva a más vieja, así que se respeta el
    primer acierto. Pero "más nueva" se mide solo entre las que **confirman** el ciclo (la
    entrada de ventana comparte ``decision_id`` y es más nueva que la traza). Lo descartado se
    declara en dos cuentas distintas —``duplicates`` (trazas de más) y ``extra_rows`` (filas de
    cualquier clase, incluida la entrada de decisión del mismo ``decision_id``)— para que un
    reintento sea observable sin que el baseline normal lo enmascare.
    """
    keys: list[str] = []
    seen: set[str] = set()
    for raw in cycle_ids:
        key = _clean(raw)
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    if not keys:
        return CycleRegimeReading()

    derivable: dict[str, str] = {}
    not_derivable: list[str] = []
    for key in keys:
        derived = cycle_decision_id(key)
        if derived is None:
            not_derivable.append(key)
        else:
            derivable[derived] = key

    rows: list[Any] = []
    ids = list(derivable)
    size = max(1, int(chunk_size))
    for start in range(0, len(ids), size):
        rows.extend(await fetch(ids[start : start + size]))

    by_decision: dict[str, list[Any]] = {}
    for entry in rows:
        by_decision.setdefault(_clean(getattr(entry, "decision_id", None)), []).append(entry)

    regime_by_cycle: dict[str, str] = {}
    unconfirmed: list[str] = []
    absent: list[str] = []
    duplicates: dict[str, int] = {}
    extra_rows: dict[str, int] = {}
    for derived, cycle_id in derivable.items():
        candidates = by_decision.get(derived, [])
        if not candidates:
            absent.append(cycle_id)
            continue
        traces = [entry for entry in candidates if _is_trace(entry, cycle_id)]
        regime = next(
            (found for entry in traces if (found := _confirmed_regime(entry, cycle_id))),
            None,
        )
        if regime is None:
            # Hay fila(s) para ese ``decision_id``, pero ninguna confirma ser la traza de ESTE
            # ciclo: el hueco no es "no está", es "no se puede creer". Se declara distinto.
            unconfirmed.append(cycle_id)
        else:
            regime_by_cycle[cycle_id] = regime
            if len(traces) > 1:
                # Reintento del tick (o traza duplicada): el mapa no crece, pero la lectura lo
                # declara. Solo se cuenta aquí: sin confirmación no hay "ganadora" que elegir.
                duplicates[cycle_id] = len(traces) - 1
            extra = len(candidates) - 1
            if extra > 0:
                # Filas de más de cualquier clase (p.ej. la entrada de la decisión aprobada, que
                # comparte ``decision_id`` por diseño). Se declaran aparte para que el baseline no
                # se confunda con un reintento real.
                extra_rows[cycle_id] = extra

    return CycleRegimeReading(
        regime_by_cycle=regime_by_cycle,
        unconfirmed=tuple(unconfirmed),
        absent=tuple(absent),
        not_derivable=tuple(not_derivable),
        requested=len(keys),
        duplicates=duplicates,
        extra_rows=extra_rows,
    )
