#!/usr/bin/env python3
"""OPS · Cohorte DÍA-D as-run: descubrimiento real de días D y re-certificación.

Qué hace
--------
1. **Descubre** los días ``D`` que de verdad tienen fills durables de una cuenta que
   EXISTE en ``investment_accounts`` y de instrumentos que EXISTEN en ``instruments``
   y tienen barras ``1d``. Cada fila que se descarta por referencia inexistente se
   cuenta y se declara: no se publican "cuentas fantasma" (el error que publicó
   ``47 cuentas`` cuando solo había ``2``).
2. ``--run`` rejuega cada ``(cuenta, día)`` con el CLI existente
   ``apps/api-python/scripts/v2_102_dia_d_as_run.py`` (``--universe-instrument``
   repetido una vez por instrumento, nunca una lista separada por comas).
3. Tras las ejecuciones, lee los artefactos de disco y aplica ``certify_cohort`` de
   ``bolsa_application.dia_d_certification``: el veredicto de la cohorte no se
   inventa, se recalcula del sobre de auditoría de cada artefacto.

Modos
-----
* ``--dry-run`` (por defecto): descubre y lista el plan sin ejecutar ningún replay.
  También certifica, **solo lectura**, los artefactos que ya haya en disco.
* ``--run``: ejecuta el replay de cada día y después certifica la cohorte.

Garantías
---------
* **No escribe en PostgreSQL**: la conexión se abre en modo ``read_only`` y todas las
  sentencias son ``SELECT``.
* **Usa psycopg SINCRONO**: en Windows el ``ProactorEventLoop`` rompe psycopg async
  (el mismo defecto que obligó a arreglar ``v2_102``).
* **La cuenta de la ventana PAPER no se duplica**: se lee de ``WINDOW_CONFIG.account``
  en ``scripts/lib/window-forward.mjs`` (fuente única del operador).
* **Un día que falla no tumba la herramienta**: se registra con su código de salida y
  el resto de días sigue.

Uso (desde la raíz del repo)::

    .venv\\Scripts\\python.exe scripts/ops/cohorte_as_run.py --dry-run
    .venv\\Scripts\\python.exe scripts/ops/cohorte_as_run.py --run --json \\
        --out operability_runs/dia-d-as-run/cohorte-as-run.json

Salidas: ``0`` correcto · ``1`` fallo de ejecución/entorno · ``2`` no hay nada que
rejugar (se declara, no se fuerza).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import psycopg

from bolsa_application.dia_d_as_run import DEFAULT_MIN_COHORT_SAMPLES
from bolsa_application.dia_d_certification import certify_cohort

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOTENV = _REPO_ROOT / ".env"
_WINDOW_FORWARD_MJS = _REPO_ROOT / "scripts" / "lib" / "window-forward.mjs"
_AS_RUN_CLI = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_102_dia_d_as_run.py"
_AS_RUN_DIR = _REPO_ROOT / "operability_runs" / "dia-d-as-run"

_REPORT_VERSION = "cohorte-as-run/1"
_WINDOW_ACCOUNT_RE = re.compile(r"\baccount:\s*'([^']+)'")
_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_DAY_SUFFIX_RE = re.compile(r"^as-run-(?P<day>\d{4}-\d{2}-\d{2})\.json$")

#: ``ohlcv_bars.timeframe`` es un ENUM de PostgreSQL llamado ``"Timeframe"``. Se compara
#: casteando la columna a texto: así la consulta no depende del nombre exacto del tipo
#: (que psycopg resolvía como ``timeframe`` y PostgreSQL rechazaba por no existir).
_TIMEFRAME_1D = "b.timeframe::text = '1d'"

#: Tope por defecto del subproceso de un día (el propio CLI puede tardar minutos).
_DEFAULT_REPLAY_TIMEOUT_SECONDS = 3600.0


# ── configuración: .env, URL y fuente única de la cuenta de la ventana ───────


def _unquote_env_value(value: str) -> str:
    """Quita comillas envolventes (simples o dobles) de un valor del ``.env``."""
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1].strip()
    return text


def read_env_file(path: Path) -> dict[str, str]:
    """Lee un ``.env`` tolerando BOM, ``export`` y comillas.

    No interpreta expansiones ni comentarios al final de un valor: los valores se
    toman literales salvo las comillas envolventes, que se retiran. Un fichero
    ausente devuelve un mapa vacío (el llamante decide si es un error).
    """
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = _unquote_env_value(value)
    return values


def _strip_prisma_query_with_repo_helper(url: str) -> str:
    """Reutiliza el normalizador del repo (``Settings.normalize_database_url``).

    Ese helper elimina TODO el query string para quitar ``?schema=...``. Solo es seguro
    reutilizarlo cuando el query contiene únicamente ``schema``; si hay otros parámetros
    libpq (``sslmode``, ``connect_timeout``...) se reconstruye la URL conservándolos.
    """
    try:
        from bolsa_infrastructure.config import Settings
    except ImportError:  # pragma: no cover — el venv del repo siempre lo instala
        return url.split("?", 1)[0]
    return Settings.normalize_database_url(url) or url


def normalize_database_url(raw: str) -> tuple[str, str | None]:
    """Adapta ``DATABASE_URL`` a lo que entiende libpq/psycopg.

    Prisma añade ``?schema=<nombre>``, que libpq NO acepta
    (``invalid URI query parameter: schema``). Se traduce a
    ``options=-c search_path=<nombre>``; si el esquema es ``public`` se elimina el
    parámetro (el ``search_path`` por defecto ya lo cubre). El resto de parámetros
    libpq se conserva. Devuelve ``(url, schema)``.
    """
    text = (raw or "").strip()
    if not text:
        raise RuntimeError("DATABASE_URL vacía: no se puede descubrir la cohorte")
    if text.startswith("postgresql+psycopg://"):
        text = "postgresql://" + text[len("postgresql+psycopg://") :]

    split = urlsplit(text)
    if split.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError(
            f"DATABASE_URL no es PostgreSQL (scheme={split.scheme!r}); no se puede continuar"
        )

    pairs = parse_qsl(split.query, keep_blank_values=True)
    schema: str | None = None
    kept: list[tuple[str, str]] = []
    for key, value in pairs:
        if key.lower() == "schema":
            schema = value.strip()
        else:
            kept.append((key, value))

    if schema is not None and not _SCHEMA_RE.match(schema):
        raise RuntimeError(f"schema inválido en DATABASE_URL: {schema!r}")

    if not kept and (schema is None or schema.lower() == "public"):
        # Caso Prisma estándar (``?schema=public``): el helper del repo ya lo resuelve.
        return _strip_prisma_query_with_repo_helper(text), schema

    if schema is not None and schema.lower() != "public":
        kept.append(("options", f"-c search_path={schema}"))
    # ``quote`` (no ``quote_plus``): libpq no interpreta ``+`` como espacio.
    query = urlencode(kept, doseq=True, quote_via=quote)
    return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment)), schema


def resolve_database_url() -> tuple[str, str | None]:
    """``DATABASE_URL`` del entorno o, si no llega, del ``.env`` raíz (con BOM/comillas)."""
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        raw = read_env_file(_DOTENV).get("DATABASE_URL", "").strip()
    return normalize_database_url(_unquote_env_value(raw))


def describe_database(url: str, schema: str | None) -> dict[str, Any]:
    """Descripción REDACTADA de la BD (sin credenciales) para el informe."""
    split = urlsplit(url)
    return {
        "host": split.hostname,
        "port": split.port,
        "database": split.path.lstrip("/"),
        "schema": schema,
    }


def window_account_id() -> str:
    """Id de la cuenta PAPER leído de ``WINDOW_CONFIG.account`` (fuente única)."""
    try:
        source = _WINDOW_FORWARD_MJS.read_text(encoding="utf-8")
    except OSError:
        return ""
    start = source.find("export const WINDOW_CONFIG")
    if start < 0:
        return ""
    match = _WINDOW_ACCOUNT_RE.search(source[start:])
    return match.group(1).strip() if match else ""


# ── descubrimiento read-only ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TableIntegrity:
    """Recuento de UNA tabla SIN claves foráneas: filas válidas y descartes declarados.

    ``orphan_any_rows`` cuenta filas distintas con al menos una referencia rota (no se
    obtiene sumando cuenta+instrumento: una fila rota por ambos motivos cuenta una vez).
    ``without_bars_rows`` son filas con referencias existentes pero cuyo instrumento no
    tiene barras ``1d``: también se descartan, pero NO son huérfanas.
    """

    table: str
    account_column: str
    instrument_column: str
    total_rows: int
    orphan_any_rows: int
    orphan_account_rows: int
    orphan_instrument_rows: int
    both_orphan_rows: int
    without_bars_rows: int

    @property
    def valid_rows(self) -> int:
        return self.total_rows - self.orphan_any_rows - self.without_bars_rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "accountColumn": self.account_column,
            "instrumentColumn": self.instrument_column,
            "totalRows": self.total_rows,
            "validRows": self.valid_rows,
            "discardedForMissingReference": self.orphan_any_rows,
            "accountOrphanRows": self.orphan_account_rows,
            "instrumentOrphanRows": self.orphan_instrument_rows,
            "bothOrphanRows": self.both_orphan_rows,
            "excludedForMissingBars1d": self.without_bars_rows,
        }


@dataclass(frozen=True, slots=True)
class DayPlan:
    day: str
    fills: int

    def to_dict(self) -> dict[str, Any]:
        return {"day": self.day, "fills": self.fills}


@dataclass(frozen=True, slots=True)
class AccountPlan:
    account_id: str
    is_window_account: bool
    days: tuple[DayPlan, ...]
    universe: tuple[str, ...]
    universe_symbols: dict[str, str]
    universe_source: str
    fills_total: int
    fill_instruments_outside_universe: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "account": self.account_id,
            "isWindowAccount": self.is_window_account,
            "days": [item.to_dict() for item in self.days],
            "universe": list(self.universe),
            "universeSymbols": dict(self.universe_symbols),
            "universeSource": self.universe_source,
            "fills": self.fills_total,
            "fillInstrumentsOutsideUniverse": list(self.fill_instruments_outside_universe),
        }


@dataclass(frozen=True, slots=True)
class Discovery:
    plans: tuple[AccountPlan, ...]
    fills: TableIntegrity
    positions: TableIntegrity
    accounts_existing: int
    instruments_total: int
    instruments_with_bars_1d: int
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountsExisting": self.accounts_existing,
            "instrumentsTotal": self.instruments_total,
            "instrumentsWithBars1d": self.instruments_with_bars_1d,
            "fills": self.fills.to_dict(),
            "positions": self.positions.to_dict(),
            "discardedRowsByMissingReference": {
                "sim_fill_finance_context": self.fills.orphan_any_rows,
                "sim_auto_positions": self.positions.orphan_any_rows,
                "total": self.fills.orphan_any_rows + self.positions.orphan_any_rows,
            },
            "plans": [plan.to_dict() for plan in self.plans],
            "warnings": list(self.warnings),
        }


def _scalar(cursor: psycopg.Cursor[Any], sql: str, params: Sequence[Any] = ()) -> int:
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return int(row[0]) if row is not None and row[0] is not None else 0


def _fills_integrity(cursor: psycopg.Cursor[Any]) -> TableIntegrity:
    table = "sim_fill_finance_context"
    broken_account = (
        "(f.account_id IS NULL OR btrim(f.account_id) = '' OR NOT EXISTS ("
        " SELECT 1 FROM investment_accounts a WHERE a.id = f.account_id))"
    )
    broken_instrument = (
        "(f.instrument_id IS NULL OR btrim(f.instrument_id) = '' OR NOT EXISTS ("
        " SELECT 1 FROM instruments i WHERE i.id = f.instrument_id))"
    )
    instrument_without_bars = (
        "NOT " + broken_instrument + " AND NOT EXISTS ("
        " SELECT 1 FROM ohlcv_bars b WHERE b.instrument_id = f.instrument_id AND "
        + _TIMEFRAME_1D
        + ")"
    )
    total = _scalar(cursor, f"SELECT count(*) FROM {table}")
    orphan_account = _scalar(
        cursor, f"SELECT count(*) FROM {table} f WHERE {broken_account}"
    )
    orphan_instrument = _scalar(
        cursor, f"SELECT count(*) FROM {table} f WHERE {broken_instrument}"
    )
    both_orphan = _scalar(
        cursor,
        f"SELECT count(*) FROM {table} f WHERE {broken_account} AND {broken_instrument}",
    )
    orphan_any = _scalar(
        cursor,
        f"SELECT count(*) FROM {table} f WHERE {broken_account} OR {broken_instrument}",
    )
    without_bars = _scalar(
        cursor,
        f"SELECT count(*) FROM {table} f WHERE NOT {broken_account} AND {instrument_without_bars}",
    )
    return TableIntegrity(
        table=table,
        account_column="account_id",
        instrument_column="instrument_id",
        total_rows=total,
        orphan_any_rows=orphan_any,
        orphan_account_rows=orphan_account,
        orphan_instrument_rows=orphan_instrument,
        both_orphan_rows=both_orphan,
        without_bars_rows=without_bars,
    )


def _positions_integrity(cursor: psycopg.Cursor[Any]) -> TableIntegrity:
    table = "sim_auto_positions"
    broken_account = (
        "(p.account_id IS NULL OR btrim(p.account_id) = '' OR NOT EXISTS ("
        " SELECT 1 FROM investment_accounts a WHERE a.id = p.account_id))"
    )
    # El instrumento de ``sim_auto_positions`` vive en ``symbol`` y puede ser el id del
    # catálogo o su símbolo: se aceptan ambos, nunca se asume que apunta a algo.
    resolve_instrument = (
        "EXISTS (SELECT 1 FROM instruments i WHERE i.id = p.symbol OR i.symbol = p.symbol)"
    )
    broken_instrument = f"(p.symbol IS NULL OR btrim(p.symbol) = '' OR NOT {resolve_instrument})"
    instrument_without_bars = (
        f"{resolve_instrument} AND NOT EXISTS ("
        " SELECT 1 FROM instruments i JOIN ohlcv_bars b ON b.instrument_id = i.id"
        f" WHERE (i.id = p.symbol OR i.symbol = p.symbol) AND {_TIMEFRAME_1D})"
    )
    total = _scalar(cursor, f"SELECT count(*) FROM {table}")
    orphan_account = _scalar(
        cursor, f"SELECT count(*) FROM {table} p WHERE {broken_account}"
    )
    orphan_instrument = _scalar(
        cursor, f"SELECT count(*) FROM {table} p WHERE {broken_instrument}"
    )
    both_orphan = _scalar(
        cursor,
        f"SELECT count(*) FROM {table} p WHERE {broken_account} AND {broken_instrument}",
    )
    orphan_any = _scalar(
        cursor,
        f"SELECT count(*) FROM {table} p WHERE {broken_account} OR {broken_instrument}",
    )
    without_bars = _scalar(
        cursor,
        f"SELECT count(*) FROM {table} p WHERE NOT {broken_account} AND {instrument_without_bars}",
    )
    return TableIntegrity(
        table=table,
        account_column="account_id",
        instrument_column="symbol",
        total_rows=total,
        orphan_any_rows=orphan_any,
        orphan_account_rows=orphan_account,
        orphan_instrument_rows=orphan_instrument,
        both_orphan_rows=both_orphan,
        without_bars_rows=without_bars,
    )


def _account_universe(
    cursor: psycopg.Cursor[Any], account_id: str, fallback: Sequence[str]
) -> tuple[tuple[str, ...], dict[str, str], str]:
    """Universo declarado de la cuenta: posiciones durables resueltas y con barras 1d.

    ``sim_auto_positions`` es el estado operativo que el replay rejuega; si la cuenta no
    tiene posiciones durables, se cae a los instrumentos de sus fills válidos (y se
    declara la fuente). Nunca se incluye un instrumento sin barras ``1d``.
    """
    cursor.execute(
        f"""
        SELECT DISTINCT i.id, i.symbol
        FROM sim_auto_positions p
        JOIN instruments i ON i.id = p.symbol OR i.symbol = p.symbol
        WHERE p.account_id = %s
          AND EXISTS (
              SELECT 1 FROM ohlcv_bars b
              WHERE b.instrument_id = i.id AND {_TIMEFRAME_1D}
          )
        ORDER BY i.id
        """,
        (account_id,),
    )
    symbols = {str(row[0]): str(row[1]) for row in cursor.fetchall()}
    if symbols:
        return tuple(sorted(symbols)), symbols, "sim_auto_positions"

    fallback_ids = sorted({str(item) for item in fallback if str(item).strip()})
    if fallback_ids:
        placeholders = ", ".join(["%s"] * len(fallback_ids))
        cursor.execute(
            f"SELECT id, symbol FROM instruments WHERE id IN ({placeholders}) ORDER BY id",
            tuple(fallback_ids),
        )
        symbols = {str(row[0]): str(row[1]) for row in cursor.fetchall()}
        return tuple(sorted(symbols)), symbols, "sim_fill_finance_context"
    return (), {}, "none"


def discover(
    cursor: psycopg.Cursor[Any], *, accounts_filter: Sequence[str] = ()
) -> Discovery:
    """Descubre cuentas/días/universo comprobando que cada referencia EXISTE."""
    warnings: list[str] = []

    accounts_existing = _scalar(cursor, "SELECT count(*) FROM investment_accounts")
    instruments_total = _scalar(cursor, "SELECT count(*) FROM instruments")
    instruments_with_bars = _scalar(
        cursor,
        f"""
        SELECT count(DISTINCT b.instrument_id)
        FROM ohlcv_bars b
        WHERE {_TIMEFRAME_1D}
        """,
    )

    fills = _fills_integrity(cursor)
    positions = _positions_integrity(cursor)

    filter_sql = ""
    filter_params: tuple[Any, ...] = ()
    selected = [str(item).strip() for item in accounts_filter if str(item).strip()]
    if selected:
        filter_sql = " AND f.account_id = ANY(%s)"
        filter_params = (selected,)

    cursor.execute(
        f"""
        SELECT f.account_id,
               f.instrument_id,
               min(i.symbol) AS symbol,
               (f.created_at AT TIME ZONE 'UTC')::date AS day,
               count(*) AS fills
        FROM sim_fill_finance_context f
        JOIN investment_accounts a ON a.id = f.account_id
        JOIN instruments i ON i.id = f.instrument_id
        WHERE EXISTS (
            SELECT 1 FROM ohlcv_bars b
            WHERE b.instrument_id = i.id AND {_TIMEFRAME_1D}
        ){filter_sql}
        GROUP BY f.account_id, f.instrument_id, day
        ORDER BY f.account_id, day, f.instrument_id
        """,
        filter_params,
    )
    groups = cursor.fetchall()

    days_by_account: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    instruments_by_account: dict[str, set[str]] = defaultdict(set)
    rows_by_account = 0
    for account_id, instrument_id, _symbol, day, fills_count in groups:
        account = str(account_id)
        day_iso = day.isoformat() if hasattr(day, "isoformat") else str(day)
        count = int(fills_count)
        days_by_account[account][day_iso] += count
        instruments_by_account[account].add(str(instrument_id))
        rows_by_account += count

    if rows_by_account != fills.valid_rows:
        warnings.append(
            "fills: las filas agrupadas no coinciden con las filas válidas del recuento "
            f"({rows_by_account} != {fills.valid_rows}); revisa la consulta antes de confiar en el plan"
        )

    window_id = window_account_id()
    if not window_id:
        warnings.append(
            "no se pudo leer WINDOW_CONFIG.account de scripts/lib/window-forward.mjs: "
            "ninguna cuenta se marca como ventana PAPER"
        )

    plans: list[AccountPlan] = []
    for account in sorted(days_by_account):
        fill_instruments = instruments_by_account[account]
        universe, universe_symbols, source = _account_universe(
            cursor, account, sorted(fill_instruments)
        )
        outside = tuple(sorted(set(fill_instruments) - set(universe)))
        day_plans = tuple(
            DayPlan(day=day, fills=count)
            for day, count in sorted(days_by_account[account].items())
        )
        plans.append(
            AccountPlan(
                account_id=account,
                is_window_account=bool(window_id) and account == window_id,
                days=day_plans,
                universe=universe,
                universe_symbols=universe_symbols,
                universe_source=source,
                fills_total=sum(item.fills for item in day_plans),
                fill_instruments_outside_universe=outside,
            )
        )

    return Discovery(
        plans=tuple(plans),
        fills=fills,
        positions=positions,
        accounts_existing=accounts_existing,
        instruments_total=instruments_total,
        instruments_with_bars_1d=instruments_with_bars,
        warnings=tuple(warnings),
    )


# ── ejecución del replay ────────────────────────────────────────────────────


def artifact_path(account_id: str, day: str) -> Path:
    return _AS_RUN_DIR / account_id / f"as-run-{day}.json"


def build_replay_command(
    *, python: str, account_id: str, day: str, universe: Sequence[str], out: Path
) -> list[str]:
    """Comando del CLI existente.

    ``--universe-instrument`` es ``action="append"``: se repite una vez por instrumento.
    Pasar una lista separada por comas NO declara el universo (fue un bug real).
    """
    command = [
        python,
        str(_AS_RUN_CLI),
        "--at",
        day,
        "--account-id",
        account_id,
    ]
    for instrument in universe:
        command.extend(["--universe-instrument", instrument])
    command.extend(["--verify-bars", "--json", "--out", str(out)])
    return command


def run_plan(
    plans: Sequence[AccountPlan],
    *,
    python: str,
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    """Ejecuta un replay por ``(cuenta, día)``; un fallo se registra y NO detiene el resto."""
    runs: list[dict[str, Any]] = []
    total = sum(len(plan.days) for plan in plans)
    index = 0
    for plan in plans:
        for day_plan in plan.days:
            index += 1
            out = artifact_path(plan.account_id, day_plan.day)
            out.parent.mkdir(parents=True, exist_ok=True)
            command = build_replay_command(
                python=python,
                account_id=plan.account_id,
                day=day_plan.day,
                universe=plan.universe,
                out=out,
            )
            print(
                f"[{index}/{total}] {plan.account_id} D={day_plan.day} "
                f"universo={len(plan.universe)} fills={day_plan.fills}",
                flush=True,
            )
            started = time.perf_counter()
            entry: dict[str, Any] = {
                "account": plan.account_id,
                "day": day_plan.day,
                "out": str(out),
                "command": command,
                "artifactExists": False,
            }
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(_REPO_ROOT),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                entry.update(
                    {
                        "ok": False,
                        "returnCode": None,
                        "error": f"timeout tras {timeout_seconds:.0f}s",
                    }
                )
            except OSError as exc:
                entry.update({"ok": False, "returnCode": None, "error": f"OSError: {exc}"})
            else:
                ok = completed.returncode == 0 and out.is_file()
                entry.update(
                    {
                        "ok": ok,
                        "returnCode": int(completed.returncode),
                        "artifactExists": out.is_file(),
                    }
                )
                if not ok:
                    error = (completed.stderr or completed.stdout or "").strip()
                    entry["error"] = error[-2000:] if error else "sin salida del subproceso"
            entry["elapsedSeconds"] = round(time.perf_counter() - started, 3)
            runs.append(entry)
            state = "OK" if entry.get("ok") else "FALLO"
            print(f"    {state} ({entry['elapsedSeconds']}s)", flush=True)
    return runs


# ── certificación de los artefactos de disco ────────────────────────────────


def load_artifacts() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Lee todos los ``as-run-*.json`` de disco; un fichero roto se declara, no rompe."""
    artifacts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    if not _AS_RUN_DIR.is_dir():
        return artifacts, errors
    for path in sorted(_AS_RUN_DIR.rglob("as-run-*.json")):
        match = _DAY_SUFFIX_RE.match(path.name)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
        else:
            if isinstance(payload, dict):
                entry: dict[str, Any] = dict(payload)
                if not entry.get("day") and match is not None:
                    entry["day"] = match.group("day")
                artifacts.append(entry)
            else:
                errors.append({"path": str(path), "error": "el artefacto no es un objeto JSON"})
    return artifacts, errors


