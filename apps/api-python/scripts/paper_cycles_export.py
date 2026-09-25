#!/usr/bin/env python3
"""AUTO-20/20B — vuelca a JSON el material PAPER **REAL** que consume el instrumento de calibración.

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

``AUTO-20B`` añade dos garantías de MATERIAL:

* **Completitud (paginación).** Las reservas de los ciclos se leen por PÁGINAS con ``offset`` hasta
  agotar el material: ``--limit`` es el tamaño de página, no un tope que pueda truncar el universo.
  Si una página llena no aporta nada nuevo, la lectura NO puede afirmar completitud y el volcado
  **se bloquea** (``exit 2``) en vez de emitir un JSON sesgado.
* **Manifest + huella.** El JSON lleva un ``material_manifest`` hermano de ``note``/``cycles``
  (nunca dentro de ``cycles`` ni en el journal): conteos del material, base de riesgo, huecos
  declarados y la huella ``material_fingerprint_v1``. Sirve para auditar que el universo medido es
  el que se cree y para comparar dos corridas sin dudar del material. Sin PG, sin material o sin
  completitud, se DECLARA y se sale con ``2``.

``AUTO-20C`` añade dos DECLARACIONES que NO cambian el material:

* **Perímetro.** Además de las versiones PEDIDAS (``requestedStrategyVersions``), el manifest
  publica las OBSERVADAS (``observedStrategyVersions``) y cuantifica los fills que quedan FUERA del
  universo solicitado —``fillsExcludedNoVersion``/``fillsExcludedOtherVersion``—. No los incluye:
  hace visible el contorno para que "orb-trend puro" no se lea sin ver qué se dejó fuera.
* **Procedencia virtual.** El material es PAPER con **dinero VIRTUAL**: el manifest declara
  ``executionReality`` (``virtual_paper_only``) y ``brokerVenue``, y si la venue NO es ``paper`` el
  volcado se BLOQUEA (``exit 2``): un artefacto PAPER no se sella con material de otra venue.

Uso::

  uv run --no-sync python apps/api-python/scripts/paper_cycles_export.py \\
      --account-id <uuid> --strategy-version orb-trend > ciclos.json
  uv run --no-sync python scripts/research/auto_replay_battery.py --walk-forward --cycles ciclos.json

README: el JSON lleva ``{"note": ..., "material_manifest": {...}, "cycles": [...]}``; la nota y la
huella se imprimen por **stderr** (nunca dentro del JSON de stdout), igual que los fixtures.

Códigos de salida:

* ``0`` — volcado (el JSON va por stdout; la nota y el recuento, por stderr).
* ``1`` — uso incorrecto (falta ``--account-id``/``--strategy-version``): lo decide ``argparse``.
* ``2`` — **BLOQUEADO**: sin PostgreSQL, sin material, sin completitud probada, o con la venue
  distinta de ``paper``, NO se imprime un JSON vacío o truncado como si fuera una medición; "no
  medido" se declara en stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

#: Nota que viaja en el JSON y que ``auto_replay_battery.py`` copia a stderr: deja escrito que este
#: material es REAL (no el fixture sintético) para que nadie lea sus veredictos como si midieran una
#: estrategia de laboratorio, y que es PAPER **VIRTUAL** — dineros simulados, jamás una plataforma
#: real—. La realidad de ejecución es la constante única de ``auto_evidence_report``.
MATERIAL_NOTE = (
    "material PAPER REAL sobre cuenta PAPER VIRTUAL (dinero VIRTUAL: nunca XTB ni ninguna "
    "plataforma real): fills durables + riesgo de reserva + régimen AUTO-10 "
    "(mismo camino que el informe, vía adaptive_instrument_cycles)"
)


class MaterialIncompleteError(RuntimeError):
    """AUTO-20B — la lectura de reservas no pudo garantizar COMPLETITUD.

    Se lanza cuando una página llena no aporta identificadores nuevos (el ``offset`` no avanza o
    el store lo ignora): seguir leyendo daría vueltas sobre el mismo material y declarar el
    JSON como "el universo" sería un sesgo de selección silencioso. El llamante lo traduce a
    ``exit 2`` (BLOQUEADO), no a un informe.
    """


class NonPaperVenueError(RuntimeError):
    """AUTO-20C — el exportador solo sella material de la venue PAPER (dinero VIRTUAL).

    Con ``broker_venue`` distinta de ``paper`` (p. ej. un carril LIVE) NO se publica un artefacto
    etiquetado como PAPER: sellar material de otra venue como evidencia PAPER sería una mentira de
    procedencia. Se traduce a ``exit 2`` (BLOQUEADO) con el motivo declarado.
    """


def _json_default(value: Any) -> Any:
    """Serializa lo que el JSON no cubre: ``Decimal`` → ``str`` y objetos con ``to_dict``.

    Los ciclos del instrumento llevan ``pnl``/``riskAmount`` en ``Decimal`` (aritmética exacta
    del FIFO) y el coste estimado como ``TradingCost``. Sin este puente, ``json.dump`` revienta
    con el material REAL —un fallo que el fixture sintético nunca ejercita—. El ``Decimal`` va
    como cadena para no perder exactitud: el lector lo vuelve a ``Decimal`` con ``cycle_r``.
    """
    if isinstance(value, Decimal):
        return str(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    raise TypeError(f"no serializable a JSON: {type(value).__name__}")


async def _read_all_reservations(
    store: Any, account_id: str, cycle_ids: list[str], *, page_size: int
) -> tuple[list[Any], bool]:
    """(I/O) lee TODAS las reservas de esos ciclos, paginando; declara si no pudo completar.

    Devuelve ``(reservas, saturado)``. La paginación avanza por ``offset`` con un orden total en
    el store, así que la concatenación de páginas es el universo sin huecos ni repeticiones. La
    parada es una página corta (``< page_size``). Una página llena sin ids NUEVOS significa que
    el ``offset`` no progresa: ``saturado=True`` —el llamante NO puede afirmar completitud—.
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


