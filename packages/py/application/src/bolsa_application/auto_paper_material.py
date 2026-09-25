"""AUTO-22 — LECTOR ÚNICO del material PAPER **REAL** durable (fills + riesgo + régimen).

Qué resuelve: hasta ``v2.68`` el único sitio que sabía leer de PostgreSQL el material PAPER con
denominador de R era el exportador ``apps/api-python/scripts/paper_cycles_export.py``. Al añadir
en ``AUTO-22`` una SEGUNDA entrada (el *run* de evidencia end-to-end), copiar esa lectura habría
creado dos caminos capaces de divergir en silencio —el defecto exacto que ``AUTO-20`` cerró—. Este
módulo es la única implementación; el exportador y el run la **importan**, no la re-escriben.

Qué hace, exactamente: lee los **fills durables** de una o varias versiones de estrategia,
reconstruye el **riesgo comprometido por ciclo** (``reserved_risk``) y el **régimen** con las MISMAS
piezas que el turno AUTO durable —``cycles_from_fills``, el pegado de fricción de ``AUTO-16/17``,
``cycle_risk_from_reservations`` (``AUTO-9``) y el lector de régimen de ``AUTO-10``— y devuelve el
material en la forma que consume el instrumento de calibración.

Tres garantías de MATERIAL que no se relajan:

* **Completitud (paginación).** Las reservas de los ciclos se leen por PÁGINAS con ``offset`` hasta
  agotar el material: ``limit`` es el tamaño de página, no un tope que pueda truncar el universo. Si
  una página llena no aporta nada nuevo, la lectura NO puede afirmar completitud y se **bloquea**
  (``MaterialIncompleteError``) en vez de devolver un material sesgado.
* **Manifest + huella.** El material viaja con un ``material_manifest`` hermano (nunca dentro de
  ``cycles``): conteos, base de riesgo, huecos declarados y la huella ``material_fingerprint_v1``.
* **Procedencia PAPER virtual.** El material es PAPER con **dinero VIRTUAL**: el manifest declara
  ``executionReality`` y ``brokerVenue``, y si la venue NO es ``paper`` la lectura se BLOQUEA
  (``NonPaperVenueError``): un artefacto PAPER no se sella con material de otra venue.

Read-only: no escribe nada (ni journal ni tabla). El manifest es un artefacto de investigación.
"""

from __future__ import annotations

from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from bolsa_analytics.cognitive.auto_evidence_report import (
    EXECUTION_REALITY_VIRTUAL_PAPER,
    MATERIAL_ORIGIN_PAPER_REAL,
)

__all__ = [
    "MATERIAL_NOTE",
    "MaterialIncompleteError",
    "NonPaperVenueError",
    "PaperMaterial",
    "ReservationsReader",
    "read_all_reservations",
    "read_paper_material",
]

#: Nota que viaja en el JSON del material: deja escrito que es REAL (no el fixture sintético) y que
#: es PAPER **VIRTUAL** — dineros simulados, jamás una plataforma real—, para que nadie lea sus
#: veredictos como si midieran una estrategia de laboratorio. La realidad de ejecución es la
#: constante única de ``auto_evidence_report``.
MATERIAL_NOTE = (
    "material PAPER REAL sobre cuenta PAPER VIRTUAL (dinero VIRTUAL: nunca XTB ni ninguna "
    "plataforma real): fills durables + riesgo de reserva + régimen AUTO-10 "
    "(mismo camino que el informe, vía adaptive_instrument_cycles)"
)


class ReservationsReader(Protocol):
    """Contrato del paginador inyectable de reservas (el seam de la sonda de fail-closed).

    Es un ``Protocol`` —no un ``Callable`` con la firma suelta— porque el lector real recibe
    ``page_size`` por NOMBRE: un ``Callable`` posicional no describiría la llamada y el chequeo de
    tipos dejaría de valer.
    """

    def __call__(
        self, store: Any, account_id: str, cycle_ids: list[str], *, page_size: int
    ) -> Awaitable[tuple[list[Any], bool]]: ...


class MaterialIncompleteError(RuntimeError):
    """La lectura de reservas no pudo garantizar COMPLETITUD.

    Se lanza cuando una página llena no aporta identificadores nuevos (el ``offset`` no avanza o el
    store lo ignora): seguir leyendo daría vueltas sobre el mismo material y declarar el universo
    como completo sería un sesgo de selección silencioso. Quien llama lo traduce a BLOQUEADO
    (``exit 2``), nunca a un informe.
    """


class NonPaperVenueError(RuntimeError):
    """El material solo se sella desde la venue PAPER (dinero VIRTUAL).

    Con ``broker_venue`` distinta de ``paper`` (p. ej. un carril LIVE) NO se publica un artefacto
    etiquetado como PAPER: sellar material de otra venue como evidencia PAPER sería una mentira de
    procedencia. Se traduce a BLOQUEADO (``exit 2``) con el motivo declarado.
    """


@dataclass(frozen=True, slots=True)
class PaperMaterial:
    """Material PAPER leído: su nota declarada, su manifest/huella y los ciclos del instrumento."""

    note: str
    manifest: Mapping[str, Any]
    cycles: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        """Forma del payload del exportador: ``{note, material_manifest, cycles}``."""
        return {
            "note": self.note,
            "material_manifest": dict(self.manifest),
            "cycles": [dict(row) for row in self.cycles],
        }


