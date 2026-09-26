#!/usr/bin/env python3
"""AUTO-MATERIAL-1/2 — PAPER MATERIAL READINESS: pre-flight del material antes del RUN (AUTO-22).

Qué hace, exactamente: lee de PostgreSQL el material PAPER durable —fills, reservas, intents de
salida y régimen— con las MISMAS piezas que el lector único (``AUTO-22``) y declara, **antes** de
``auto_evidence_run.py``, en qué NIVEL está el material:

    FILL → CYCLE → ENTRY+EXIT → RESERVED RISK → R

* ``PRODUCER_READY`` — la estructura está completa (linaje, reservas, cierres, salidas, R medible).
* ``EVIDENCE_READY`` — además hay ``>=min`` ciclos medibles por estrategia (nivel por defecto).

Por qué existe: en ``v2.72`` el primer RUN real se declaró BLOQUEADO con 761 fills, 0 ``cycle_id``
y 0 reservas, pero ese diagnóstico solo se veía **después** de intentar la corrida. Este gate mide
los hechos y los publica (tabla + JSON), y desde ``v2.74`` separa "el material está bien formado"
de "ya hay evidencia estadística bastante".

Es un LECTOR, no un productor: **no** repara material, **no** infiere ``cycle_id``, **no** inventa
``reserved_risk`` y **no** convierte N fills en N operaciones. Un material incompleto se declara.

Uso::

  uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \\
      --account-id <uuid> --strategy-version orb-trend
  uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \\
      --account-id <uuid> --strategy-version orb-trend --level producer
  uv run --no-sync python apps/api-python/scripts/paper_material_readiness.py \\
      --account-id <uuid> --strategy-version orb-trend --json > readiness.json

Códigos de salida:

* ``0`` — se alcanzó el nivel pedido (``producer`` o ``evidence``).
* ``1`` — uso incorrecto: lo decide ``argparse``.
* ``2`` — **BLOCKED**: sin PostgreSQL, sin material, sin linaje/cierres/denominador, venue no PAPER
  o por debajo del nivel pedido. "No medido" se declara por stderr; nunca un READY falso.
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
    from sqlalchemy import func, select

    from bolsa_application.auto_cycle_regime_reader import read_cycle_regimes
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models.tables import (
        AutoExitOrderRow,
        PortfolioReservationRow,
        SimFillFinanceContextRow,
    )
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

            # Linaje de SALIDA: la columna ``cycle_id`` de los intents de ESTA cuenta (agregado
            # ligero, read-only). Acotado por cuenta: un exit de otra cuenta no puede hacer pasar
            # el bloque de productor.
            exit_cycles = (
                (
                    await session.execute(
                        select(AutoExitOrderRow.cycle_id).where(
                            AutoExitOrderRow.account_id == account_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            exit_orders = [{"cycle_id": value} for value in exit_cycles]

            # Población TOTAL de la tabla (informativa): separa "lo que hay en la base" del
            # universo real del instrumento/cuenta. Nunca entra en un veredicto.
            database_totals = {
                "fills": int(
                    (await session.execute(select(func.count()).select_from(SimFillFinanceContextRow))).scalar_one()
                ),
                "reservations": int(
                    (
                        await session.execute(
                            select(func.count()).select_from(PortfolioReservationRow)
                        )
                    ).scalar_one()
                ),
                "exitOrders": int(
                    (await session.execute(select(func.count()).select_from(AutoExitOrderRow))).scalar_one()
                ),
            }

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
        database_totals=database_totals,
    )


def _mark(ok: bool) -> str:
    """Marca legible y ASCII: ``[ok]`` / ``[X]`` (sin depender de emojis ni del codec)."""
    return "[ok]" if ok else "[X] "


def _print_report(readiness: PaperMaterialReadiness, *, level: str) -> None:
    facts = readiness.facts
    lineage = readiness.lineage
    min_cycles = int(facts["minCyclesPerStrategy"])
    level_name = "producer" if level == "producer" else "evidence"

    print(f"PAPER MATERIAL READINESS (level={level_name})")
    print("-" * 52)

    # Las TRES poblaciones, separadas para que "761 fills" no se lea como cientos de operaciones
    # del instrumento (son la tabla entera; el universo de esta cuenta puede ser 4).
    database = facts.get("databaseTotals")
    if database is not None:
        print("DATABASE TOTAL (all accounts/versions)")
        print(f"  fills (whole table)         {database['fills']}")
        print(f"  reservations (whole table)  {database['reservations']}")
        print(f"  exit orders (whole table)   {database['exitOrders']}")
        print("-" * 52)
    print(f"INSTRUMENT UNIVERSE (account {facts.get('account')})")
    if facts.get("fillsTotalForAccount") is not None:
        print(f"  fills (all versions)        {facts['fillsTotalForAccount']}")
    else:
        print("  fills (all versions)        (not measured)")
    print("-" * 52)
    print("AUTO MATERIAL (requested versions)")
    print(f"  durable fills               {facts['durableFills']}")
    print(
        f"  fills with cycle_id         {facts['fillsWithCycle']}  "
        f"{_mark(facts['fillsWithCycle'] > 0)}"
    )
    print(f"  closed cycles               {facts['closedCycles']}  {_mark(facts['closedCycles'] > 0)}")
    print(
        f"  reserved-risk cycles        {facts['measurableCycles']}  "
        f"{_mark(facts['measurableCycles'] > 0)}"
    )
    print(f"  exit intents with cycle_id   {lineage['cycle']['exitOrdersWithCycle']}")
    print(f"  reservations                {facts['reservations']}  {_mark(facts['reservations'] > 0)}")
    print(
        f"  measurable R (>={min_cycles}/strategy)".ljust(30)
        + f"{facts['maxMeasurableCyclesPerVersion']}  "
        + _mark(bool(facts["versionsMeetingMinimum"]))
    )
    print("-" * 52)
    print(f"PRODUCER READY?               {'YES' if readiness.producer_ready else 'NO'}")
    print(f"EVIDENCE READY?               {'YES' if readiness.evidence_ready else 'NO'}")
    print("Allocation                    FROZEN")
    if readiness.producer_blockers:
        print("\nPRODUCER BLOCKERS")
        for blocker in readiness.producer_blockers:
            print(f"  - {blocker}")
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
    parser.add_argument(
        "--level",
        choices=("producer", "evidence"),
        default="evidence",
        help="nivel exigido: 'producer' (estructura) o 'evidence' (estructura + mínimo; default)",
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
        _print_report(readiness, level=args.level)

    if readiness.achieved(args.level):
        print(
            f"# {readiness.verdict}: nivel '{args.level}' alcanzado "
            f"(nivel medido: {readiness.verdict})",
            file=sys.stderr,
        )
        return 0
    print(
        f"# BLOQUEADO: nivel '{args.level}' NO alcanzado (nivel medido: {readiness.verdict}); "
        "motivos: "
        + "; ".join(readiness.blockers),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
