#!/usr/bin/env python3
"""Paquete de cierre de una medicion sellada de la ventana PAPER (read-only).

Que es
------
El instrumento que reune, para un dia de la ventana, todo lo que el dictamen de cierre necesita
comprobar: ticks efectivos frente al contador del runner, frontera de barra ``B``, cobertura real de
la barra, material durable CON identificadores, ciclos cerrados, atestacion del arbol (version,
Alembic, freeze, hashes) y las filas del ledger del dia.

DECLARACION EXPLICITA (leer antes de usar)
------------------------------------------
* **Read-only.** Abre una conexion con ``default_transaction_read_only = on`` y solo hace ``SELECT``.
  No abre el motor, no escribe en PostgreSQL, no toca el journal durable, no migra, no envia senales
  a ningun proceso y no modifica el arbol ni el pin.
* **No fabrica.** Un dato ausente se publica como ``null`` con su motivo (``UNKNOWN != 0``); un cero
  solo se publica si la consulta devolvio filas y el recuento es realmente cero.
* **Snapshot.** Con ``--snapshot`` el paquete se puede emitir con la corrida viva: los artefactos
  que aun no existen (``forward.json``, ``manifest`` definitivo, certificacion) viajan ``null`` y se
  declaran como pendientes en vez de tumbar el paquete.

Uso (desde la raiz del repo)::

    uv run --no-sync python scripts/ops/final_package.py --day 20261106 --snapshot
    uv run --no-sync python scripts/ops/final_package.py --day 20261106

Codigos de salida: ``0`` paquete emitido (aunque tenga huecos), ``1`` uso incorrecto, ``2`` no se
pudo leer la base o el repositorio.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "operability_runs" / "window-runs"
WINDOW_CONFIG_MJS = ROOT / "scripts" / "lib" / "window-forward.mjs"
WINDOW_JSON = ROOT / "operability_runs" / "operability-window.json"

_ISO = "%Y-%m-%dT%H:%M:%SZ"


def _die(message: str, code: int = 2) -> int:
    print(f"# BLOQUEADO: {message}", file=sys.stderr)
    return code


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def git(*args: str) -> str | None:
    try:
        done = subprocess.run(  # noqa: S603 - git local, argumentos literales
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return done.stdout.strip() or None


def package_version() -> str | None:
    data = read_json(ROOT / "package.json")
    return data.get("version") if isinstance(data, dict) else None


def window_pin() -> dict[str, Any] | None:
    """Pin operativo: ``WINDOW_CONFIG`` del runner (no clave de freeze, vive en ``scripts/``)."""
    try:
        text = WINDOW_CONFIG_MJS.read_text(encoding="utf-8")
    except OSError:
        return None
    pin: dict[str, Any] = {}
    for key in ("commit", "appsHash", "packagesHash", "account", "versionA", "versionB"):
        found = re.search(rf"^\s*{key}:\s*'([^']*)'", text, re.MULTILINE)
        pin[key] = found.group(1) if found else None
    watch = re.search(r"^\s*watchSize:\s*(\d+)", text, re.MULTILINE)
    pin["watchSize"] = int(watch.group(1)) if watch else None
    return pin


def dsn() -> str:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL no declarada en el entorno ni en .env")
    return re.sub(r"^postgresql(\+psycopg)?://", "postgresql://", raw).split("?", 1)[0]


class Reader:
    """SELECT-only con savepoint: una consulta que no aplica no aborta el paquete."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def rows(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with self._conn.transaction():
            cursor = self._conn.execute(sql, params)
            columns = [col.name for col in cursor.description or ()]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        found = self.rows(sql, params)
        return found[0] if found else None

    def guarded(self, sql: str, params: tuple = ()) -> Any:
        """Filas, o la declaracion del motivo por el que esa consulta no aplica."""
        try:
            return self.rows(sql, params)
        except Exception as exc:  # noqa: BLE001 - se declara, no se inventa
            first = str(exc).splitlines()[0][:120]
            return {"unreadable": first}

    def guarded_one(self, sql: str, params: tuple = ()) -> Any:
        """Primera fila de una consulta agregada, o el motivo por el que no aplica."""
        found = self.guarded(sql, params)
        if isinstance(found, list):
            return found[0] if found else None
        return found


def _lock(run_dir: Path) -> dict[str, Any] | None:
    data = read_json(run_dir / ".run.lock" / "lock.json")
    return data if isinstance(data, dict) else None


def _segment(
    reader: Reader, engine_ticks: str, start: datetime, end: datetime | None
) -> dict[str, Any]:
    """Tramo homogeneo de ticks: recuento, actividad, propuestas, vetos y motivos."""
    bounds = "tick_at >= %s"
    params: list[Any] = [engine_ticks, start]
    if end is not None:
        bounds += " and tick_at < %s"
        params.append(end)
    aggregate = reader.guarded_one(
        f"select count(*) as ticks, min(seq) as seq_min, max(seq) as seq_max,"
        f" min(tick_at) as first_tick, max(tick_at) as last_tick,"
        f" coalesce(sum(proposals), 0)::int as proposals,"
        f" coalesce(sum(vetoes), 0)::int as vetoes,"
        f" count(*) filter (where activity = 'NO_ACTIVITY') as no_activity,"
        f" count(*) filter (where vetoes > 0) as ticks_with_vetoes"
        f" from auto_engine_ticks where engine_id = %s and {bounds}",
        tuple(params),
    )
    activity = reader.guarded(
        f"select activity, count(*) as ticks, coalesce(sum(proposals), 0)::int as proposals,"
        f" coalesce(sum(vetoes), 0)::int as vetoes"
        f" from auto_engine_ticks where engine_id = %s and {bounds}"
        f" group by activity order by ticks desc",
        tuple(params),
    )
    reasons = reader.guarded(
        f"select reason, count(*) as ticks, coalesce(sum(proposals), 0)::int as proposals,"
        f" coalesce(sum(vetoes), 0)::int as vetoes"
        f" from auto_engine_ticks where engine_id = %s and {bounds}"
        f" group by reason order by ticks desc",
        tuple(params),
    )
    return {"aggregate": aggregate, "by_activity": activity, "by_reason": reasons}