def certify(artifacts: Sequence[Mapping[str, Any]], *, min_samples: int) -> dict[str, Any]:
    """``certify_cohort`` del dominio: la cohorte se recalcula, no se copia."""
    return certify_cohort(artifacts, min_samples=min_samples).to_dict()


# ── informe ─────────────────────────────────────────────────────────────────


def _print_discovery(discovery: Discovery) -> None:
    fills = discovery.fills
    positions = discovery.positions
    print("Referencias inexistentes (descartadas, NO contadas como cuentas reales):")
    print(
        f"  {fills.table}: {fills.total_rows} filas, "
        f"{fills.orphan_any_rows} descartadas por referencia inexistente "
        f"(cuenta {fills.orphan_account_rows}, instrumento {fills.orphan_instrument_rows}, "
        f"ambas {fills.both_orphan_rows}), "
        f"{fills.without_bars_rows} por falta de barras 1d, {fills.valid_rows} válidas"
    )
    print(
        f"  {positions.table}: {positions.total_rows} filas, "
        f"{positions.orphan_any_rows} descartadas por referencia inexistente "
        f"(cuenta {positions.orphan_account_rows}, instrumento {positions.orphan_instrument_rows}, "
        f"ambas {positions.both_orphan_rows}), "
        f"{positions.without_bars_rows} por falta de barras 1d, {positions.valid_rows} válidas"
    )
    if discovery.warnings:
        print("Avisos del descubrimiento:")
        for warning in discovery.warnings:
            print(f"  ! {warning}")
    print()
    print(f"Cuentas con cobertura real: {len(discovery.plans)}")
    for plan in discovery.plans:
        tag = " (cuenta de la ventana PAPER)" if plan.is_window_account else ""
        print(
            f"  - {plan.account_id}{tag} · {len(plan.days)} días · "
            f"{len(plan.universe)} instrumentos"
        )
        days = ", ".join(f"{item.day} ({item.fills} fills)" for item in plan.days)
        print(f"    días: {days}")
        universe = ", ".join(
            f"{instrument} ({plan.universe_symbols.get(instrument, '?')})"
            for instrument in plan.universe
        )
        print(f"    universo ({plan.universe_source}): {universe or '(vacío)'}")
        if plan.fill_instruments_outside_universe:
            outside = ", ".join(plan.fill_instruments_outside_universe)
            print(
                "    instrumentos con fills fuera del universo declarado "
                f"(declarado, no descartado): {outside}"
            )


