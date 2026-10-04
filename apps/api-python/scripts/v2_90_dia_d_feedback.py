"""V2.90 · DÍA-D AUTO — BARRIDO MULTI-DÍA del bucle de realimentación POR VALOR.

Qué es
------
Extiende el sandbox de ``v2_89`` (un día) a una **ventana** ``D0..D1``: corre el MISMO harness
hermético (``v2.86``/``v2.87``) una sola vez sobre el rango, pliega por instrumento lo que el
motor **DECLARÓ**, lo que la ventana PAPER **EJECUTÓ** (hechos durables de cada ``D``, read-only),
lo que el mercado hizo **después** (OOS real) y las incidencias de software/operativa/dato. El
resultado es el artefacto que sirve ``GET /api/auto/dia-d-feedback`` y pinta ``/auto-monitor``.

Advisory y read-only
--------------------
* **NO** cambia el motor, los umbrales, ``TOP_N``, la allocation ni los pesos A/B: es una LECTURA.
* **NO** escribe en PostgreSQL: el motor corre con stores en memoria (cuarentena). Las únicas
  lecturas son barras, sectores y los hechos durables de cada ``D``.
* Un hueco se declara ``NOT_MEASURED`` / ``None``; nunca se rellena con ``0``.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_90_dia_d_feedback.py \
        --from 2026-09-25 --to 2026-09-30 --json
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import os
import pathlib
import sys
from datetime import datetime, timedelta
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto"

logger = logging.getLogger("v2_90_dia_d_feedback")


def _load_module(filename: str, name: str) -> Any:
    """Carga un runner hermano por ruta (mismo patrón que ``v2.89``)."""
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_v89() -> Any:
    return _load_module("v2_89_dia_d_auto_replay.py", "v2_89_dia_d_auto_replay")


# ── Catálogo de errores: lecturas read-only de los hechos durables de ``D`` ──────


async def _read_day_errors(factory: Any, *, account_id: str, day: str) -> list[dict[str, Any]]:
    """Incidencias OPERATIVAS/DATA de los hechos durables de ``D`` (read-only).

    Cada familia sale del vocabulario ya existente (``auto_reason_codes`` /
    ``market_operability``): aquí solo se LEE y se atribuye. Un día sin hechos no aporta errores.
    """
    from sqlalchemy import select

    from bolsa_application.dia_d_auto_feedback import (
        error_kind_for_execution_status,
        error_kind_for_exit_state,
        error_kind_for_reason,
        normalize_error,
    )
    from bolsa_infrastructure.database.models.tables import (
        AutoExitOrderRow,
        DecisionJournalEntryRow,
        ExecutionEventRow,
        PortfolioReservationRow,
    )

    start = datetime.fromisoformat(f"{day}T00:00:00+00:00")
    end = start + timedelta(days=1)
    errors: list[dict[str, Any]] = []

    def _add(entry: dict[str, Any] | None) -> None:
        if entry is not None:
            errors.append(entry)

    async with factory() as session:
        exit_rows = (
            await session.execute(
                select(AutoExitOrderRow.instrument_id, AutoExitOrderRow.state).where(
                    AutoExitOrderRow.account_id == account_id,
                    AutoExitOrderRow.created_at >= start,
                    AutoExitOrderRow.created_at < end,
                )
            )
        ).all()
        for instrument, state in exit_rows:
            kind = error_kind_for_exit_state(state)
            if kind:
                _add(normalize_error(day=day, symbol=instrument, kind=kind, code=state))

        exec_rows = (
            await session.execute(
                select(ExecutionEventRow.status).where(
                    ExecutionEventRow.account_id == account_id,
                    ExecutionEventRow.captured_at >= start,
                    ExecutionEventRow.captured_at < end,
                )
            )
        ).all()
        for (status,) in exec_rows:
            kind = error_kind_for_execution_status(status)
            if kind:
                _add(normalize_error(day=day, kind=kind, code=status))

        reservation_rows = (
            await session.execute(
                select(PortfolioReservationRow.instrument_id, PortfolioReservationRow.status).where(
                    PortfolioReservationRow.account_id == account_id,
                    PortfolioReservationRow.created_at >= start,
                    PortfolioReservationRow.created_at < end,
                )
            )
        ).all()
        for instrument, status in reservation_rows:
            kind = error_kind_for_reason(status)
            if kind:
                _add(normalize_error(day=day, symbol=instrument, kind=kind, code=status))

        journal_rows = (
            await session.execute(
                select(DecisionJournalEntryRow.instrument_id, DecisionJournalEntryRow.payload).where(
                    DecisionJournalEntryRow.account_id == account_id,
                    DecisionJournalEntryRow.created_at >= start,
                    DecisionJournalEntryRow.created_at < end,
                )
            )
        ).all()
        for instrument, payload in journal_rows:
            reasons = (payload or {}).get("reasonCodes") if isinstance(payload, dict) else None
            for code in reasons or ():
                kind = error_kind_for_reason(code)
                if kind:
                    _add(normalize_error(day=day, symbol=instrument, kind=kind, code=code))

    return errors


async def _read_fill_counts_by_symbol(
    factory: Any, *, account_id: str, day: str
) -> dict[str, int]:
    """Fills durables de ``D`` por instrumento (read-only): la cara ejecutada del paso ``FILL``."""
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

    start = datetime.fromisoformat(f"{day}T00:00:00+00:00")
    end = start + timedelta(days=1)
    counts: dict[str, int] = {}
    async with factory() as session:
        rows = (
            await session.execute(
                select(SimFillFinanceContextRow.instrument_id).where(
                    SimFillFinanceContextRow.account_id == account_id,
                    SimFillFinanceContextRow.created_at >= start,
                    SimFillFinanceContextRow.created_at < end,
                )
            )
        ).all()
    for (instrument,) in rows:
        key = str(instrument or "").strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _fill_divergences(
    *,
    day: str,
    declared_row: dict[str, Any],
    executed_counts: dict[str, int],
) -> list[dict[str, Any]]:
    """Divergencias de SOFTWARE del paso determinista ``FILL``, atribuidas por INSTRUMENTO.

    Solo se evalúa si el día tiene alguna cara ejecutada (si no, el comparador ya declara el
    paso ``NOT_MEASURED``): comparar contra un ``0`` inexistente fabricaría una divergencia.
    """
    from bolsa_application.dia_d_auto_feedback import SOFTWARE, normalize_error

    declared_counts: dict[str, int] = {}
    for row in declared_row.get("fillRows") or ():
        symbol = str(row.get("symbol") or "").strip()
        if symbol:
            declared_counts[symbol] = declared_counts.get(symbol, 0) + 1

    errors: list[dict[str, Any]] = []
    for symbol in sorted(set(declared_counts) | set(executed_counts)):
        if declared_counts.get(symbol, 0) != executed_counts.get(symbol, 0):
            entry = normalize_error(day=day, symbol=symbol, kind=SOFTWARE, code="FILL")
            if entry is not None:
                errors.append(entry)
    return errors


# ── Orquestación ─────────────────────────────────────────────────────────────────


def _resolve_window(args: argparse.Namespace, days: list[str]) -> tuple[str, str]:
    """Ventana ``[D0, D1]`` pedida por ``--from/--to`` o por ``--at/--days`` (índices de barras)."""
    from bolsa_application.dia_d_auto import normalize_day

    start = normalize_day(args.from_day)
    end = normalize_day(args.to_day)
    if start and end:
        if start > end:
            raise RuntimeError(f"la ventana está invertida: {start} > {end}")
        return start, end

    if not normalize_day(args.at):
        raise RuntimeError("indica --from/--to o --at (con --days)")

    anchor = normalize_day(args.at)
    if anchor not in days:
        raise RuntimeError(f"el día {anchor} no está en el calendario de barras")
    span = max(1, int(args.days))
    end_index = days.index(anchor)
    start_index = max(0, end_index - (span - 1))
    return days[start_index], days[end_index]


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.dia_d_auto import compare_declared_vs_executed, normalize_day
    from bolsa_application.dia_d_auto_feedback import (
        SOFTWARE,
        build_dia_d_feedback_artifact,
        build_value_scorecard,
        normalize_error,
        software_error_for_step,
    )
    from bolsa_application.operability_window import window_gate
    from bolsa_application.replay_oos import census_operable_days
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    v89 = _load_v89()
    v86 = v89._load_v86()  # noqa: SLF001 — MISMO harness.
    v87 = v89._load_v87()  # noqa: SLF001

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    try:
        explicit_watch = [s.strip() for s in (args.watch or "").split(",") if s.strip()]
        watch = explicit_watch
        if not watch:
            v76 = v86._load_v76_module()  # noqa: SLF001 — MISMA derivación del watch.
            watch = await v76._watch_from_catalog(  # noqa: SLF001
                factory, int(args.watch_size), min_bars=int(args.min_bars)
            )
        if not watch:
            raise RuntimeError("el catálogo no aportó ningún instrumento con sector e historia")
        # D34-05: el watch derivado del catálogo ACTUAL puede introducir survivorship bias en
        # estudios históricos. Se DECLARA (no se cambia la derivación).
        watch_source = "explicit" if explicit_watch else "catalog"
        v86._configure_env(watch=watch, venue=str(args.venue), edge=float(args.edge))  # noqa: SLF001
        # Determinismo: el precio del replay es el ``price_script`` histórico inyectado.
        os.environ["AUTO_ENGINE_SIM_REAL_PRICE"] = "0"

        bars_by_symbol = await v86._read_bars(factory, watch)  # noqa: SLF001
        days = v86._trading_days(bars_by_symbol)  # noqa: SLF001
        if not days:
            raise RuntimeError("no hay barras D1 para simular")

        window_from, window_to = _resolve_window(args, days)
        if window_from not in days or window_to not in days:
            raise RuntimeError(
                f"la ventana {window_from}..{window_to} no está en el calendario "
                f"({days[0]}..{days[-1]})"
            )
        d0_index = days.index(window_from)
        d1_index = days.index(window_to)

        start_index = max(1, d0_index - max(1, int(args.history_days)))
        end_index = min(len(days), d1_index + 1 + max(0, int(args.horizon_days)))
        census = census_operable_days(bars_by_symbol, days)
        operable_flags = [row.entries_allowed_long for row in census.days]
        sectors = await v86._load_sectors(factory, watch)  # noqa: SLF001

        replay = await v87._run_durable_replay(  # noqa: SLF001 — harness hermético.
            watch=watch,
            bars_by_symbol=bars_by_symbol,
            sectors=sectors,
            days=days,
            start_index=start_index,
            max_ticks=end_index - start_index,
            edge=float(args.edge),
            account_id=str(args.account_id),
            version_a=str(args.version_a),
            engine_id=f"dia-d-feedback-{os.urandom(3).hex()}",
            operable_days=operable_flags,
            durable_cycle=True,
        )

        score = replay.get("score") or {}
        day_rows = {row.get("day"): row for row in replay.get("perDay", [])}
        book_by_day = {
            row.get("day"): row for row in (replay.get("book") or {}).get("perDay", [])
        }
        window_days = [day for day in days[d0_index : d1_index + 1] if day in day_rows]
        if not window_days:
            raise RuntimeError("el replay no alcanzó ningún día de la ventana pedida")

        errors: list[dict[str, Any]] = []
        gate_rows: list[dict[str, Any]] = []

        # El cierre durable de un D-cycle se busca hasta el MISMO horizonte OOS que el replay
        # (identidad única declarado/ejecutado; hallazgo D34-01).
        replay_end = normalize_day(replay.get("endDay"))
        close_window_end = (
            datetime.fromisoformat(f"{replay_end}T00:00:00+00:00") + timedelta(days=1)
            if replay_end
            else None
        )

        def _add(entry: dict[str, Any] | None) -> None:
            if entry is not None:
                errors.append(entry)

        for day in window_days:
            declared_row = day_rows[day]
            declared = v89._declared_steps(declared_row)  # noqa: SLF001
            oos = v89._oos_for_day(score, day)  # noqa: SLF001
            declared["CYCLE_CLOSED"] = v89._cycle_closed_step(oos)  # noqa: SLF001
            executed, executed_detail = await v89._read_executed_facts(  # noqa: SLF001
                factory,
                account_id=str(args.account_id),
                day=day,
                close_window_end=close_window_end,
            )
            comparison = compare_declared_vs_executed(declared, executed)
            for row in comparison:
                step = str(row.get("step"))
                # FILL se atribuye por INSTRUMENTO más abajo (precisión); aquí SIGNAL/ORDER.
                if step == "FILL":
                    continue
                if software_error_for_step(step, row.get("verdict")):
                    _add(normalize_error(day=day, kind=SOFTWARE, code=step))

            errors.extend(await _read_day_errors(factory, account_id=str(args.account_id), day=day))

            if bool(executed_detail.get("anyDurableFacts")):
                executed_fills = await _read_fill_counts_by_symbol(
                    factory, account_id=str(args.account_id), day=day
                )
                errors.extend(
                    _fill_divergences(
                        day=day, declared_row=declared_row, executed_counts=executed_fills
                    )
                )

            # Integridad del replay: un libro no medible es un fallo de SOFTWARE declarado.
            book_row = book_by_day.get(day)
            if book_row is not None and not book_row.get("measurable"):
                _add(normalize_error(day=day, kind=SOFTWARE, code="blocked"))

            gate_rows.append(
                {
                    "day": day,
                    "regimes": [declared_row.get("regime")] if declared_row.get("regime") else [],
                    "measurableCycles": int(oos.get("closedCount", 0) or 0),
                }
            )

        horizon = replay.get("horizon") or {}
        if horizon.get("truncationReason"):
            refused = replay.get("refusedDay") or horizon.get("lastDay") or window_days[-1]
            _add(normalize_error(day=refused, kind=SOFTWARE, code=str(horizon["truncationReason"])))

        round_trips = [
            row
            for row in score.get("roundTrips", [])
            if str(row.get("entryDay") or "") in set(window_days)
        ]
        by_symbol: dict[str, list[dict[str, Any]]] = {}
        for trip in round_trips:
            by_symbol.setdefault(str(trip.get("symbol") or ""), []).append(trip)

        symbols = sorted(
            {str(symbol) for symbol in watch}
            | {symbol for symbol in by_symbol if symbol}
            | {str(error.get("symbol")) for error in errors if error.get("symbol")}
        )
        values = [
            build_value_scorecard(
                symbol,
                round_trips=by_symbol.get(symbol, []),
                errors=[error for error in errors if str(error.get("symbol") or "") == symbol],
                days=window_days,
            )
            for symbol in symbols
        ]

        gate = window_gate(gate_rows)
        return build_dia_d_feedback_artifact(
            window_from=window_days[0],
            window_to=window_days[-1],
            days=window_days,
            values=values,
            errors=errors,
            gate=gate,
            meta={
                "bump": "2.11.48-beta",
                "phase": "V2.90 DIA-D AUTO FEEDBACK",
                "nature": "INVESTIGACION",
                "account": str(args.account_id),
                "versionA": str(args.version_a),
                "venue": str(args.venue),
                "watchSize": len(watch),
                "watchSource": watch_source,
                "survivorBiasRisk": watch_source == "catalog",
                "historyDays": int(args.history_days),
                "horizonDays": int(args.horizon_days),
                "replayStart": replay.get("startDay"),
                "replayEnd": replay.get("endDay"),
                "replayHorizon": horizon,
                "realPriceForcedOff": True,
            },
        )
    finally:
        await engine.dispose()


def _print_text(artifact: dict[str, Any]) -> None:
    window = artifact["window"]
    summary = artifact["summary"]
    print(f"DÍA-D AUTO · FEEDBACK READ-ONLY · {window['from']}..{window['to']}")
    print("=" * 72)
    errors = summary["errors"]
    print(
        f"valores                   {summary['values']} "
        f"(soportadosOOS={summary['oosSupported']} mixtos={summary['mixed']} "
        f"refutados={summary['refuted']} n/d={summary['notMeasured']})"
    )
    print(
        f"errores                   software={errors['SOFTWARE']} "
        f"operativa={errors['OPERATIONAL']} datos={errors['DATA']}"
    )
    print(f"gate de ventana           {artifact.get('gate', {}).get('verdict')}")
    print()
    print("VALOR                VEREDICTO      R medio    hit      n    errores")
    print("-" * 72)
    for value in artifact["values"]:
        expectancy = value["expectancyR"]
        hit = value["hitRate"]
        print(
            f"{value['symbol']:<20} {value['verdict']:<14} "
            f"{('n/d' if expectancy is None else f'{expectancy:+.3f}'):>8} "
            f"{('n/d' if hit is None else f'{hit:.2f}'):>5} "
            f"{value['measuredCycles']:>5} {value['errorTotal']:>8}"
        )
    if artifact.get("limits"):
        print()
        print("LÍMITES DECLARADOS")
        for item in artifact["limits"]:
            print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_day", default=None, help="primer día D0 (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_day", default=None, help="último día D1 (YYYY-MM-DD)")
    parser.add_argument("--at", default=None, help="ancla D1 cuando no se da --from/--to")
    parser.add_argument("--days", type=int, default=5, help="días de la ventana con --at")
    parser.add_argument("--watch", default=None, help="instrumentos separados por coma (si falta, catálogo)")
    parser.add_argument("--watch-size", type=int, default=20, help="tamaño del watch derivado")
    parser.add_argument("--min-bars", type=int, default=60, help="barras D1 mínimas en el watch derivado")
    parser.add_argument("--history-days", type=int, default=90, help="días previos a D0 simulados (contexto)")
    parser.add_argument("--horizon-days", type=int, default=20, help="días posteriores a D1 simulados (OOS)")
    parser.add_argument("--edge", type=float, default=0.9, help="valor declarado del seam de edge")
    parser.add_argument("--account-id", default="1484e253d2d54645945a6b1d7", help="cuenta de la ventana")
    parser.add_argument("--version-a", default="v283-window-a", help="versión A de la ventana")
    parser.add_argument("--venue", default="paper", choices=("paper", "simulated"))
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    args = parser.parse_args(argv)

    if int(args.watch_size) <= 0 or int(args.min_bars) <= 0:
        print("# uso incorrecto: --watch-size y --min-bars deben ser > 0", file=sys.stderr)
        return 1
    if int(args.days) < 1 or int(args.history_days) < 1 or int(args.horizon_days) < 0:
        print("# uso incorrecto: --days >= 1, --history-days >= 1 y --horizon-days >= 0", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    try:
        artifact = asyncio.run(_run(args))
    except Exception as error:  # noqa: BLE001 — sin PG/mercado no hay evidencia: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo construir el feedback ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    window = artifact["window"]
    default_name = f"feedback-{window['from']}_{window['to']}.json"
    out_path = pathlib.Path(args.out) if args.out else _REPO_ROOT / _OUT_SUBDIR / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    if args.json:
        print(payload)
    else:
        _print_text(artifact)
        print()
        print(f"artefacto                 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