def build(
    day: str, snapshot: bool, expected_ticks: int | None, cycles_export_exit: int | None
) -> dict[str, Any]:
    import psycopg

    day_iso = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    day_date = date.fromisoformat(day_iso)
    run_dir = RUNS / day
    forward = ROOT / "operability_runs" / f"forward-market-{day}.json"
    forward_copy = run_dir / "forward.json"
    manifest_path = run_dir / "manifest.json"
    lock = _lock(run_dir)
    pin = window_pin()
    manifest = read_json(manifest_path)
    forward_json = read_json(forward) or read_json(forward_copy)

    if pin is None:
        raise RuntimeError("no se pudo leer WINDOW_CONFIG de scripts/lib/window-forward.mjs")

    run_start = _dt((lock or {}).get("startedAt"))
    if run_start is None and isinstance(forward_json, dict):
        run_start = _dt(forward_json.get("startedAt"))

    bundle: dict[str, Any] = {
        "day": day,
        "dayIso": day_iso,
        "mode": "snapshot" if snapshot else "definitivo",
        "generatedAt": datetime.now(UTC).strftime(_ISO),
        "declaration": (
            "Paquete read-only. Un dato ausente viaja null con su motivo; un 0 solo se publica "
            "cuando la consulta devolvio filas. Ningun umbral del gate se toca."
        ),
        "artifacts": {
            "forward": {
                "path": str(forward.relative_to(ROOT)),
                "exists": forward.is_file(),
                "sha256": sha256_file(forward),
            },
            "forward_copy": {
                "path": str(forward_copy.relative_to(ROOT)),
                "exists": forward_copy.is_file(),
                "sha256": sha256_file(forward_copy),
            },
            "window_global": {
                "path": str(WINDOW_JSON.relative_to(ROOT)),
                "exists": WINDOW_JSON.is_file(),
                "sha256": sha256_file(WINDOW_JSON),
                "note": (
                    "Fichero global de la ultima corrida que llego al paso window; NO es el "
                    "window.json de esta corrida si el runner no ha cerrado. La copia del dia "
                    "vive en window-runs/<dia>/window.json."
                ),
            },
            "window_run_copy": {
                "path": str((run_dir / "window.json").relative_to(ROOT)),
                "exists": (run_dir / "window.json").is_file(),
                "sha256": sha256_file(run_dir / "window.json"),
            },
            "manifest": {
                "path": str(manifest_path.relative_to(ROOT)),
                "exists": manifest_path.is_file(),
                "sha256": sha256_file(manifest_path),
            },
            "locked_day": {
                "path": str((run_dir / ".run.lock" / "lock.json").relative_to(ROOT)),
                "exists": lock is not None,
                "content": lock,
            },
            "aborted_attempt": {
                name: sha256_file(run_dir / "attempt-1940z-oldtree" / name)
                for name in ("forward.err.txt", "manifest.json", "preflight.json")
            },
        },
        "ledger": _ledger_rows(day),
        "attestation": _attestation(pin, manifest),
        "gate": _gate(forward_json, manifest, lock, snapshot),
    }

    with psycopg.connect(dsn()) as conn:
        conn.execute("SET default_transaction_read_only = on")
        conn.execute("SET statement_timeout = '30s'")
        reader = Reader(conn)
        engine = _engine_id(reader, day_iso)
        frontier = datetime.combine(day_date + timedelta(days=1), time.min, tzinfo=UTC)
        attestation = bundle["attestation"]
        attestation["alembic"] = reader.guarded_one("select version_num from alembic_version")
        bundle["ticks"] = _ticks(reader, engine, run_start, snapshot)
        bundle["bar_frontier"] = _bar_frontier(reader, engine, run_start, day_date, snapshot)
        blind = (bundle["bar_frontier"].get("blind") or {}).get("aggregate")
        blind_start = blind.get("first_tick") if isinstance(blind, dict) else None
        bundle["bar_coverage"] = _bar_coverage(
            reader, day_date, pin.get("watchSize"), run_start, frontier, blind_start
        )
        bundle["material"] = _material(reader, day_iso, pin.get("account"), engine)
        bundle["cycles"] = _cycles(reader, day_iso)
        attestation["checks"]["windowProvenanceMatchesRunCopy"] = _window_provenance_check(
            forward_json, bundle["artifacts"]["window_run_copy"]["sha256"]
        )

    cert_paths = {
        "window": ROOT / "operability_runs" / "paper-window-certification" / f"cert-{day}.json",
        "cycles": ROOT / "operability_runs" / f"paper-cycles-{day}.json",
        "cycles_stderr": ROOT / "operability_runs" / f"paper-cycles-{day}.err.txt",
        "operational": _resolve_operational(day),
    }
    day_list = ((read_json(cert_paths["window"]) or {}).get("certification") or {}).get(
        "dayList"
    ) or []
    with psycopg.connect(dsn()) as conn:
        conn.execute("SET default_transaction_read_only = on")
        reader = Reader(conn)
        bundle["windowDays"] = _window_days_audit(reader, list(day_list), cert_paths)

    ticks_agg = bundle["ticks"].get("aggregate")
    bundle["termination"] = _termination(
        {
            "forward": forward,
            "forward_copy": forward_copy,
        },
        lock,
        bundle["ledger"],
        expected_ticks,
        ticks_agg,
    )
    bundle["certification"] = _certification(cert_paths, cycles_export_exit, expected_ticks)
    return bundle


def _engine_id(reader: Reader, day_iso: str) -> str | None:
    found = reader.guarded(
        "select engine_id, count(*) as ticks from auto_engine_ticks"
        " where tick_at::date = %s group by engine_id order by ticks desc limit 1",
        (day_iso,),
    )
    if isinstance(found, list) and found:
        return str(found[0]["engine_id"])
    return None


