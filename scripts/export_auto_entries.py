#!/usr/bin/env python
"""Exporta las entradas REALES de AUTO desde el ledger de ciclos a ``date,yahoo_symbol``.

Fuente: el ledger ``dia-d-multi-cycle-ledger-*`` que escribe::

    v2_93_dia_d_multi.py --cycles-out <ruta>

Cada fila del ledger es UN ciclo (una entrada ejecutada). ``entryDay`` es el día de
EJECUCIÓN (el fill), que es exactamente la fecha que el control de entradas aleatorias
necesita para entrar en la apertura de ese día.

Dos hechos del ledger que este script maneja explícitamente:

* ``symbol`` es el ``instruments.id`` (uuid/hex), NO el ticker. Se traduce a
  ``yahoo_symbol`` contra la BD. Sin ese mapeo el control pediría series que no existen.
* ``cycleId`` NO es único: hay reentradas sobre el mismo instrumento con el mismo id.
  Se deduplica por la clave compuesta (símbolo, entryDay, entryPrice, exitDay), que sí
  identifica la fila. ``--expect-entries`` vigila que no se pierda ninguna.

Uso::

    python scripts/export_auto_entries.py \
        --ledger operability_runs/dia-d-auto/v2_93_2026-11-09.cycles.json \
        --out entradas_auto.csv

    python scripts/export_auto_entries.py --ledger ... --start 2022-01-27 --end 2026-10-26

Solo lectura: no escribe en PostgreSQL.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

EXPECTED_ENTRIES = 192  # ciclos medidos en el artefacto dia-d 2026-11-05


def _normalized_url(raw: str) -> str:
    url = raw.strip().strip('"').split("?")[0]
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def _database_url(explicit: str | None) -> str:
    if explicit:
        return _normalized_url(explicit)
    env = os.environ.get("DATABASE_URL")
    if env:
        return _normalized_url(env)
    dotenv = Path(__file__).resolve().parents[1] / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                return _normalized_url(line.split("=", 1)[1])
    raise SystemExit(
        "Falta DATABASE_URL (variable de entorno o .env): el ledger trae instruments.id "
        "y hay que traducirlo a yahoo_symbol."
    )


def load_symbol_map(database_url: str, ids: set[str]) -> dict[str, str]:
    """``instruments.id -> yahoo_symbol`` para los ids del ledger (solo lectura)."""
    from sqlalchemy import create_engine, text

    if not ids:
        return {}
    with create_engine(database_url).connect() as conn:
        rows = conn.execute(
            text(
                """
                select id, coalesce(yahoo_symbol, symbol) as yahoo_symbol, symbol
                from instruments
                where id = any(:ids)
                """
            ),
            {"ids": sorted(ids)},
        ).fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def load_ledger(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cycles = payload.get("cycles")
    if not isinstance(cycles, list):
        raise SystemExit(f"{path}: no es un ledger de ciclos (falta 'cycles')")
    return cycles


def select_entries(
    cycles: list[dict[str, Any]], start: str, end: str
) -> tuple[list[dict[str, Any]], int, int]:
    """Filtra por entryDay y deduplica por la clave de la FILA (no por cycleId)."""
    in_window = [
        c
        for c in cycles
        if c.get("entryDay") and start <= str(c["entryDay"]) <= end
    ]
    seen: set[tuple[str, str, float, str]] = set()
    kept: list[dict[str, Any]] = []
    for cycle in sorted(in_window, key=lambda c: (str(c["entryDay"]), str(c.get("symbol")))):
        key = (
            str(cycle.get("symbol")),
            str(cycle.get("entryDay")),
            round(float(cycle.get("entryPrice") or 0.0), 8),
            str(cycle.get("exitDay")),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(cycle)
    return kept, len(in_window), len(in_window) - len(kept)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", required=True, help="ledger de ciclos (v2_93 --cycles-out)")
    ap.add_argument("--start", default="2022-01-27", help="primer entryDay incluido")
    ap.add_argument("--end", default="2026-10-26", help="último entryDay incluido")
    ap.add_argument("--out", default="entradas_auto.csv", help="CSV de salida (date,yahoo_symbol)")
    ap.add_argument(
        "--expect-entries",
        type=int,
        default=EXPECTED_ENTRIES,
        help="filas esperadas tras el filtro (0 = no validar)",
    )
    ap.add_argument("--database-url", default=None, help="por defecto DATABASE_URL o .env")
    a = ap.parse_args(argv)

    ledger_path = Path(a.ledger)
    if not ledger_path.is_absolute():
        ledger_path = Path(__file__).resolve().parents[1] / ledger_path
    if not ledger_path.exists():
        print(f"# BLOQUEADO: no existe el ledger {ledger_path}", file=sys.stderr)
        return 2

    cycles = load_ledger(ledger_path)
    entries, in_window, dropped = select_entries(cycles, str(a.start), str(a.end))
    if not entries:
        print(
            f"# BLOQUEADO: 0 entradas con entryDay en [{a.start}, {a.end}] "
            f"(ledger con {len(cycles)} ciclos)",
            file=sys.stderr,
        )
        return 1

    ids = {str(c.get("symbol")) for c in entries if c.get("symbol")}
    symbol_map = load_symbol_map(_database_url(a.database_url), ids)
    missing = sorted(ids - set(symbol_map))
    if missing:
        print(
            "# BLOQUEADO: hay instrument_id del ledger sin fila en instruments "
            f"({len(missing)}): {missing[:5]}",
            file=sys.stderr,
        )
        return 1

    rows = [
        (str(c["entryDay"]), symbol_map[str(c["symbol"])])
        for c in entries
        if c.get("entryDay") and c.get("symbol") in symbol_map
    ]
    if a.expect_entries and len(rows) != a.expect_entries:
        print(
            f"# BLOQUEADO: se esperaban {a.expect_entries} entradas y hay {len(rows)} "
            f"(en ventana {in_window}, descartadas por duplicado {dropped})",
            file=sys.stderr,
        )
        return 1

    out_path = Path(a.out)
    if not out_path.is_absolute():
        out_path = Path(__file__).resolve().parents[1] / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "yahoo_symbol"])
        writer.writerows(rows)

    dates = sorted({r[0] for r in rows})
    symbols = sorted({r[1] for r in rows})
    print(f"ledger      {ledger_path.name} · {len(cycles)} ciclos")
    print(f"ventana     [{a.start}, {a.end}] · {in_window} en ventana · {dropped} duplicados exactos")
    print(f"escrito     {out_path} · {len(rows)} filas")
    print(f"fechas      {len(dates)} distintas · {dates[0]} → {dates[-1]}")
    print(f"simbolos    {len(symbols)} distintos: {', '.join(symbols)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
