#!/usr/bin/env python3
"""AUTO-20 — vuelca a JSON el material PAPER **REAL** que consume el instrumento de calibración.

Qué hace, exactamente: lee de PostgreSQL los **fills durables** de una o varias versiones de
estrategia, reconstruye el **riesgo comprometido por ciclo** (``reserved_risk``) y el **régimen**
con las MISMAS piezas que el turno AUTO durable —``cycles_from_fills``, el pegado de fricción de
``AUTO-16/17``, ``cycle_risk_from_reservations`` (``AUTO-9``) y el lector de régimen de ``AUTO-10``—
y emite por **stdout** el JSON que consume ``scripts/research/auto_replay_battery.py``.

Por qué existe (el punto de ``AUTO-20``): el material que produce ``cycles_from_fills`` **no trae
base de riesgo**, y sin denominador el R **no es medible** (``cycle_risk`` declara
``risk_unmeasured``). Lanzar la calibración sobre esas filas daría un informe **vacío** —honesto,
pero inútil—. Este volcado pega el riesgo con la MISMA costura pública que el informe durable
(``adaptive_instrument_cycles``), así que la calibración y el informe miden los MISMOS ciclos: sin
un segundo camino que pueda divergir en silencio.

Uso::

  uv run --no-sync python apps/api-python/scripts/paper_cycles_export.py \\
      --account-id <uuid> --strategy-version orb-trend > ciclos.json
  uv run --no-sync python scripts/research/auto_replay_battery.py --walk-forward --cycles ciclos.json

README: el JSON lleva ``{"note": ..., "cycles": [...]}``; la nota se imprime por **stderr** (nunca
dentro del JSON de stdout), igual que los fixtures del instrumento.

Códigos de salida:

* ``0`` — volcado (el JSON va por stdout; la nota y el recuento, por stderr).
* ``1`` — uso incorrecto (falta ``--account-id``/``--strategy-version``): lo decide ``argparse``.
* ``2`` — **BLOQUEADO**: sin PostgreSQL, o sin material, NO se imprime un JSON vacío como si fuera
  una medición; "no medido" se declara en stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

#: Nota que viaja en el JSON y que ``auto_replay_battery.py`` copia a stderr: deja escrito que este
#: material es REAL (no el fixture sintético), para que nadie lea sus veredictos como si midieran
#: una estrategia de laboratorio.
MATERIAL_NOTE = (
    "material PAPER REAL: fills durables + riesgo de reserva + régimen AUTO-10 "
    "(mismo camino que el informe, vía adaptive_instrument_cycles)"
)


async def _export(account_id: str, versions: list[str], *, limit: int) -> dict[str, Any]:
    """(I/O) lee el material durable y lo devuelve en la forma del instrumento. Sin escribir nada."""
    from bolsa_application.auto_cycle_regime_reader import read_cycle_regimes
    from bolsa_application.auto_self_evaluation_feed import adaptive_instrument_cycles
    from bolsa_application.cycle_risk import cycle_risk_from_reservations
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    engine = create_engine(get_settings())
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
            # Las MISMAS lecturas que el turno (``_v2_cycle_risk``): reservas de los ciclos que
            # aparecen en los fills y régimen durable por ``decision_id`` derivado, confirmando el
            # ``payload['cycleId']``. Un ciclo sin reserva queda con su hueco declarado.
            reservations = await reservation_store.list_by_cycle_ids(
                account_id, cycle_ids, limit=limit
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
    finally:
        await engine.dispose()
    return {"note": MATERIAL_NOTE, "cycles": [dict(row) for row in cycles]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, help="cuenta cuyos fills durables se leen")
    parser.add_argument(
        "--strategy-version",
        action="append",
        dest="versions",
        required=True,
        help="versión de estrategia a volcar (repetible; sin ella no se adivina el universo)",
    )
    parser.add_argument(
        "--limit", type=int, default=2000, help="tope de reservas leídas por tanda (AUTO-9: 2000)"
    )
    args = parser.parse_args(argv)

    if any(not str(version).strip() for version in args.versions):
        print("# uso incorrecto: --strategy-version no admite cadenas vacías", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — quirks del loop en la máquina de desarrollo.
        # psycopg no corre sobre el ProactorEventLoop por defecto de Windows; el repo ya usa el
        # selector en sus pruebas PG. Sin esto, el volcado fallaría en Windows por el loop, no por
        # la base de datos — y un fallo de infraestructura no debe leerse como "sin material".
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        payload = asyncio.run(
            _export(args.account_id, list(args.versions), limit=max(1, int(args.limit)))
        )
    except Exception as error:  # noqa: BLE001 — sin lectura no hay material: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo leer el material durable ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    if not payload["cycles"]:
        print(
            "# BLOQUEADO: no hay ciclos cerrados con fill durable para esas versiones/cuenta",
            file=sys.stderr,
        )
        return 2

    print(
        f"# {len(payload['cycles'])} ciclos de {len(args.versions)} versiones "
        f"(cuenta {args.account_id})",
        file=sys.stderr,
    )
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