async def read_all_reservations(
    store: Any, account_id: str, cycle_ids: list[str], *, page_size: int
) -> tuple[list[Any], bool]:
    """(I/O) lee TODAS las reservas de esos ciclos, paginando; declara si no pudo completar.

    Devuelve ``(reservas, saturado)``. La paginación avanza por ``offset`` con un orden total en el
    store, así que la concatenación de páginas es el universo sin huecos ni repeticiones. La parada
    es una página corta (``< page_size``). Una página llena sin ids NUEVOS significa que el ``offset``
    no progresa: ``saturado=True`` —quien llama NO puede afirmar completitud—.
    """
    collected: dict[str, Any] = {}
    offset = 0
    while True:
        page = await store.list_by_cycle_ids(
            account_id, cycle_ids, limit=page_size, offset=offset
        )
        fresh = 0
        for row in page:
            key = str(getattr(row, "reservation_id", "") or "")
            if key and key not in collected:
                collected[key] = row
                fresh += 1
        if len(page) < page_size:
            return list(collected.values()), False
        if fresh == 0:
            # Página llena que no aporta nada nuevo: el offset no avanza. Fail-closed.
            return list(collected.values()), True
        offset += page_size


async def read_paper_material(
    account_id: str,
    versions: Sequence[str],
    *,
    limit: int = 2000,
    reservations_reader: ReservationsReader = read_all_reservations,
) -> PaperMaterial:
    """(I/O) lee el material durable PAPER y lo devuelve en la forma del instrumento.

    ``reservations_reader`` es el **seam** declarado de la paginación: por defecto
    ``read_all_reservations`` (el real). Existe para que la sonda de fail-closed pueda inyectar una
    lectura que no completa y probar el BLOQUEO sin tocar PostgreSQL.

    Bloquea (no devuelve material sesgado) si la venue no es PAPER o si la lectura de reservas no
    pudo garantizar completitud.
    """
    from bolsa_application.auto_cycle_regime_reader import read_cycle_regimes
    from bolsa_application.auto_material_manifest import build_material_manifest
    from bolsa_application.auto_self_evaluation_feed import adaptive_instrument_cycles
    from bolsa_application.cycle_risk import cycle_risk_from_reservations
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    settings = get_settings()
    # AUTO-20C — la venue del artefacto es PAPER (virtual). Sellar material de otro carril como
    # evidencia PAPER sería una mentira de procedencia: se DECLARA y se bloquea.
    if str(settings.broker_venue).strip().lower() != "paper":
        raise NonPaperVenueError(
            f"venue '{settings.broker_venue}' no es PAPER: un artefacto PAPER no se sella con "
            "material de otra venue"
        )
    engine = create_engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            context_store = PostgresSimFillFinanceContextStore(session)
            reservation_store = PostgresReservationStore(session)
            repository = SqlAlchemyJournalRepository(session)

            fills: list[Any] = []
            for version in versions:
                fills.extend(
                    await context_store.list_for_strategy_version(
                        version, account_id=account_id
                    )
                )
            cycle_ids = sorted(
                {str(fill.cycle_id).strip() for fill in fills if str(fill.cycle_id or "").strip()}
            )
            # AUTO-20C — PERÍMETRO: cuántos fills tiene la cuenta por versión, para DECLARAR los que
            # quedan FUERA del universo pedido (sin versión / de otra versión). Solo cuenta
            # (agregado del store): no añade material ni cambia la huella del universo medido.
            fills_by_version = await context_store.count_by_strategy_version(
                account_id=account_id
            )
            # Las MISMAS lecturas que el turno (``_v2_cycle_risk``): reservas de los ciclos que
            # aparecen en los fills y régimen durable por ``decision_id`` derivado, confirmando el
            # ``payload['cycleId']``. Un ciclo sin reserva queda con su hueco declarado. La lectura
            # se PAGINA hasta completitud: una sola página podía truncar el material sin que nadie
            # lo viera (fills existen y falta el denominador ⇒ ``unmeasured_r`` por sesgo de lectura).
            reservations, saturated = await reservations_reader(
                reservation_store, account_id, cycle_ids, page_size=max(1, int(limit))
            )
            if saturated:
                raise MaterialIncompleteError(
                    f"la lectura de reservas no completó (ciclos={len(cycle_ids)}, "
                    f"reservas={len(reservations)}, página={max(1, int(limit))})"
                )
            reading = await read_cycle_regimes(repository.list_by_decision_ids, cycle_ids)
            cycle_risk = cycle_risk_from_reservations(
                cycle_ids,
                reservations,
                regime_by_cycle=dict(reading.regime_by_cycle),
                regime_source_durable=True,
            )
            # El ÚNICO punto donde se pega el riesgo: ``adaptive_instrument_cycles`` (público,
            # AUTO-20). La calibración y el informe durable cuelgan del mismo material.
            cycles = adaptive_instrument_cycles(fills, cycle_risk)
            # Manifest de INVESTIGACIÓN (nunca dentro de ``cycles`` ni en el journal): declara
            # conteos del material y su huella para poder auditar que el universo es el que se cree.
            manifest = build_material_manifest(
                account_id=account_id,
                requested_versions=list(versions),
                fills=fills,
                cycles=cycles,
                reservations_read=len(reservations),
                risk_read_saturated=saturated,
                export_timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                material_origin=MATERIAL_ORIGIN_PAPER_REAL,
                fills_by_version=fills_by_version,
                execution_reality=EXECUTION_REALITY_VIRTUAL_PAPER,
                broker_venue=str(settings.broker_venue),
                regime_confirmed=reading.confirmed,
                regime_absent=len(reading.absent),
                regime_unconfirmed=len(reading.unconfirmed),
                regime_not_derivable=len(reading.not_derivable),
            )
    finally:
        await engine.dispose()
    return PaperMaterial(
        note=MATERIAL_NOTE,
        manifest=manifest,
        cycles=tuple(dict(row) for row in cycles),
    )