async def _export(account_id: str, versions: list[str], *, limit: int) -> dict[str, Any]:
    """(I/O) lee el material durable y lo devuelve en la forma del instrumento. Sin escribir nada."""
    from bolsa_analytics.cognitive.auto_evidence_report import (
        EXECUTION_REALITY_VIRTUAL_PAPER,
        MATERIAL_ORIGIN_PAPER_REAL,
    )
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
    # evidencia PAPER sería una mentira de procedencia: se DECLARA y se bloquea (exit 2).
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
            # AUTO-20C — PERÍMETRO: cuántos fills tiene la cuenta por versión, para DECLARAR los
            # que quedan FUERA del universo pedido (sin versión / de otra versión). Solo cuenta
            # (agregado del store): no añade material ni cambia la huella del universo medido.
            fills_by_version = await context_store.count_by_strategy_version(
                account_id=account_id
            )
            # Las MISMAS lecturas que el turno (``_v2_cycle_risk``): reservas de los ciclos que
            # aparecen en los fills y régimen durable por ``decision_id`` derivado, confirmando el
            # ``payload['cycleId']``. Un ciclo sin reserva queda con su hueco declarado.
            #
            # AUTO-20B — COMPLETITUD: la lectura se pagina hasta recuperar TODAS las reservas de
            # los ciclos pedidos. Una sola página con ``limit`` podía truncar el material sin que
            # nadie lo viera (``fills`` existen y falta el denominador ⇒ ``unmeasured_r`` por un
            # sesgo de lectura, no por la estrategia). Si no se puede garantizar completitud, se
            # DECLARA y se bloquea (``MaterialIncompleteError`` → exit 2).
            reservations, saturated = await _read_all_reservations(
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
                requested_versions=versions,
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
    return {
        "note": MATERIAL_NOTE,
        "material_manifest": manifest,
        "cycles": [dict(row) for row in cycles],
    }


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
        "--limit",
        type=int,
        default=2000,
        help=(
            "TAMAÑO DE PÁGINA de reservas (AUTO-20B: la lectura se pagina hasta completar; "
            "ya no es un tope que pueda truncar el universo en silencio)"
        ),
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
    except MaterialIncompleteError as error:
        # La lectura NO pudo garantizar completitud: un JSON parcial sería un sesgo de
        # selección disfrazado de medición. Se declara y se bloquea.
        print(f"# BLOQUEADO: {error}", file=sys.stderr)
        return 2
    except NonPaperVenueError as error:
        # AUTO-20C — la venue no es PAPER: un artefacto PAPER no se sella con material ajeno.
        print(f"# BLOQUEADO: {error}", file=sys.stderr)
        return 2
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

    manifest = payload["material_manifest"]
    print(
        f"# {len(payload['cycles'])} ciclos de {len(args.versions)} versiones "
        f"(cuenta {args.account_id}); huella {manifest['fingerprint']}",
        file=sys.stderr,
    )
    print(
        f"# perímetro: fills total={manifest['fillsTotalForAccount']} "
        f"seleccionados={manifest['fillsSelected']} "
        f"sinVersión={manifest['fillsExcludedNoVersion']} "
        f"otraVersión={manifest['fillsExcludedOtherVersion']}",
        file=sys.stderr,
    )
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False, default=_json_default)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
