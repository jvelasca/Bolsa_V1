#!/usr/bin/env python3
"""AUTO-20/20B/20C — vuelca a JSON el material PAPER **REAL** que consume el instrumento.

Qué hace, exactamente: lee de PostgreSQL el material durable PAPER —fills, riesgo de reserva y
régimen— con el **lector único** de la aplicación
(``bolsa_application.auto_paper_material.read_paper_material``, AUTO-22) y emite por **stdout** el
JSON ``{"note", "material_manifest", "cycles"}`` que consume
``scripts/research/auto_replay_battery.py``.

Por qué el lector vive ahora en ``bolsa_application``: ``AUTO-22`` añade una segunda entrada al
material (el *run* de evidencia end-to-end, ``auto_evidence_run.py``). Copiar esta lectura habría
creado dos caminos capaces de divergir en silencio en el denominador de R —el defecto que
``AUTO-20`` cerró—. El exportador y el run **importan la misma** implementación; este fichero solo
se ocupa del contrato de CLI, del JSON y de los códigos de salida.

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
from decimal import Decimal
from typing import Any

# El lector es ÚNICO (AUTO-22): vive en la aplicación y este script lo importa. ``MATERIAL_NOTE``
# (nota del material) y las excepciones de bloqueo se re-exportan aquí para conservar el contrato
# público del exportador: documentos y sondas apuntan a este fichero.
from bolsa_application.auto_paper_material import (
    MATERIAL_NOTE,  # noqa: F401
    MaterialIncompleteError,
    NonPaperVenueError,
    read_all_reservations,
    read_paper_material,
)

#: Alias del paginador real. Se mantiene como nombre del MÓDULO a propósito: la sonda de fail-closed
#: lo parchea aquí (``monkeypatch.setattr(module, "_read_all_reservations", ...)``) y ``_export`` lo
#: resuelve en tiempo de llamada, de modo que la inyección sigue mordiendo sin tocar PostgreSQL.
_read_all_reservations = read_all_reservations


def _json_default(value: Any) -> Any:
    """Serializa lo que el JSON no cubre: ``Decimal`` → ``str`` y objetos con ``to_dict``.

    Los ciclos del instrumento llevan ``pnl``/``riskAmount`` en ``Decimal`` (aritmética exacta del
    FIFO) y el coste estimado como ``TradingCost``. Sin este puente, ``json.dump`` revienta con el
    material REAL —un fallo que el fixture sintético nunca ejercita—. El ``Decimal`` va como cadena
    para no perder exactitud: el lector lo vuelve a ``Decimal`` con ``cycle_r``.
    """
    if isinstance(value, Decimal):
        return str(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    raise TypeError(f"no serializable a JSON: {type(value).__name__}")


async def _export(account_id: str, versions: list[str], *, limit: int) -> dict[str, Any]:
    """(I/O) delega en el lector único y devuelve el payload del exportador. Sin escribir nada."""
    material = await read_paper_material(
        account_id,
        list(versions),
        limit=limit,
        reservations_reader=_read_all_reservations,
    )
    return material.as_dict()


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
