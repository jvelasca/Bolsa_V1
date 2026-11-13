"""Guardián: filas SIM que apuntan a cuentas o instrumentos que ya no existen.

``sim_auto_positions`` y ``sim_fill_finance_context`` no tienen claves foráneas (solo PK), así
que la BD acepta filas cuyo ``account_id`` o cuyo instrumento apunta a una entidad borrada. Un
preflight las contó como si fueran cuentas reales y publicó un diagnóstico equivocado (PR
#120); este script cierra ese hueco.

Hace **solo SELECT** (conexión en modo ``read_only``) y delega el recuento en la función pura
``bolsa_application.sim_reference_integrity.find_orphan_sim_rows``: aquí no se decide qué es
huérfano, solo se leen las filas y se imprime el informe.

psycopg **sincrono** a propósito: async en Windows choca con el quirk de ``ProactorEventLoop``
y este guardián debe poder correr como paso suelto de CI sin ese riesgo.

Uso (desde la raíz del repo):
    .venv\\Scripts\\python.exe packages/py/infrastructure/scripts/assert_no_orphan_sim_rows.py
    ... --json
    ... --max-rows 50

Códigos de salida:
    ``0`` sin huérfanos (escaneo completo);
    ``2`` con huérfanos;
    ``1`` error de configuración, de consulta o de uso (el guardián no pasa en silencio);
    ``3`` escaneo truncado por ``--max-rows`` y sin huérfanos: no se puede afirmar limpieza.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from bolsa_application.sim_reference_integrity import (
    FILLS_INSTRUMENT_COLUMN,
    POSITIONS_INSTRUMENT_COLUMN,
    TABLE_SIM_AUTO_POSITIONS,
    TABLE_SIM_FILL_FINANCE_CONTEXT,
    SimReferenceIntegrityReport,
    TableReferenceIntegrity,
    find_orphan_sim_rows,
)

_CONNECT_TIMEOUT = 10
#: Máximo de ids que se listan en la salida humana (``--json`` no recorta nada).
_MAX_IDS_SHOWN = 20
_DOTENV = Path(__file__).resolve().parents[4] / ".env"

_POSITIONS_SQL = (
    f"SELECT account_id, {POSITIONS_INSTRUMENT_COLUMN} FROM {TABLE_SIM_AUTO_POSITIONS} "
    f"ORDER BY account_id, engine_id, {POSITIONS_INSTRUMENT_COLUMN}"
)
_FILLS_SQL = (
    f"SELECT account_id, {FILLS_INSTRUMENT_COLUMN} FROM {TABLE_SIM_FILL_FINANCE_CONTEXT} "
    "ORDER BY execution_id"
)
_ACCOUNTS_SQL = "SELECT id FROM investment_accounts ORDER BY id"
_INSTRUMENTS_SQL = "SELECT id FROM instruments ORDER BY id"


@dataclass(frozen=True, slots=True)
class _Snapshot:
    """Filas leídas (solo columnas de referencia) e ids existentes, sin juicio todavía."""

    positions: tuple[dict[str, object], ...]
    fills: tuple[dict[str, object], ...]
    known_account_ids: tuple[str, ...]
    known_instrument_ids: tuple[str, ...]
    positions_truncated: bool
    fills_truncated: bool

    @property
    def truncated(self) -> bool:
        return self.positions_truncated or self.fills_truncated


def _load_env() -> None:
    """Carga ``.env`` sin pisar variables ya exportadas (convención del repo)."""
    if not _DOTENV.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv es dev-dependency
        return
    load_dotenv(_DOTENV, override=False)


def _database_url() -> str:
    """``DATABASE_URL`` normalizada a formato psycopg (sin ``+psycopg`` ni query string)."""
    _load_env()
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL no configurado: no se puede auditar la BD")
    url = raw.strip()
    if url.startswith("postgresql+psycopg://"):
        url = "postgresql://" + url[len("postgresql+psycopg://") :]
    # ``?schema=public`` es válido para Prisma/SQLAlchemy y NO para psycopg.
    return url.split("?", 1)[0]


def _fetch_snapshot(url: str, max_rows: int | None) -> _Snapshot:
    """Lee las filas de referencia y los ids existentes. Solo SELECT, nunca escritura."""
    import psycopg
    from psycopg.rows import dict_row

    def _select_rows(cur: Any, sql: str) -> tuple[dict[str, object], ...]:
        if max_rows is None:
            cur.execute(sql)
        else:
            cur.execute(f"{sql} LIMIT %s", (max_rows,))
        return tuple(cur.fetchall())

    with psycopg.connect(url, autocommit=True, connect_timeout=_CONNECT_TIMEOUT) as conn:
        # Defensa explícita: aunque alguien edite este script, la sesión no puede escribir.
        conn.read_only = True
        with conn.cursor(row_factory=dict_row) as cur:
            positions = _select_rows(cur, _POSITIONS_SQL)
            fills = _select_rows(cur, _FILLS_SQL)
        accounts = tuple(str(row[0]) for row in conn.execute(_ACCOUNTS_SQL).fetchall())
        instruments = tuple(str(row[0]) for row in conn.execute(_INSTRUMENTS_SQL).fetchall())

    return _Snapshot(
        positions=positions,
        fills=fills,
        known_account_ids=accounts,
        known_instrument_ids=instruments,
        positions_truncated=max_rows is not None and len(positions) >= max_rows,
        fills_truncated=max_rows is not None and len(fills) >= max_rows,
    )


def _print_ids(label: str, ids: Sequence[str]) -> None:
    """Lista ids ordenados; en salida humana se recorta y se declara lo no mostrado."""
    if not ids:
        return
    shown = ids[:_MAX_IDS_SHOWN]
    suffix = "" if len(ids) <= _MAX_IDS_SHOWN else f" (+{len(ids) - _MAX_IDS_SHOWN} más)"
    print(f"  {label} ({len(ids)} distintos){suffix}: {', '.join(shown) or '(vacío)'}")


def _print_table(report: TableReferenceIntegrity) -> None:
    """Una tabla: filas, huérfanas por motivo y solapamiento declarado."""
    print(
        f"{report.table}: {report.total_rows} filas; {report.orphan_rows} huérfanas "
        f"[cuenta={report.account_orphan_rows}, instrumento={report.instrument_orphan_rows}, "
        f"ambos={report.both_orphan_rows} (solapamiento, NO sumar)]"
    )
    if report.orphan_account_ids or report.orphan_instrument_ids:
        _print_ids("cuentas inexistentes", report.orphan_account_ids)
        _print_ids("instrumentos inexistentes", report.orphan_instrument_ids)


def _print_report(report: SimReferenceIntegrityReport, snapshot: _Snapshot) -> None:
    print(
        f"ids conocidos: {report.known_account_count} cuentas, "
        f"{report.known_instrument_count} instrumentos"
    )
    _print_table(report.positions)
    _print_table(report.fills)
    if snapshot.positions_truncated or snapshot.fills_truncated:
        truncated = [
            name
            for name, flag in (
                (TABLE_SIM_AUTO_POSITIONS, snapshot.positions_truncated),
                (TABLE_SIM_FILL_FINANCE_CONTEXT, snapshot.fills_truncated),
            )
            if flag
        ]
        print(f"AVISO: escaneo truncado por --max-rows en {', '.join(truncated)}")
    if report.clean:
        print("filas SIM huérfanas: ninguna")
    else:
        print(
            f"FALLO: {report.orphan_rows} filas SIM con referencias rotas "
            "(una fila puede fallar por cuenta y por instrumento; se declara en 'ambos')",
            file=sys.stderr,
        )


def _positive_int(raw: str) -> int:
    """``--max-rows`` debe ser un entero positivo; ``0``/negativo no significa "sin límite"."""
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"entero inválido: {raw!r}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("--max-rows debe ser > 0")
    return value


class _GuardArgumentParser(argparse.ArgumentParser):
    """Parser con salida ``1`` ante uso inválido: ``2`` queda reservado a "hay huérfanos"."""

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        print(f"FALLO: {message}", file=sys.stderr)
        raise SystemExit(1)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = _GuardArgumentParser(
        description=(
            "Detecta filas de sim_auto_positions y sim_fill_finance_context que apuntan a "
            "cuentas o instrumentos inexistentes (solo SELECT)."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="imprime el informe completo en JSON (incluye todos los ids huérfanos)",
    )
    parser.add_argument(
        "--max-rows",
        type=_positive_int,
        default=None,
        metavar="N",
        help="lee como máximo N filas por tabla (diagnóstico; un escaneo truncado no es verde)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        url = _database_url()
    except RuntimeError as exc:
        print(f"FALLO: {exc}", file=sys.stderr)
        return 1
    try:
        snapshot = _fetch_snapshot(url, args.max_rows)
    except Exception as exc:  # noqa: BLE001 - el guardián debe fallar, no skipear
        print(f"FALLO: no se pudo auditar la BD: {exc}", file=sys.stderr)
        return 1

    report = find_orphan_sim_rows(
        snapshot.positions,
        snapshot.fills,
        snapshot.known_account_ids,
        snapshot.known_instrument_ids,
    )

    if args.json:
        payload = report.to_dict()
        payload["scan"] = {
            "maxRows": args.max_rows,
            "positionsRowsRead": len(snapshot.positions),
            "fillsRowsRead": len(snapshot.fills),
            "positionsTruncated": snapshot.positions_truncated,
            "fillsTruncated": snapshot.fills_truncated,
            "truncated": snapshot.truncated,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_report(report, snapshot)

    if not report.clean:
        return 2
    if snapshot.truncated:
        # Un escaneo parcial sin huérfanos NO demuestra limpieza: no puede salir 0.
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
