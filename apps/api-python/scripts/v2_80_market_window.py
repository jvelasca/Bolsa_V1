#!/usr/bin/env python3
"""V2.80 · AUTO-MATERIAL-8 — AUTO MARKET WINDOW (serie diaria de la ventana de operación).

Qué resuelve: la auditoría de ``v2.79`` cerró la instrumentación del censo, pero la pregunta que
decide el siguiente paso —**¿por qué el AUTO opera o no opera, y cuánto material genera?**— exige
una **ventana real de mercado** (>=4 dias). Esta herramienta construye esa serie diaria leyendo el
**journal durable** y el material de riesgo por ciclo, con el linaje (``account``, ``instrument``,
``strategy_version``, ``cycle_id``) que permite reconstruir cada día.

No decide nada: es **READ-ONLY**. NO escribe en el journal durable, NO abre el motor, NO recalcula
el gate y NO cambia un umbral. Reutiliza la MISMA puerta del censo que ``market_operability``
(``collect_journal_reasons`` / ``split_journal_reasons`` / ``classify_veto_reasons``) y el MISMO R
que el informe (``measured_r``). Escribe SOLO su propio journal (JSONL, directorio no versionado);
nunca ``evidence_runs/`` ni ``evidence_validations/``.

Desde ``v2.81`` (``AUTO-MATERIAL-9``) la misma corrida publica además el **funnel de operabilidad**
(``--render``), el ``unresolved_age`` y un **informe HTML** autocontenido; ``--forward`` (OPCIONAL,
read-only) enriquece el funnel con el universo/dato/régimen/órdenes del runner y el par A/B.

Uso (desde la raíz del repo)::

    # Serie de los últimos 4 días + informe HTML (artefacto de la ventana):
    BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py \\
        --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --days 4 --render \\
        --forward 'operability_runs/forward-market-*.json' \\
        --out operability_runs/operability-window.json \\
        --html operability_runs/operability-window.html

    # Guardar la serie en un JSON (sin escribir el journal acumulado):
    BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_80_market_window.py \\
        --account-id "$ACCOUNT" --strategy-version "$VERSION_A" --json --no-write \\
        --out operability_runs/window-$(date +%Y%m%d).json

Códigos de salida: ``0`` si se leyó al menos un día; ``2`` si no hay ningún día que leer (se
declara por stderr); ``1`` uso incorrecto.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_DOTENV = _ROOT / ".env"
_DEFAULT_JOURNAL = _ROOT / "operability_runs" / "window.jsonl"
_DEFAULT_HTML = _ROOT / "operability_runs" / "operability-window.html"


def _die(message: str, code: int = 2) -> int:
    print(f"# BLOQUEADO: {message}", file=sys.stderr)
    return code


def _day_of(value: Any) -> str:
    """Día ISO (``YYYY-MM-DD``) de un instante durable, o ``""`` si no es legible (no se adivina)."""
    if isinstance(value, datetime):
        return (value.astimezone(UTC) if value.tzinfo else value).date().isoformat()
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else ""


def _since_day(args: argparse.Namespace) -> str | None:
    if args.since:
        return str(args.since)[:10]
    if args.days:
        return (datetime.now(UTC) - timedelta(days=int(args.days))).date().isoformat()
    return None


def _evidence_day(path: Path, evidence: dict[str, Any]) -> str:
    """Día de la evidencia del runner, declarado (nunca se adivina): campo o nombre del fichero."""
    for field in ("day", "asOf", "date"):
        value = str(evidence.get(field) or "").strip()
        if value:
            return value[:10]
    digits = "".join(ch if ch.isdigit() else " " for ch in path.stem).split()
    for token in digits:
        if len(token) == 8:  # YYYYMMDD
            return f"{token[:4]}-{token[4:6]}-{token[6:]}"
    return ""


def _load_evidence(patterns: list[str]) -> dict[str, dict[str, Any]]:
    """Evidencia del runner por día (``--forward``, OPCIONAL y read-only). Sin campo de día, se omite."""
    by_day: dict[str, dict[str, Any]] = {}
    for pattern in patterns:
        for match in sorted(glob.glob(str(pattern), recursive=True)):
            path = Path(match)
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                print(f"  !! evidencia ilegible {path}; se omite", file=sys.stderr)
                continue
            if not isinstance(payload, dict):
                continue
            day = _evidence_day(path, payload)
            if day:
                by_day.setdefault(day, payload)
    return by_day


async def _read_journal(repository: Any, account_id: str, since: str | None) -> list[Any]:
    """Todas las entradas del journal de la cuenta (paginado). El día se filtra después."""
    rows: list[Any] = []
    offset = 0
    page = 500
    while True:
        batch, total = await repository.list_entries(
            account_id=account_id, since=since, limit=page, offset=offset
        )
        rows.extend(batch)
        if not batch or len(rows) >= int(total):
            break
        offset += page
    return rows


async def _collect(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.auto_cycle_regime_reader import read_cycle_regimes
    from bolsa_application.auto_paper_material import read_all_reservations
    from bolsa_application.auto_self_evaluation_feed import adaptive_instrument_cycles
    from bolsa_application.cycle_risk import cycle_risk_from_reservations
    from bolsa_application.operability_window import build_window_row, window_gate
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    # Misma guarda de procedencia que el instrumento: una ventana PAPER no se lee de otra venue.
    if str(settings.broker_venue).strip().lower() != "paper":
        raise RuntimeError(
            f"venue '{settings.broker_venue}' no es PAPER: la ventana se mide sobre material PAPER"
        )

    versions = [str(v).strip() for v in (args.strategy_version or []) if str(v).strip()]
    if not versions:
        raise RuntimeError("sin --strategy-version no hay material que leer")
    account_id = str(args.account_id)
    since_day = _since_day(args)
    since_ts = f"{since_day}T00:00:00Z" if since_day else None
    captured_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

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
            cycle_ids = sorted(
                {str(fill.cycle_id).strip() for fill in fills if str(fill.cycle_id or "").strip()}
            )
            reservations, saturated = await read_all_reservations(
                reservation_store, account_id, cycle_ids, page_size=max(1, int(args.limit))
            )
            reading = await read_cycle_regimes(repository.list_by_decision_ids, cycle_ids)
            cycle_risk = cycle_risk_from_reservations(
                cycle_ids,
                reservations,
                regime_by_cycle=dict(reading.regime_by_cycle),
                regime_source_durable=True,
            )
            cycles = adaptive_instrument_cycles(fills, cycle_risk)
            journal = await _read_journal(repository, account_id, since_ts)
    finally:
        await engine.dispose()

    from bolsa_analytics.cognitive.auto_adaptive_confidence import closed_instant

    fills_by_day: dict[str, list[Any]] = {}
    for fill in fills:
        day = _day_of(getattr(fill, "created_at", None))
        if day:
            fills_by_day.setdefault(day, []).append(fill)
    cycles_by_day: dict[str, list[Any]] = {}
    undated_cycles = 0
    for row in cycles:
        day = _day_of(closed_instant(row))
        if day:
            cycles_by_day.setdefault(day, []).append(row)
        else:
            undated_cycles += 1
    journal_by_day: dict[str, list[Any]] = {}
    for record in journal:
        day = _day_of(getattr(record, "created_at", None))
        if day:
            journal_by_day.setdefault(day, []).append(record)

    days = sorted(set(fills_by_day) | set(cycles_by_day) | set(journal_by_day))
    if since_day:
        days = [day for day in days if day >= since_day]

    # Evidencia del runner (OPCIONAL, read-only): enriquece el funnel y el par A/B del día.
    evidence_by_day = _load_evidence(list(args.forward or []))

    rows: list[dict[str, Any]] = []
    for day in days:
        day_fills = fills_by_day.get(day, [])
        day_cycles = cycles_by_day.get(day, [])
        instruments = {str(getattr(fill, "instrument_id", "") or "") for fill in day_fills}
        rows.append(
            build_window_row(
                day,
                account=account_id,
                entries=journal_by_day.get(day, []),
                cycles=day_cycles,
                fills=len(day_fills),
                versions=versions,
                instruments=[name for name in instruments if name],
                captured_at=captured_at,
                evidence=evidence_by_day.get(day),
            )
        )

    header = {
        "capturedAt": captured_at,
        "account": account_id,
        "versions": versions,
        "sinceDay": since_day,
        "fillsRead": len(fills),
        "cyclesRead": len(cycles),
        "cycleIds": cycle_ids,
        "reservationsRead": len(reservations),
        "reservationsSaturated": saturated,
        "regimeConfirmed": reading.confirmed,
        "regimeGaps": len(reading.absent) + len(reading.unconfirmed) + len(reading.not_derivable),
        "journalEntriesRead": len(journal),
        "undatedCycles": undated_cycles,
        "evidenceDays": sorted(evidence_by_day),
    }
    return rows, {"header": header, "gate": window_gate(rows)}


def _render(rows: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    from bolsa_application.operability_window import render_window_series

    header = meta["header"]
    gate = meta["gate"]
    print("AUTO MARKET WINDOW (V2.81 · AUTO-MATERIAL-9) — read-only, sin PostgreSQL de escritura")
    print("=" * 92)
    print(
        f"cuenta {header['account']}  ·  versiones {', '.join(header['versions']) or '(ninguna)'}"
        f"  ·  capturado {header['capturedAt']}"
    )
    print(
        f"fills leidos {header['fillsRead']}  ·  ciclos {header['cyclesRead']}"
        f"  ·  reservas {header['reservationsRead']}"
        f"{' (SATURADO: lectura incompleta)' if header['reservationsSaturated'] else ''}"
        f"  ·  entradas de journal {header['journalEntriesRead']}"
        f"  ·  evidencia (--forward) dias {len(header.get('evidenceDays') or [])}"
    )
    print("")
    print(render_window_series(rows))
    print("")
    print("GATE DE LA VENTANA (>= 4 dias, >= 2 episodios de regimen, >= 32 ciclos medibles):")
    print(
        f"  dias={gate['days']}/{gate['minDays']}  episodios={gate['episodes']}/{gate['minEpisodes']}"
        f"  ciclos={gate['cycles']}/{gate['minCycles']}  =>  {gate['verdict']}"
    )
    if not gate["ready"]:
        print("  (INCONCLUSIVE / NO MEDIDO: la ventana aun no acredita diversidad de mercado)")
    print("")
    print("Nota: ENTRY = decisiones de entrada; VETOS = vetos PUROS; FILLS/CYCLES del material durable.")
    print("      eventos/posicion NO son vetos; other>0 es una violacion de contrato (ALERTA).")


def _write_out(path: Path, rows: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "rows": rows}
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )


def _write_html(path: Path, rows: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    from bolsa_application.operability_window import render_window_html

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_window_html(rows, meta) + "\n", encoding="utf-8")


def _append_journal(path: Path, rows: list[dict[str, Any]]) -> int:
    """Añade las filas nuevas (por día+cuenta+versiones) al journal acumulado, sin duplicar."""
    existing: set[tuple[str, ...]] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                record = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                existing.add(_identity(record))
    fresh = [row for row in rows if _identity(row) not in existing]
    if not fresh:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for row in fresh:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")
    return len(fresh)


def _identity(row: dict[str, Any]) -> tuple[str, ...]:
    versions = ",".join(str(v) for v in (row.get("versions") or []))
    return (
        str(row.get("day") or ""),
        str(row.get("account") or ""),
        versions,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, help="cuenta PAPER de la ventana")
    parser.add_argument(
        "--strategy-version",
        action="append",
        default=None,
        required=True,
        metavar="VERSION",
        help="versión de estrategia del material (repetible: una por estrategia del par A/B)",
    )
    parser.add_argument("--days", type=int, default=None, help="ventana de los últimos N días")
    parser.add_argument("--since", default=None, help="día ISO desde el que leer (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=2000, help="tamaño de página de las lecturas")
    parser.add_argument(
        "--journal",
        default=str(_DEFAULT_JOURNAL),
        help="journal JSONL acumulado (por defecto operability_runs/window.jsonl, no versionado)",
    )
    parser.add_argument("--out", default=None, help="escribe la serie completa en este JSON")
    parser.add_argument(
        "--forward",
        action="append",
        default=None,
        metavar="PATH|GLOB",
        help="JSON de evidencia del runner (repetible; admite glob). OPCIONAL: enriquece el "
        "funnel (universo/dato/régimen/órdenes) y el par A/B del día; read-only.",
    )
    parser.add_argument(
        "--html",
        default=str(_DEFAULT_HTML),
        help="informe HTML de la ventana (por defecto operability_runs/operability-window.html, "
        "no versionado); vacío para no escribirlo",
    )
    parser.add_argument("--render", action="store_true", help="publica la tabla diaria y el gate")
    parser.add_argument("--json", action="store_true", help="emite la serie como JSON por stdout")
    parser.add_argument(
        "--no-write", action="store_true", help="no escribe el journal acumulado (dry-run)"
    )
    args = parser.parse_args(argv)

    if sys.platform == "win32":  # pragma: no cover — quirk del loop psycopg en la máquina dev.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        rows, meta = asyncio.run(_collect(args))
    except Exception as error:  # noqa: BLE001 — sin lectura no hay serie: se DECLARA.
        return _die(f"no se pudo leer la ventana ({type(error).__name__}: {error})")

    if not rows:
        return _die("no hay ningún día de operabilidad que leer en la ventana")

    if args.json:
        print(json.dumps({"meta": meta, "rows": rows}, indent=2, sort_keys=True, ensure_ascii=False, default=str))
    elif args.render:
        _render(rows, meta)

    if args.out:
        _write_out(Path(args.out), rows, meta)
    if args.html:
        html_path = Path(args.html)
        if not html_path.is_absolute():
            html_path = _ROOT / html_path
        _write_html(html_path, rows, meta)
        print(f"# informe html: {html_path}", file=sys.stderr)
    if not args.no_write:
        journal_path = Path(args.journal)
        if not journal_path.is_absolute():
            journal_path = _ROOT / journal_path
        added = _append_journal(journal_path, rows)
        print(f"# journal: {added} fila(s) nueva(s) — {journal_path}", file=sys.stderr)

    violations = [row.get("day") for row in rows if bool(row.get("contractViolation"))]
    if violations:
        print(
            f"# ALERTA CONTRATO: other>0 en {', '.join(str(day) for day in violations)} "
            "(motivo(s) sin catalogar; revisar alta de reason code)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