def _ledger_rows(day: str) -> list[dict[str, Any]]:
    """Todas las filas del dia: no se colapsan el intento fallido y el definitivo."""
    path = RUNS / "ledger.jsonl"
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if str(row.get("day")) != day:
            continue
        rows.append(
            {
                key: row.get(key)
                for key in (
                    "day",
                    "status",
                    "reason",
                    "account",
                    "versionA",
                    "configMode",
                    "watchSize",
                    "freeze",
                    "gate",
                    "steps",
                    "startedAt",
                    "finishedAt",
                    "durationMs",
                )
            }
        )
    return rows


def _attestation(pin: dict[str, Any], manifest: Any) -> dict[str, Any]:
    head_apps = git("rev-parse", "HEAD:apps")
    head_packages = git("rev-parse", "HEAD:packages")
    freeze = (manifest or {}).get("freeze") if isinstance(manifest, dict) else None
    freeze_apps = freeze.get("apps") if isinstance(freeze, dict) else None
    freeze_packages = freeze.get("packages") if isinstance(freeze, dict) else None
    return {
        "packageVersion": package_version(),
        "alembic": None,
        "git": {
            "head": git("rev-parse", "HEAD"),
            "headShort": git("rev-parse", "--short", "HEAD"),
            "branch": git("branch", "--show-current"),
            "apps": head_apps,
            "packages": head_packages,
        },
        "pin": {
            "commit": pin.get("commit"),
            "appsHash": pin.get("appsHash"),
            "packagesHash": pin.get("packagesHash"),
            "account": pin.get("account"),
            "versionA": pin.get("versionA"),
            "versionB": pin.get("versionB"),
            "watchSize": pin.get("watchSize"),
        },
        "checks": {
            "appsMatchesPin": bool(head_apps and head_apps == pin.get("appsHash")),
            "packagesMatchesPin": bool(head_packages and head_packages == pin.get("packagesHash")),
            "manifestFreezeOk": freeze.get("ok") if isinstance(freeze, dict) else None,
            "manifestFreezeApps": freeze_apps,
            "manifestFreezePackages": freeze_packages,
            "manifestFreezeMatchesPin": bool(
                freeze_apps == pin.get("appsHash") and freeze_packages == pin.get("packagesHash")
            ),
        },
        "freezeRule": (
            "El freeze son los dos tree hashes (apps/packages). Una nota de etiqueta distinta "
            "entre el commit del pin y HEAD es esperada y no mueve el freeze. Un manifest con "
            "hashes distintos de los del pin describe OTRA corrida (p.ej. el intento pre-sello)."
        ),
    }