def _print_cohort(cohort: Mapping[str, Any], *, title: str) -> None:
    print()
    print(title)
    print(f"  verdict: {cohort.get('verdict')}")
    print(f"  samples: {cohort.get('samples')}")
    print(f"  required: {cohort.get('required')}")
    certified_days = cohort.get("certifiedDays") or []
    print(f"  certifiedDays: {', '.join(str(day) for day in certified_days) or '(ninguno)'}")
    failed = cohort.get("failed") or []
    if failed:
        print("  failed:")
        for item in failed:
            failure_reasons = "; ".join(
                str(reason) for reason in (item.get("reasons") or [])
            )
            print(
                f"    - {item.get('day')}: {item.get('verdict')} -> "
                f"{failure_reasons or '(sin motivo)'}"
            )
    else:
        print("  failed: (ninguno)")
    cohort_reasons = cohort.get("reasons") or []
    print(f"  reasons: {'; '.join(str(reason) for reason in cohort_reasons) or '(ninguno)'}")
    print(f"  hash: {cohort.get('hash')}")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


# ── CLI ─────────────────────────────────────────────────────────────────────


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Descubre los días D reales de la cohorte DÍA-D as-run (solo referencias "
            "existentes) y, con --run, rejuega y re-certifica la cohorte."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Descubre y lista el plan sin ejecutar el replay (modo por defecto).",
    )
    mode.add_argument(
        "--run",
        action="store_true",
        help="Ejecuta el replay de cada (cuenta, día) y certifica después la cohorte.",
    )
    parser.add_argument(
        "--account",
        action="append",
        default=[],
        metavar="ID",
        help="Limita el plan a esta cuenta (repetible). No usar listas separadas por comas.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_COHORT_SAMPLES,
        help=f"Muestras mínimas de la cohorte (por defecto {DEFAULT_MIN_COHORT_SAMPLES}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime el informe completo en JSON por stdout.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Escribe el informe completo en esta ruta JSON.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Intérprete que ejecuta v2_102 (por defecto, el de este proceso).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=_DEFAULT_REPLAY_TIMEOUT_SECONDS,
        help=f"Tope por día del subproceso (por defecto {_DEFAULT_REPLAY_TIMEOUT_SECONDS:.0f}s).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    mode = "run" if args.run else "dry-run"
    if args.min_samples < 1:
        print("--min-samples debe ser >= 1", file=sys.stderr)
        return 1
    if args.timeout_seconds <= 0:
        print("--timeout-seconds debe ser > 0", file=sys.stderr)
        return 1
    if mode == "run":
        if not _AS_RUN_CLI.is_file():
            print(f"no existe el CLI del replay: {_AS_RUN_CLI}", file=sys.stderr)
            return 1
        if not Path(args.python).is_file():
            print(f"no existe el intérprete indicado: {args.python}", file=sys.stderr)
            return 1

    try:
        url, schema = resolve_database_url()
    except RuntimeError as exc:
        print(f"configuración inválida: {exc}", file=sys.stderr)
        return 1

    report: dict[str, Any] = {
        "version": _REPORT_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(),
        "mode": mode,
        "database": describe_database(url, schema),
        "windowAccount": window_account_id(),
        "minSamples": args.min_samples,
        "executed": [],
        "artifactsOnDisk": 0,
        "artifactErrors": [],
    }

    try:
        with psycopg.connect(url) as connection:
            # Garantía de solo-lectura a nivel de sesión: el descubrimiento no puede escribir.
            connection.read_only = True
            with connection.cursor() as cursor:
                discovery = discover(cursor, accounts_filter=args.account)
    except psycopg.Error as exc:
        print(f"PostgreSQL no disponible o consulta fallida: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    report["discovery"] = discovery.to_dict()

    if mode == "run":
        if not discovery.plans:
            report["cohort"] = certify([], min_samples=args.min_samples)
            print("No hay ninguna (cuenta, día) con fills válidos: no se ejecuta nada.")
            _print_discovery(discovery)
            _print_cohort(report["cohort"], title="Cohorte (sin artefactos):")
            return 2
        report["executed"] = run_plan(
            discovery.plans,
            python=args.python,
            timeout_seconds=args.timeout_seconds,
        )

    artifacts, artifact_errors = load_artifacts()
    report["artifactsOnDisk"] = len(artifacts)
    report["artifactErrors"] = artifact_errors
    report["cohort"] = certify(artifacts, min_samples=args.min_samples)

    if args.out:
        _atomic_write_json(Path(args.out).expanduser(), report)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "COHORTE DÍA-D AS-RUN · "
            + ("ejecución" if mode == "run" else "descubrimiento (dry-run, sin replay)")
        )
        database = report["database"]
        print(
            f"BD: {database['host']}:{database['port']}/{database['database']} · "
            f"schema={database['schema']}"
        )
        print(
            f"Cuentas existentes: {discovery.accounts_existing} · "
            f"instrumentos: {discovery.instruments_total} "
            f"({discovery.instruments_with_bars_1d} con barras 1d)"
        )
        print()
        _print_discovery(discovery)
        if mode == "run":
            print()
            print("Ejecuciones:")
            for entry in report["executed"]:
                state = "OK" if entry.get("ok") else "FALLO"
                detail = "" if entry.get("ok") else f" · {entry.get('error', '')}"
                print(f"  - {entry['account']} {entry['day']}: {state}{detail}")
        if artifact_errors:
            print()
            print("Artefactos ilegibles (no cuentan para la cohorte):")
            for item in artifact_errors:
                print(f"  - {item['path']}: {item['error']}")
        print()
        title = (
            "Cohorte re-certificada (artefactos en disco):"
            if mode == "run"
            else "Cohorte actual en disco (solo lectura, sin ejecutar replay):"
        )
        _print_cohort(report["cohort"], title=title)
        if mode == "dry-run":
            print()
            print("SIN EJECUTAR: dry-run. Usa --run para rejugar y re-certificar.")

    if mode == "run" and any(not entry.get("ok") for entry in report["executed"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
