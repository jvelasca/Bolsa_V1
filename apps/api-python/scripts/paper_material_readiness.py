#!/usr/bin/env python3
"""AUTO-MATERIAL-1 — PAPER MATERIAL READINESS: pre-flight del material antes del RUN (AUTO-22).

Qué hace, exactamente: lee de PostgreSQL el material PAPER durable —fills, reservas, intents de
salida y régimen— con las MISMAS piezas que el lector único (``AUTO-22``) y declara, **antes** de
``auto_evidence_run.py``, si hay ciclos cerrados con R medible por estrategia y —si no— cuál de los
eslabones del circuito falta:

    FILL → CYCLE → ENTRY+EXIT → RESERVED RISK → R

Por qué existe: en ``v2.72`` el primer RUN real se declaró BLOQUEADO con 761 fills, 0 ``cycle_id``
y 0 reservas, pero ese diagnóstico solo se veía **después** de intentar la corrida. Este gate mide
los hechos y los publica (tabla + JSON), de modo que la operación no tenga que esperar a un fallo
para entender el bloqueo.

Es un LECTOR, no un productor: **no** repara material, **no** infiere ``cycle_id``, **no** inventa
``reserved_risk`` y **no** convierte N fills en N operaciones. Un material incompleto se declara.

Uso::

  uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \\
      --account-id <uuid> --strategy-version orb-trend
  uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \\
      --account-id <uuid> --strategy-version orb-trend --json > readiness.json

Códigos de salida:

* ``0`` — **READY**: hay al menos una estrategia con el mínimo de ciclos cerrados con R medible.
* ``1`` — uso incorrecto: lo decide ``argparse``.
* ``2`` — **BLOCKED**: sin PostgreSQL, sin material, sin linaje/cierres/denominador, o venue no
  PAPER. "No medido" se declara por stderr y stderr/stdout según ``--json``; nunca un READY falso.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from typing import Any

from bolsa_application.auto_paper_material import NonPaperVenueError
from bolsa_application.paper_material_readiness import (
    DEFAULT_MIN_MEASURABLE_CYCLES_PER_STRATEGY,
    READINESS_READY,
    PaperMaterialReadiness,
    build_paper_material_readiness,
)


def _json_default(value: Any) -> Any:
    """``Decimal`` → ``str`` y objetos con ``to_dict`` (mismo puente que el exportador)."""
    if isinstance(value, Decimal):
        return str(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    raise TypeError(f"no serializable a JSON: {type(value).__name__}")


async def _read(
    account_id: str,
    versions: list[str],
    *,
    limit: int,
    min_cycles: int,
) -> PaperMaterialReadiness:
    """(I/O) lee el material durable y compone el veredicto. Read-only: no escribe nada."""
    from sqlalchemy import select

    from bolsa_application.auto_cycle_regime_reader import read_cycle_regimes
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models.tables import AutoExitOrderRow
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    settings = get_settings()
    # Misma guarda de procedencia que el instrumento: un diagnóstico PAPER no se sella con
    # material de otra venue.
    if str(settings.broker_venue).strip().lower() != "paper":
        raise NonPaperVenueError(
            f"venue '{settings.broker_venue}' no es PAPER: el gate PAPER no se corre con "
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
                    await context_store.list_for_strategy_version(version, account_id=account_id)
                )
            fills_by_version = await context_store.count_by_strategy_version(account_id=account_id)

            cycle_ids = sorted(
                {str(fill.cycle_id).strip() for fill in fills if str(fill.cycle_id or "").strip()}
            )
            reservations = await reservation_store.list_all(account_id, limit=limit)
            # ``limit`` recibido exacto ⇒ no se puede afirmar que se vio el libro entero.
            reservations_complete = len(reservations) < max(1, int(limit))

            # Linaje de SALIDA: solo la columna ``cycle_id`` (agregado ligero, read-only).
            exit_cycles = (
                (await session.execute(select(AutoExitOrderRow.cycle_id))).scalars().all()
            )
            exit_orders = [{"cycle_id": value} for value in exit_cycles]

            reading = await read_cycle_regimes(repository.list_by_decision_ids, cycle_ids)
    finally:
        await engine.dispose()

    return build_paper_material_readiness(
        account_id=account_id,
        requested_versions=list(versions),
        fills=fills,
        reservations=reservations,
        exit_orders=exit_orders,
        regime_by_cycle=dict(reading.regime_by_cycle),
        min_cycles_per_strategy=min_cycles,
        fills_by_version=fills_by_version,
        reservations_read_complete=reservations_complete,
    )


def _mark(ok: bool) -> str:
    """Marca legible y ASCII: ``[ok]`` / ``[X]`` (sin depender de emojis ni del codec)."""
    return "[ok]" if ok else "[X] "


def _print_report(readiness: PaperMaterialReadiness) -> None:
    facts = readiness.facts
    lineage = readiness.lineage
    min_cycles = int(facts["minCyclesPerStrategy"])

    print("PAPER MATERIAL READINESS")
    print("-" * 46)
    if facts.get("fillsTotalForAccount") is not None:
        print(f"Account fills (all versions)  {facts['fillsTotalForAccount']}")
    print(f"Durable fills (requested)     {facts['durableFills']}")
    print(f"Fills with cycle_id           {facts['fillsWithCycle']}  {_mark(facts['fillsWithCycle'] > 0)}")
    print(f"Closed cycles                 {facts['closedCycles']}  {_mark(facts['closedCycles'] > 0)}")
    print(
        f"Reserved-risk cycles          {facts['measurableCycles']}  "
        f"{_mark(facts['measurableCycles'] > 0)}"
    )
    print(
        f"Measurable R (>={min_cycles}/strategy)".ljust(30)
        + f"{facts['maxMeasurableCyclesPerVersion']}  "
        + _mark(bool(facts["versionsMeetingMinimum"]))
    )
    print(f"Reservations                  {facts['reservations']}  {_mark(facts['reservations'] > 0)}")
    print(f"Exit intents with cycle_id    {lineage['cycle']['exitOrdersWithCycle']}")
    print("-" * 46)
    verdict = "YES" if readiness.ready else "NO"
    print(f"AUTO-22 READY?                {verdict}")
    print("Allocation                    FROZEN")
    if readiness.blockers:
        print("\nBLOCKERS")
        for blocker in readiness.blockers:
            print(f"  - {blocker}")
    print(f"\nSello: {readiness.method}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, help="cuenta PAPER cuyos fills se diagnostican")
    parser.add_argument(
        "--strategy-version",
        action="append",
        dest="versions",
        required=True,
        help="versión de estrategia a diagnosticar (repetible)",
    )
    parser.add_argument(
        "--min-cycles",
        type=int,
        default=DEFAULT_MIN_MEASURABLE_CYCLES_PER_STRATEGY,
        help="mínimo de ciclos cerrados con R por estrategia (default declarado del protocolo)",
    )
    parser.add_argument("--limit", type=int, default=2000, help="tope de lectura de reservas")
    parser.add_argument("--json", action="store_true", help="emite el diagnóstico como JSON por stdout")
    args = parser.parse_args(argv)

    if any(not str(version).strip() for version in args.versions):
        print("# uso incorrecto: --strategy-version no admite cadenas vacías", file=sys.stderr)
        return 1
    if int(args.min_cycles) <= 0:
        print("# uso incorrecto: --min-cycles debe ser > 0", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — quirks del loop en la máquina de desarrollo.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        readiness = asyncio.run(
            _read(
                args.account_id,
                list(args.versions),
                limit=max(1, int(args.limit)),
                min_cycles=int(args.min_cycles),
            )
        )
    except NonPaperVenueError as error:
        print(f"# BLOQUEADO: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # noqa: BLE001 — sin lectura no hay diagnóstico: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo leer el material durable ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    if args.json:
        json.dump(readiness.as_dict(), sys.stdout, indent=2, ensure_ascii=False, default=_json_default)
        sys.stdout.write("\n")
    else:
        _print_report(readiness)

    if readiness.verdict == READINESS_READY:
        print(
            f"# READY: material suficiente en {readiness.facts['versionsMeetingMinimum']}",
            file=sys.stderr,
        )
        return 0
    print(
        "# BLOQUEADO: material PAPER insuficiente; motivos: "
        + "; ".join(readiness.blockers),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