def _pid_alive(pid: int | None) -> bool | None:
    """¿Sigue vivo el PID que declara el lock? `None` si no se pudo comprobar."""
    if not pid:
        return None
    try:
        done = subprocess.run(  # noqa: S603 - tasklist local, filtro literal
            ["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return str(int(pid)) in done.stdout


def _termination(
    artifact_paths: dict[str, Path],
    lock: dict[str, Any] | None,
    ledger: list[dict[str, Any]],
    expected_ticks: int | None,
    observed_ticks: Any,
) -> dict[str, Any]:
    """Cómo termino la corrida, leido de artefactos y del proceso: no se supone."""
    forward_ready = artifact_paths["forward"].is_file() or artifact_paths["forward_copy"].is_file()
    lock_pid = (lock or {}).get("pid")
    alive = _pid_alive(lock_pid)
    lock_day = str((lock or {}).get("day") or "") or None
    lock_start = _dt((lock or {}).get("startedAt"))
    this_run_row = [
        row
        for row in ledger
        if lock_day
        and str(row.get("day")) == lock_day
        and row.get("status") != "NON_MARKET_DAY"
        and (
            lock_start is None or (_dt(str(row.get("startedAt") or "")) or lock_start) >= lock_start
        )
    ]
    ticks = observed_ticks.get("ticks") if isinstance(observed_ticks, dict) else None
    if forward_ready:
        status = "COMPLETED"
        reading = "forward.json escrito: el runner completo su finalizacion."
    elif lock is not None and alive is False:
        status = "PREMATURE_TERMINATION"
        reading = (
            "El proceso del lock ya no existe y no hay forward.json: la corrida termino sin "
            "finalizar. Los ticks durables son el unico registro; el contador del runner y su "
            "resumen no existen."
        )
    elif lock is not None and alive is True:
        status = "RUNNING"
        reading = "El proceso del lock sigue vivo: la corrida continua."
    else:
        status = "UNKNOWN"
        reading = "Sin forward.json y sin lock legible: no se puede afirmar como termino."
    return {
        "status": status,
        "reading": reading,
        "forwardWritten": forward_ready,
        "lock": lock,
        "lockPidAlive": alive,
        "ledgerRowsForLockedDay": this_run_row,
        "hasFinalLedgerRow": bool(
            [row for row in this_run_row if row.get("status") in {"MEDIDO", "HARD_ERROR"}]
        ),
        "ticksObserved": ticks,
        "ticksExpected": expected_ticks,
        "ticksMissing": (expected_ticks - ticks)
        if (expected_ticks and ticks is not None)
        else None,
        "note": (
            "Un error de Python habria dejado traceback y habria escrito la fila del ledger (asi "
            "ocurrio al matar el intento de 19:40Z). Sin fila y sin rastro, lo que desaparecio fue "
            "el proceso node del runner. El registro de energia dice si hubo suspension."
        ),
    }


def _window_days_audit(reader: Reader, day_list: list[str], artifacts: Any) -> dict[str, Any]:
    """Por que cada dia del gate cuenta como dia de ventana: barra, fills, ticks y motivos."""
    rows: list[dict[str, Any]] = []
    for day in day_list:
        rows.append(
            {
                "day": day,
                "barsForDay": reader.guarded_one(
                    "select count(distinct instrument_id) as instruments from ohlcv_bars"
                    " where timeframe = '1d' and timestamp::date = %s",
                    (day,),
                ),
                "fills": reader.guarded_one(
                    "select count(*) as fills from sim_fill_finance_context"
                    " where created_at::date = %s",
                    (day,),
                ),
                "ticks": reader.guarded_one(
                    "select count(*) as ticks, coalesce(sum(proposals), 0)::int as proposals,"
                    " coalesce(sum(vetoes), 0)::int as vetoes"
                    " from auto_engine_ticks where tick_at::date = %s",
                    (day,),
                ),
                "tickReasons": reader.guarded(
                    "select reason, count(*) as ticks from auto_engine_ticks"
                    " where tick_at::date = %s group by reason order by ticks desc",
                    (day,),
                ),
            }
        )
    return {
        "dayList": day_list,
        "days": rows,
        "source": (
            "v2_98/v2_100 declaran `days` como cubos de CALENDARIO con fill, ciclo cerrado O "
            "entrada de journal (v2_80 `_collect`: days = fills | cycles | journal). Un dia con "
            "solo entradas de journal `idle` cuenta como dia del gate."
        ),
        "certificationArtifacts": artifacts,
    }


def _resolve_operational(day: str) -> Path:
    """El bundle v2_100 escribe en `.../<captura>/evidence.json`; se busca el mas reciente."""
    base = ROOT / "operability_runs" / f"operational-certification-{day}"
    candidates = sorted(
        base.glob("*/evidence.json"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    return candidates[0] if candidates else base / day / "evidence.json"


def _certification(
    paths: dict[str, Path], cycle_export_exit: int | None, expected_ticks: int | None
) -> dict[str, Any]:
    """Ingiere lo que ya se ejecuto: rutas, hashes y veredictos. No inventa ninguno."""
    window_cert = read_json(paths["window"])
    operational = read_json(paths["operational"])
    cycles_json = read_json(paths["cycles"])
    cert_block = (
        (window_cert or {}).get("certification", {}) if isinstance(window_cert, dict) else {}
    )
    pendings = (operational or {}).get("pendings", {}) if isinstance(operational, dict) else {}
    return {
        "artifacts": {
            "v2_98": {
                "path": str(paths["window"]),
                "exists": paths["window"].is_file(),
                "sha256": sha256_file(paths["window"]),
            },
            "paper_cycles_export": {
                "path": str(paths["cycles"]),
                "exists": paths["cycles"].is_file(),
                "size": paths["cycles"].stat().st_size if paths["cycles"].is_file() else None,
                "sha256": sha256_file(paths["cycles"]),
                "exitCode": cycle_export_exit,
                "note": (
                    "exit 2 = BLOQUEADO: el exportador no emite un JSON vacio como si fuera una "
                    "medicion. 'No medido' se declara por stderr; el fichero de stdout queda vacio "
                    "a proposito y NO es un resultado."
                    if cycle_export_exit == 2
                    else None
                ),
            },
            "v2_100": {
                "path": str(paths["operational"]),
                "exists": paths["operational"].is_file(),
                "sha256": sha256_file(paths["operational"]),
            },
            "stderr_cycles": {
                "path": str(paths["cycles_stderr"]),
                "exists": paths["cycles_stderr"].is_file(),
                "sha256": sha256_file(paths["cycles_stderr"]),
            },
        },
        "v2_98": {
            "verdict": cert_block.get("verdict"),
            "days": cert_block.get("days"),
            "episodes": cert_block.get("episodes"),
            "measurableCycles": cert_block.get("measurableCycles"),
            "ready": cert_block.get("ready"),
            "missingCriterionIds": cert_block.get("missingCriterionIds"),
            "dayList": cert_block.get("dayList"),
            "thresholds": cert_block.get("thresholds"),
        },
        "paper_cycles_export": {
            "material": (
                {
                    "cycles": len(cycles_json.get("cycles") or []),
                    "manifest": cycles_json.get("material_manifest"),
                }
                if isinstance(cycles_json, dict)
                else None
            ),
            "blocked": cycle_export_exit == 2,
        },
        "v2_100": {
            "closedPendings": (operational or {}).get("closedPendings"),
            "openPendings": (operational or {}).get("openPendings"),
            "P1": pendings.get("P1"),
            "P2": pendings.get("P2"),
            "P3": pendings.get("P3"),
            "P4": pendings.get("P4"),
        },
        "note": (
            "Los tres instrumentos leen HECHOS DURABLES: su veredicto no depende de que exista "
            "forward.json. Ningun umbral se toca."
        ),
    }


def _window_provenance_check(forward_json: Any, run_copy_sha: str | None) -> bool | None:
    """El `window.json` del dia debe coincidir con el hash que declara el forward."""
    if not isinstance(forward_json, dict) or not run_copy_sha:
        return None
    provenance = forward_json.get("windowProvenance")
    declared = provenance.get("windowJsonSha256") if isinstance(provenance, dict) else None
    if not declared:
        return None
    return declared == run_copy_sha


def _gate(
    forward_json: Any, manifest: Any, lock: dict[str, Any] | None, snapshot: bool
) -> dict[str, Any]:
    manifest_meta = manifest if isinstance(manifest, dict) else {}
    manifest_start = _dt(manifest_meta.get("startedAt"))
    lock_start = _dt((lock or {}).get("startedAt"))
    stale_manifest = bool(manifest_start and lock_start and manifest_start < lock_start)
    meta = {
        "manifestStatus": manifest_meta.get("status"),
        "manifestReason": manifest_meta.get("reason"),
        "manifestStartedAt": manifest_meta.get("startedAt"),
        "manifestFinishedAt": manifest_meta.get("finishedAt"),
        "manifestDescribesThisRun": (not stale_manifest) if manifest_start else None,
        "manifestNote": (
            "El manifest del directorio describe el intento ABORTADO (anterior al lock de esta "
            "corrida); no es el resultado de la corrida viva. Se reescribe al cerrar."
            if stale_manifest
            else "El manifest corresponde al arranque de esta corrida."
        ),
    }
    if not isinstance(forward_json, dict):
        return {
            "available": False,
            "reason": "forward.json aun no escrito"
            + (" (corrida viva: snapshot)" if snapshot else ""),
            "stopReason": None,
            "ticksReported": None,
            "turnTotals": None,
            "lastGateReason": None,
            "readiness": None,
            "windowProvenance": None,
            **meta,
        }
    return {
        "available": True,
        "stopReason": forward_json.get("stopReason"),
        "ticksReported": forward_json.get("ticks"),
        "turnTotals": forward_json.get("turnTotals"),
        "lastGateReason": forward_json.get("lastGateReason"),
        "priceSources": forward_json.get("priceSources"),
        "watchSource": forward_json.get("watchSource"),
        "watchSize": forward_json.get("watchSize"),
        "decided": forward_json.get("decided"),
        "readiness": forward_json.get("readiness"),
        "sample": forward_json.get("sample"),
        "windowProvenance": forward_json.get("windowProvenance"),
        **meta,
    }


def _ticks(
    reader: Reader, engine: str | None, run_start: datetime | None, snapshot: bool
) -> dict[str, Any]:
    if engine is None or run_start is None:
        return {
            "available": False,
            "reason": "sin engine_id o sin arranque de corrida (lock/forward ausente)",
        }
    aggregate = reader.guarded_one(
        "select count(*) as ticks, min(seq) as seq_min, max(seq) as seq_max,"
        " min(tick_at) as first_tick, max(tick_at) as last_tick,"
        " coalesce(sum(proposals), 0)::int as proposals,"
        " coalesce(sum(vetoes), 0)::int as vetoes,"
        " count(*) filter (where activity = 'NO_ACTIVITY') as no_activity"
        " from auto_engine_ticks where engine_id = %s and tick_at >= %s",
        (engine, run_start),
    )
    return {
        "available": True,
        "engineId": engine,
        "runStart": run_start.strftime(_ISO),
        "snapshot": snapshot,
        "aggregate": aggregate,
        "note": (
            "Contador del LEDGER durable (auto_engine_ticks), no el contador del bucle del runner. "
            "Un tick sin turno (sin precio de ejecucion) tambien es una ejecucion del motor: "
            "activity=ANALYZING con vetoes=0 es un tick RECORRIDO que no decidio ningun simbolo."
        ),
    }


def _bar_frontier(
    reader: Reader,
    engine: str | None,
    run_start: datetime | None,
    day_date: date,
    snapshot: bool,
) -> dict[str, Any]:
    if engine is None or run_start is None:
        return {"available": False, "reason": "sin engine_id o sin arranque de corrida"}
    midnight = datetime.combine(day_date + timedelta(days=1), time.min, tzinfo=UTC)
    with_bar = _segment(reader, engine, run_start, midnight) if run_start < midnight else None
    blind_start = max(run_start, midnight)
    blind = _segment(reader, engine, blind_start, None)
    return {
        "available": True,
        "engineId": engine,
        "frontierUtc": midnight.strftime(_ISO),
        "withBar": with_bar,
        "blind": blind,
        "note": (
            "withBar = ticks con la barra del dia corriente disponible (antes de medianoche UTC). "
            "blind = ticks posteriores: sin sesion/barra, el contrato fail-closed del precio deja "
            "el bucle recorrido y sin decisiones. El tramo ciego NO cuenta como medido."
            + (
                " Corrida viva: el tramo ciego puede seguir creciendo hasta el cierre."
                if snapshot
                else ""
            )
        ),
    }


def _bar_coverage(
    reader: Reader,
    day_date: date,
    watch_size: int | None,
    run_start: datetime | None,
    frontier: datetime | None,
    blind_start: datetime | None,
) -> dict[str, Any]:
    by_timeframe = reader.guarded(
        "select timeframe, count(distinct instrument_id) as instruments"
        " from ohlcv_bars where timestamp::date = %s group by timeframe order by timeframe",
        (day_date,),
    )
    totals = reader.guarded_one(
        "select count(*) as instruments, count(*) filter (where is_active) as active from instruments"
    )
    list_members = reader.guarded_one(
        "select count(distinct instrument_id) as instruments from instrument_list_items"
    )
    intersection = reader.guarded_one(
        "select count(*) as with_bar_in_lists from ("
        " select distinct b.instrument_id from ohlcv_bars b"
        " where b.timeframe = '1d' and b.timestamp::date = %s"
        " intersect select distinct i.instrument_id from instrument_list_items i) x",
        (day_date,),
    )
    bars_without_list = reader.guarded_one(
        "select count(*) as with_bar_outside_lists from ("
        " select distinct b.instrument_id from ohlcv_bars b"
        " where b.timeframe = '1d' and b.timestamp::date = %s"
        " except select distinct i.instrument_id from instrument_list_items i) x",
        (day_date,),
    )
    list_without_bar = reader.guarded_one(
        "select count(*) as in_lists_without_bar from ("
        " select distinct i.instrument_id from instrument_list_items i"
        " except select distinct b.instrument_id from ohlcv_bars b"
        " where b.timeframe = '1d' and b.timestamp::date = %s) x",
        (day_date,),
    )
    bars_today = reader.guarded_one(
        "select count(distinct instrument_id) as instruments from ohlcv_bars"
        " where timeframe = '1d' and timestamp::date = %s",
        (day_date,),
    )
    bars_next_day = reader.guarded_one(
        "select count(distinct instrument_id) as instruments from ohlcv_bars"
        " where timeframe = '1d' and timestamp::date = %s",
        (day_date + timedelta(days=1),),
    )
    bars_at_run_start = (
        reader.guarded_one(
            "select count(distinct instrument_id) as instruments from ohlcv_bars"
            " where timeframe = '1d' and timestamp::date = %s and created_at <= %s",
            (day_date, run_start),
        )
        if run_start
        else None
    )
    bars_at_frontier = (
        reader.guarded_one(
            "select count(distinct instrument_id) as instruments from ohlcv_bars"
            " where timeframe = '1d' and timestamp::date = %s and created_at < %s",
            (day_date, frontier),
        )
        if frontier
        else None
    )
    ingest_timeline = reader.guarded(
        "select date_trunc('hour', created_at) as hour, count(*) as bars"
        " from ohlcv_bars where timeframe = '1d' and timestamp::date = %s"
        " group by 1 order by 1",
        (day_date,),
    )
    bars_at_blind_start = (
        reader.guarded_one(
            "select count(distinct instrument_id) as instruments from ohlcv_bars"
            " where timeframe = '1d' and timestamp::date = %s and created_at <= %s",
            (day_date, blind_start),
        )
        if blind_start
        else None
    )
    return {
        "day": day_date.isoformat(),
        "byTimeframe": by_timeframe,
        "barsWithDay": bars_today,
        "barsAtRunStart": bars_at_run_start,
        "barsAtFrontier": bars_at_frontier,
        "barsAtBlindStart": bars_at_blind_start,
        "barsForNextDay": bars_next_day,
        "ingestTimeline": ingest_timeline,
        "catalog": totals,
        "listMembers": list_members,
        "intersection": intersection,
        "barsOutsideLists": bars_without_list,
        "listsWithoutBar": list_without_bar,
        "watchSizeConfigured": watch_size,
        "note": (
            "Cobertura de la BARRA del dia frente al catalogo y frente a las listas. "
            "barsAtRunStart/barsAtFrontier miden lo que habia INGERIDO al arrancar y en la frontera "
            "de medianoche: la cobertura del tramo con barra es esa, no la de hoy. barsForNextDay "
            "prueba si existe barra del dia corriente del motor tras la frontera. La cola de ingesta "
            "usa scope=lists: un instrumento fuera de lista no se encola nunca, asi que un objetivo "
            "igual al catalogo es inalcanzable por diseno. Este denominador NO es intercambiable con "
            "la cobertura OPERATIVA del preflight (60/80) ni con el watch del forward, que sale del "
            "universo ESTUDIO y no queda persistido por tick: la cobertura del watch NO se deriva "
            "de aqui."
        ),
    }


def _material(
    reader: Reader, day_iso: str, account: str | None, engine: str | None
) -> dict[str, Any]:
    fills = reader.guarded(
        "select f.execution_id, f.instrument_id, i.symbol, f.side, f.quantity, f.price,"
        " f.price_source, f.cycle_id, f.venue, f.strategy_version_id, f.created_at"
        " from sim_fill_finance_context f left join instruments i on i.id = f.instrument_id"
        " where f.created_at::date = %s order by f.created_at",
        (day_iso,),
    )
    reservations = reader.guarded(
        "select reservation_id, instrument_id, side, status, release_reason, tick_id,"
        " cycle_id, exit_order_id, created_at, released_at"
        " from portfolio_reservations"
        " where created_at::date = %s or released_at::date = %s"
        " order by created_at",
        (day_iso, day_iso),
    )
    positions = reader.guarded(
        "select symbol, quantity, entry_price, stop_price, position_state, t1_state,"
        " trailing_state, updated_at from sim_auto_positions"
        " where account_id = %s and engine_id = %s order by symbol",
        (account, engine),
    )
    exit_orders = reader.guarded(
        "select exit_order_id, instrument_id, state, reason, requested_qty, filled_qty,"
        " remaining_qty, cycle_id, created_at from auto_exit_orders"
        " where created_at::date = %s order by created_at",
        (day_iso,),
    )
    totals = reader.guarded_one(
        "select"
        " (select count(*) from sim_fill_finance_context where created_at::date = %s) as fills,"
        " (select count(*) from portfolio_reservations"
        "   where created_at::date = %s) as reservations_created,"
        " (select count(*) from auto_exit_orders where created_at::date = %s) as exit_orders,"
        " (select count(*) from sim_auto_positions"
        "   where account_id = %s and engine_id = %s) as open_positions_of_engine",
        (day_iso, day_iso, day_iso, account, engine),
    )
    return {
        "account": account,
        "engineId": engine,
        "totals": totals,
        "fills": fills,
        "reservations": reservations,
        "positions": positions,
        "exitOrders": exit_orders,
        "note": (
            "Un fill NO es una operacion cerrada: el ciclo nace al cerrarse la posicion completa. "
            "Las reservas son upsert por identidad de decision, asi que la tabla no conserva los "
            "reintentos cancelados de la misma decision. Las posiciones se acotan a la cuenta y al "
            "motor de la ventana: el catalogo de posiciones de la base no es material de esta corrida."
        ),
    }


def _cycles(reader: Reader, day_iso: str) -> dict[str, Any]:
    forward_results = reader.guarded(
        "select id, version_id, instrument_id, trades, round_trips, fills, return_pct,"
        " max_drawdown_pct, win_rate, passed, as_of, created_at"
        " from paper_forward_results where created_at::date = %s order by created_at",
        (day_iso,),
    )
    total = reader.guarded_one("select count(*) as total from paper_forward_results")
    fills_with_cycle = reader.guarded_one(
        "select count(*) as fills, count(*) filter (where cycle_id is not null) as with_cycle"
        " from sim_fill_finance_context where created_at::date = %s",
        (day_iso,),
    )
    reservations_with_cycle = reader.guarded_one(
        "select count(*) as reservations, count(*) filter (where cycle_id is not null) as with_cycle"
        " from portfolio_reservations where created_at::date = %s",
        (day_iso,),
    )
    return {
        "forwardResultsDay": forward_results,
        "forwardResultsTotal": total,
        "fillLineage": fills_with_cycle,
        "reservationLineage": reservations_with_cycle,
        "gateThresholds": {
            "minCyclesPerStrategy": 32,
            "minDays": 4,
            "minEpisodes": 2,
            "note": "Umbrales declarados del gate ADR-046: no se bajan ni se reinterpretan.",
        },
    }


def _fmt(value: Any) -> str:
    """Render legible de un valor del paquete (fechas ISO, nulos declarados)."""
    if value is None:
        return "null"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}={_fmt(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(item) for item in value) + "]"
    return str(value)


def _segment_line(label: str, segment: dict[str, Any] | None) -> str:
    if not segment:
        return f"- {label}: sin ticks"
    agg = segment.get("aggregate")
    if not isinstance(agg, dict):
        return f"- {label}: NO MEDIDO ({_fmt(agg)})"
    reasons = segment.get("by_reason")
    return (
        f"- {label}: {agg.get('ticks')} ticks (seq {agg.get('seq_min')}-{agg.get('seq_max')}, "
        f"{_fmt(agg.get('first_tick'))} -> {_fmt(agg.get('last_tick'))}), "
        f"proposals={agg.get('proposals')}, vetoes={agg.get('vetoes')}, "
        f"ticks con veto={agg.get('ticks_with_vetoes')}, NO_ACTIVITY={agg.get('no_activity')}, "
        f"motivos={_fmt(reasons)}"
    )


def _summary(bundle: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add(f"# Paquete de cierre · dia {bundle['day']} ({bundle['mode']})")
    add(f"generado: {bundle['generatedAt']}")
    add("")
    artifacts = bundle["artifacts"]
    gate = bundle["gate"]

    add("## 1. Ticks efectivos")
    ticks = bundle["ticks"]
    if not ticks.get("available"):
        add(f"- NO MEDIDO: {ticks.get('reason')}")
    else:
        agg = ticks.get("aggregate")
        if isinstance(agg, dict):
            add(
                f"- motor `{ticks['engineId']}` desde {ticks['runStart']}: "
                f"{agg.get('ticks')} ticks (seq {agg.get('seq_min')}-{agg.get('seq_max')}, "
                f"{_fmt(agg.get('first_tick'))} -> {_fmt(agg.get('last_tick'))}), "
                f"proposals={agg.get('proposals')}, vetoes={agg.get('vetoes')}, "
                f"NO_ACTIVITY={agg.get('no_activity')}"
            )
        else:
            add(f"- agregado no legible: {_fmt(agg)}")
    add(
        f"- contador del runner: {_fmt(gate.get('ticksReported'))} ticks, "
        f"stopReason={_fmt(gate.get('stopReason'))}, manifest={_fmt(gate.get('manifestStatus'))}"
    )
    add(f"- manifest describe esta corrida: {_fmt(gate.get('manifestDescribesThisRun'))}")
    if gate.get("manifestNote"):
        add(f"- nota del manifest: {gate['manifestNote']}")
    add("")

    add("## 2. Frontera de barra")
    frontier = bundle["bar_frontier"]
    if not frontier.get("available"):
        add(f"- NO MEDIDO: {frontier.get('reason')}")
    else:
        add(f"- frontera: {frontier.get('frontierUtc')}")
        add(_segment_line("withBar", frontier.get("withBar")))
        add(_segment_line("blind", frontier.get("blind")))
        add(f"- {frontier.get('note')}")
    add("")

    add("## 3. Cobertura de la barra")
    coverage = bundle["bar_coverage"]
    add(f"- barra del dia: {_fmt(coverage.get('barsWithDay'))} instrumentos (medido ahora)")
    add(f"- barra al ARRANCAR la corrida: {_fmt(coverage.get('barsAtRunStart'))}")
    add(f"- barra en la FRONTERA de medianoche: {_fmt(coverage.get('barsAtFrontier'))}")
    add(f"- barra al primer tick CIEGO: {_fmt(coverage.get('barsAtBlindStart'))}")
    add(f"- barra del dia siguiente (B del tramo ciego): {_fmt(coverage.get('barsForNextDay'))}")
    add(f"- ingesta de la barra del dia por hora: {_fmt(coverage.get('ingestTimeline'))}")
    add(f"- por timeframe: {_fmt(coverage.get('byTimeframe'))}")
    add(f"- catalogo: {_fmt(coverage.get('catalog'))}")
    add(f"- miembros de lista: {_fmt(coverage.get('listMembers'))}")
    add(f"- barra dentro de listas: {_fmt(coverage.get('intersection'))}")
    add(f"- barra fuera de listas: {_fmt(coverage.get('barsOutsideLists'))}")
    add(f"- listas sin barra: {_fmt(coverage.get('listsWithoutBar'))}")
    add(
        f"- watch configurado: {_fmt(coverage.get('watchSizeConfigured'))} "
        f"(no determina la cobertura)"
    )
    add(f"- {coverage.get('note')}")
    add("")

    add("## 4. Material durable")
    material = bundle["material"]
    add(f"- cuenta: {_fmt(material.get('account'))} · motor: {_fmt(material.get('engineId'))}")
    add(f"- totales: {_fmt(material.get('totals'))}")
    fills = material.get("fills")
    if isinstance(fills, list):
        add(f"- fills con identificador ({len(fills)}):")
        for fill in fills:
            add(
                f"  - {_fmt(fill.get('execution_id'))} · {_fmt(fill.get('symbol'))} · "
                f"{_fmt(fill.get('side'))} · qty={_fmt(fill.get('quantity'))} · "
                f"px={_fmt(fill.get('price'))} · source={_fmt(fill.get('price_source'))} · "
                f"cycle={_fmt(fill.get('cycle_id'))} · {_fmt(fill.get('created_at'))}"
            )
    else:
        add(f"- fills: NO MEDIDO ({_fmt(fills)})")
    reservations = material.get("reservations")
    if isinstance(reservations, list):
        add(f"- reservas ({len(reservations)}):")
        for reservation in reservations:
            add(
                f"  - {_fmt(reservation.get('reservation_id'))} · "
                f"{_fmt(reservation.get('status'))}/{_fmt(reservation.get('release_reason'))} · "
                f"cycle={_fmt(reservation.get('cycle_id'))} · "
                f"tick={_fmt(reservation.get('tick_id'))}"
            )
    else:
        add(f"- reservas: NO MEDIDO ({_fmt(reservations)})")
    positions = material.get("positions")
    add(
        f"- posiciones abiertas del motor: "
        f"{len(positions) if isinstance(positions, list) else _fmt(positions)}"
    )
    add(f"- ordenes de salida del dia: {_fmt(material.get('exitOrders'))}")
    add(f"- {material.get('note')}")
    add("")

    add("## 5. Ciclos cerrados")
    cycles = bundle["cycles"]
    results = cycles.get("forwardResultsDay")
    add(
        f"- paper_forward_results del dia: "
        f"{len(results) if isinstance(results, list) else _fmt(results)}"
    )
    add(f"- paper_forward_results total: {_fmt(cycles.get('forwardResultsTotal'))}")
    add(f"- linaje fills: {_fmt(cycles.get('fillLineage'))}")
    add(f"- linaje reservas: {_fmt(cycles.get('reservationLineage'))}")
    add(f"- umbrales: {_fmt(cycles.get('gateThresholds'))}")
    add("")

    add("## 6. Atestacion del arbol")
    attestation = bundle["attestation"]
    add(f"- version: {_fmt(attestation.get('packageVersion'))}")
    add(f"- alembic: {_fmt(attestation.get('alembic'))}")
    add(f"- git: {_fmt(attestation.get('git'))}")
    add(f"- pin: {_fmt(attestation.get('pin'))}")
    add(f"- comprobaciones: {_fmt(attestation.get('checks'))}")
    hashes = {
        key: value.get("sha256")
        for key, value in artifacts.items()
        if isinstance(value, dict) and "sha256" in value
    }
    add(f"- hashes: {_fmt(hashes)}")
    add(f"- intento abortado: {_fmt(artifacts.get('aborted_attempt'))}")
    add(f"- {attestation.get('freezeRule')}")
    add("")

    add("## 7. Gate y certificacion")
    add(f"- forward.json disponible: {_fmt(gate.get('available'))}")
    if gate.get("reason"):
        add(f"- motivo: {gate.get('reason')}")
    add(f"- readiness: {_fmt(gate.get('readiness'))}")
    add(f"- turnTotals: {_fmt(gate.get('turnTotals'))}")
    add(f"- lastGateReason: {_fmt(gate.get('lastGateReason'))}")
    add(f"- priceSources: {_fmt(gate.get('priceSources'))}")
    add(f"- windowProvenance: {_fmt(gate.get('windowProvenance'))}")
    add("")

    termination = bundle["termination"]
    add("## 8. Como termino la corrida")
    add(f"- estado: **{_fmt(termination.get('status'))}**")
    add(f"- {termination.get('reading')}")
    add(f"- ticks observados: {_fmt(termination.get('ticksObserved'))}")
    add(f"- ticks esperados: {_fmt(termination.get('ticksExpected'))}")
    add(f"- ticks faltantes: {_fmt(termination.get('ticksMissing'))}")
    add(f"- lock: {_fmt(termination.get('lock'))}")
    add(f"- PID del lock vivo: {_fmt(termination.get('lockPidAlive'))}")
    add(f"- fila final en el ledger: {_fmt(termination.get('hasFinalLedgerRow'))}")
    add(f"- {termination.get('note')}")
    add("")

    certification = bundle["certification"]
    add("## 9. Certificacion (hechos durables)")
    add(f"- v2_98: {_fmt(certification.get('v2_98'))}")
    add(f"- paper_cycles_export: {_fmt(certification.get('paper_cycles_export'))}")
    add(f"- v2_100: {_fmt(certification.get('v2_100'))}")
    add(f"- artefactos: {_fmt(certification.get('artifacts'))}")
    add(f"- {certification.get('note')}")
    add("")

    window_days = bundle["windowDays"]
    add("## 10. Que dias cuenta el gate como ventana")
    for row in window_days.get("days") or []:
        add(
            f"- {row.get('day')}: barra={_fmt(row.get('barsForDay'))}, fills={_fmt(row.get('fills'))},"
            f" ticks={_fmt(row.get('ticks'))}, motivos={_fmt(row.get('tickReasons'))}"
        )
    add(f"- {window_days.get('source')}")
    add("")

    add("## Ledger del dia (todas las filas, sin colapsar)")
    for row in bundle["ledger"]:
        add(
            f"- {_fmt(row.get('startedAt'))} -> {_fmt(row.get('finishedAt'))} · "
            f"{_fmt(row.get('status'))} · {_fmt(row.get('reason'))} · "
            f"freeze={_fmt(row.get('freeze'))}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", required=True, help="dia de la ventana (YYYYMMDD)")
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="permite emitir el paquete con la corrida viva (artefactos ausentes = null)",
    )
    parser.add_argument("--json-out", default=None, help="ruta del JSON de salida")
    parser.add_argument("--md-out", default=None, help="ruta del resumen legible (markdown)")
    parser.add_argument(
        "--expected-ticks",
        type=int,
        default=None,
        help="tope de ticks con el que se lanzo la corrida (no queda en el lock: se declara)",
    )
    parser.add_argument(
        "--cycles-export-exit",
        type=int,
        default=None,
        help="codigo de salida de paper_cycles_export.py (2 = BLOQUEADO sin material)",
    )
    parser.add_argument(
        "--declare-termination",
        action="store_true",
        help=(
            "permite el paquete definitivo SIN forward.json cuando la corrida termino antes de "
            "finalizar; el bloque termination lo declara y el paquete no finge un cierre normal"
        ),
    )
    args = parser.parse_args()

    try:
        bundle = build(args.day, args.snapshot, args.expected_ticks, args.cycles_export_exit)
    except Exception as exc:  # noqa: BLE001 - se declara por stderr
        return _die(str(exc))

    default_name = (
        f"package-{args.day}.snapshot.json" if args.snapshot else f"package-{args.day}.json"
    )
    out = Path(args.json_out) if args.json_out else ROOT / "operability_runs" / default_name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    summary = _summary(bundle)
    if args.md_out:
        md = Path(args.md_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(summary + "\n", encoding="utf-8")
    print(summary)
    print(f"\n[package] escrito en {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")

    if args.snapshot:
        return 0
    termination = bundle.get("termination") or {}
    if not bundle["artifacts"]["forward"]["exists"]:
        if termination.get("status") == "PREMATURE_TERMINATION" and args.declare_termination:
            print(
                "# DECLARADO: paquete definitivo sin forward.json; la corrida termino antes de "
                "finalizar (ver bloque termination)",
                file=sys.stderr,
            )
            return 0
        return _die(
            "forward.json no existe y el paquete definitivo lo exige "
            "(si la corrida termino antes, declaralo con --declare-termination)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
