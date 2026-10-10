"""V2.89 · DÍA-D AUTO — sandbox read-only del motor AUTO sobre una fecha pasada ``D``.

Qué es
------
Un **sandbox read-only** que sitúa el motor AUTO real en una fecha pasada ``D`` con reloj y
precio inyectados (el mismo harness hermético de ``v2.86``/``v2.87``), recoge lo que el motor
**DECLARÓ** que haría ese día, lo confronta con lo que la ventana PAPER **EJECUTÓ** de verdad
(los hechos durables de ``D``, leídos read-only) y con lo que el mercado hizo **después** de
``D`` (OOS real). El resultado es un artefacto JSON determinista que la UI de ``/auto-monitor``
sirve tal cual.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO sustituye la ventana PAPER.** El cubo de calendario sale del reloj de pared, así que un
  replay no fabrica cubos durables.
* **NO escribe en PostgreSQL**: el motor corre con stores en memoria (cuarentena). Las únicas
  lecturas son las barras, los sectores y los hechos durables de ``D``.
* **NO backdatea** ``created_at``: el reloj simulado no toca el camino durable.
* **Aproximación D1**: un día = un tick.
* Un paso sin hecho durable se declara ``NOT_MEASURED``; nunca se rellena con ``0``.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_89_dia_d_auto_replay.py \
        --at 2026-09-30 --json

    # Universe(D) point-in-time: disponibilidad REAL desde barras (+ aproximaciones declaradas)
    uv run --no-sync python apps/api-python/scripts/v2_89_dia_d_auto_replay.py \
        --at 2026-09-30 --universe pit --json
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
from datetime import UTC, datetime, timedelta
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

#: Cuenta y versión de la ventana PAPER (MISMOS valores que ``v2.86``/``v2.87``: sin una
#: cuenta/versión idénticas los números no serían contrastables). El edge sigue siendo un
#: DATO declarado del seam (no una medición): la BD no se escribe.
_DEFAULT_ACCOUNT = "1484e253d2d54645945a6b1d7"
_DEFAULT_VERSION_A = "v283-window-a"
_DEFAULT_EDGE = 0.9

#: Días de historia previos a ``D`` que se simulan para calentar régimen/ATR y contexto.
_DEFAULT_HISTORY_DAYS = 90
#: Días posteriores a ``D`` que se simulan para medir el OOS real del ciclo abierto en ``D``.
_DEFAULT_HORIZON_DAYS = 20

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto"

logger = logging.getLogger("v2_89_dia_d_auto_replay")


def _load_module(filename: str, name: str) -> Any:
    """Carga un runner hermano por ruta (mismo patrón que ``v2.86``→``v2.76``)."""
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_v86() -> Any:
    return _load_module("v2_86_replay_oos_viability.py", "v2_86_replay_oos_viability")


def _load_v87() -> Any:
    return _load_module("v2_87_replay_oos_durable_cycle.py", "v2_87_replay_oos_durable_cycle")


# ── Lecturas read-only de los HECHOS DURABLES de ``D`` ───────────────────────────


async def _read_executed_facts(
    factory: Any,
    *,
    account_id: str,
    day: str,
    close_window_end: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Lee (read-only) los hechos durables de ``D`` y los proyecta a la cadena AUTO.

    Devuelve ``(executed, detail)``. Cada magnitud no observable queda ``None`` (hueco
    declarado), nunca un ``0``. El rango temporal es ``[D 00:00 UTC, D+1 00:00 UTC)`` para
    ser determinista con independencia del huso de la sesión.

    ``CYCLE_CLOSED`` usa la MISMA identidad que el lado declarado (hallazgo D34-01): un
    **D-cycle** nace con su fill de APERTURA (``buy``) en ``D`` y se busca su CIERRE
    (``sell``) hasta ``close_window_end`` (el horizonte OOS del replay), no sólo dentro de
    ``D``. Así "ciclo nacido en D que cierra después" cuenta como cerrado en ambos lados.
    """
    from sqlalchemy import select

    from bolsa_application.dia_d_auto import cycle_closure_summary
    from bolsa_infrastructure.database.models.tables import (
        AutoExitOrderRow,
        DecisionJournalEntryRow,
        PortfolioReservationRow,
        SimFillFinanceContextRow,
    )

    start = datetime.fromisoformat(f"{day}T00:00:00+00:00")
    end = start + timedelta(days=1)
    close_end = close_window_end if close_window_end is not None and close_window_end > end else end

    detail: dict[str, Any] = {"day": day, "windowStart": start.isoformat(), "windowEnd": end.isoformat()}
    executed: dict[str, Any] = {}

    async with factory() as session:
        reservations = await _count(
            session,
            select(PortfolioReservationRow.reservation_id).where(
                PortfolioReservationRow.account_id == account_id,
                PortfolioReservationRow.created_at >= start,
                PortfolioReservationRow.created_at < end,
            ),
        )
        fills = await _count(
            session,
            select(SimFillFinanceContextRow.execution_id).where(
                SimFillFinanceContextRow.account_id == account_id,
                SimFillFinanceContextRow.created_at >= start,
                SimFillFinanceContextRow.created_at < end,
            ),
        )
        exit_orders = await _count(
            session,
            select(AutoExitOrderRow.exit_order_id).where(
                AutoExitOrderRow.account_id == account_id,
                AutoExitOrderRow.created_at >= start,
                AutoExitOrderRow.created_at < end,
            ),
        )
        journal_entries = await _count(
            session,
            select(DecisionJournalEntryRow.id).where(
                DecisionJournalEntryRow.account_id == account_id,
                DecisionJournalEntryRow.created_at >= start,
                DecisionJournalEntryRow.created_at < end,
            ),
        )
        cycle_rows = (
            await session.execute(
                select(
                    SimFillFinanceContextRow.cycle_id,
                    SimFillFinanceContextRow.side,
                    SimFillFinanceContextRow.created_at,
                ).where(
                    SimFillFinanceContextRow.account_id == account_id,
                    SimFillFinanceContextRow.created_at >= start,
                    SimFillFinanceContextRow.created_at < close_end,
                    SimFillFinanceContextRow.cycle_id.is_not(None),
                )
            )
        ).all()

    # Identidad ÚNICA (D34-01): el D-cycle nace con su APERTURA (buy) en D; su cierre es un
    # sell POSTERIOR a la apertura, hasta el horizonte OOS del replay. Un ciclo abierto en
    # D-1 y cerrado en D NO es un D-cycle (no nació aquí).
    opened_cycle_ids: set[str] = set()
    closed_cycle_ids: set[str] = set()
    for cycle_id, side, created_at in cycle_rows:
        key = str(cycle_id) if cycle_id is not None else ""
        if not key:
            continue
        side_key = str(side).lower()
        if side_key == "buy" and start <= created_at < end:
            opened_cycle_ids.add(key)
        elif side_key == "sell":
            closed_cycle_ids.add(key)
    closure = cycle_closure_summary(opened_cycle_ids, closed_cycle_ids)

    any_durable = bool(reservations or fills or exit_orders or journal_entries)
    if any_durable:
        executed["RESERVATION"] = reservations
        executed["FILL"] = fills
        # ``auto_exit_orders`` es el INTENT protector: es lo que la app registró como
        # protección de una posición. No hay tabla de órdenes de ENTRADA separada (viven en
        # la reserva), así que ``ORDER`` queda como hueco declarado.
        executed["PROTECTION"] = exit_orders
        executed["CYCLE_CLOSED"] = closure["step"]
    # ``SIGNAL``/``TOP_N``/``RISK``/``ORDER``/``SETTLEMENT`` no tienen una proyección durable
    # fiable: se declaran huecos (``None``), no ceros.

    detail.update(
        {
            "anyDurableFacts": any_durable,
            "reservationsCreated": reservations,
            "fills": fills,
            "exitOrdersCreated": exit_orders,
            "journalEntries": journal_entries,
            "closeWindowEnd": close_end.isoformat(),
            "openedCycles": closure["opened"],
            "closedCycles": closure["closed"],
            "openCycles": closure["open"],
            "cycleClosureUnmeasured": closure["unmeasured"],
        }
    )
    return executed, detail


async def _count(session: Any, statement: Any) -> int:
    """Cuenta las filas de un ``select`` de columnas concretas (read-only)."""
    rows = (await session.execute(statement)).all()
    return len(rows)


# ── Proyección del replay a la cadena declarada + OOS ────────────────────────────


def _declared_steps(day_row: dict[str, Any]) -> dict[str, Any]:
    """Proyecta la foto del tick ``D`` del replay a la cadena ``declarado``."""
    return {
        "SIGNAL": day_row.get("proposals", 0) + day_row.get("vetoes", 0),
        "TOP_N": day_row.get("proposals"),
        "RISK": day_row.get("vetoes"),
        "RESERVATION": day_row.get("liveReservations"),
        "ORDER": day_row.get("orders"),
        "FILL": day_row.get("fills"),
        "PROTECTION": day_row.get("openPositions"),
        "SETTLEMENT": None,
        "CYCLE_CLOSED": None,  # se rellena con el OOS (se cierra DESPUÉS de D).
    }


def _oos_for_day(score: dict[str, Any], day: str) -> dict[str, Any]:
    """OOS real del ciclo abierto en ``D``: idas y vueltas y posiciones vivas al horizonte."""
    realized = [row for row in score.get("roundTrips", []) if row.get("entryDay") == day]
    open_positions = [row for row in score.get("openPositions", []) if row.get("entryDay") == day]
    unmeasured = [gap for gap in score.get("unmeasured", []) if str(gap).startswith(f"{day}:")]
    return {
        "realized": realized,
        "open": open_positions,
        "realizedRTotal": sum(float(row.get("realizedR", 0.0) or 0.0) for row in realized),
        "closedCount": len(realized),
        "openCount": len(open_positions),
        "unmeasured": unmeasured,
        "unmeasuredCount": len(unmeasured),
    }


def _cycle_closed_step(oos: dict[str, Any]) -> Any:
    """``1`` si el ciclo de ``D`` cerró en el horizonte, ``0`` si sigue vivo, ``None`` sin ciclo."""
    if int(oos.get("closedCount", 0)) > 0:
        return 1
    if int(oos.get("openCount", 0)) > 0:
        return 0
    return None


# ── Orquestación ─────────────────────────────────────────────────────────────────


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.dia_d_auto import (
        DEFAULT_LIMITS,
        build_dia_d_auto_artifact,
        normalize_day,
    )
    from bolsa_application.replay_oos import census_operable_days
    from bolsa_application.universe_point_in_time import universe_ids
    from bolsa_application.universe_point_in_time_catalog import (
        CatalogPointInTimeUniverse,
    )
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    v86 = _load_v86()
    v87 = _load_v87()

    try:
        day = normalize_day(args.at) or datetime.now(UTC).strftime("%Y-%m-%d")
        explicit_watch = [s.strip() for s in (args.watch or "").split(",") if s.strip()]
        universe_coverage: dict[str, Any] | None = None
        watch = explicit_watch
        if not watch and str(args.universe) == "pit":
            # D35-01: fuente point-in-time REAL (disponibilidad desde barras) + aproximaciones
            # DECLARADAS (alta/baja/sector del catálogo). Fail-closed: sin miembros NO se cae
            # al catálogo actual (eso reintroduciría el sesgo que el flag quiere evitar).
            provider = await CatalogPointInTimeUniverse.load(
                factory, min_bars=int(args.min_bars)
            )
            universe_coverage = provider.coverage()
            watch = universe_ids(provider, day)[: max(1, int(args.watch_size))]
            if not watch:
                raise RuntimeError(
                    "el universo point-in-time no aportó ningún instrumento elegible en D"
                )
        if not watch:
            v76 = v86._load_v76_module()  # noqa: SLF001 — MISMA derivación del watch.
            watch = await v76._watch_from_catalog(  # noqa: SLF001
                factory, int(args.watch_size), min_bars=int(args.min_bars)
            )
        if not watch:
            raise RuntimeError("el catálogo no aportó ningún instrumento con sector e historia")
        # D34-05: el watch derivado del catálogo ACTUAL puede introducir survivorship bias en
        # estudios históricos. Se DECLARA (no se cambia la derivación). El watch point-in-time
        # (``runtime`` = "pit") sí parte de un contrato Universe(D), pero su ``active_*`` y
        # ``sector_at`` siguen siendo aproximaciones declaradas (ver ``meta.universeCoverage``).
        if explicit_watch:
            watch_source = "explicit"
        elif universe_coverage is not None:
            watch_source = "pit"
        else:
            watch_source = "catalog"
        v86._configure_env(watch=watch, venue=str(args.venue), edge=float(args.edge))  # noqa: SLF001
        # Determinismo: el precio del replay es el ``price_script`` histórico inyectado, no
        # una lectura en vivo. No se fuerza régimen ni se baja ningún umbral.
        os.environ["AUTO_ENGINE_SIM_REAL_PRICE"] = "0"

        bars_by_symbol = await v86._read_bars(factory, watch)  # noqa: SLF001
        days = v86._trading_days(bars_by_symbol)  # noqa: SLF001
        if not days:
            raise RuntimeError("no hay barras D1 para simular")

        if day not in days:
            raise RuntimeError(f"el día {day} no está en el calendario de barras ({days[0]}..{days[-1]})")
        d_index = days.index(day)

        start_index = max(1, d_index - max(1, int(args.history_days)))
        end_index = min(len(days), d_index + 1 + max(0, int(args.horizon_days)))
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
            engine_id=f"dia-d-auto-{os.urandom(3).hex()}",
            operable_days=operable_flags,
            durable_cycle=True,
        )

        day_row = next((row for row in replay.get("perDay", []) if row.get("day") == day), None)
        if day_row is None:
            raise RuntimeError(f"el replay no alcanzó el día {day}")
        score = replay.get("score") or {}
        oos = _oos_for_day(score, day)

        replay_end = normalize_day(replay.get("endDay"))
        close_window_end = (
            datetime.fromisoformat(f"{replay_end}T00:00:00+00:00") + timedelta(days=1)
            if replay_end
            else None
        )
        executed, executed_detail = await _read_executed_facts(
            factory,
            account_id=str(args.account_id),
            day=day,
            close_window_end=close_window_end,
        )
        declared = _declared_steps(day_row)
        declared["CYCLE_CLOSED"] = _cycle_closed_step(oos)

        limits = list(DEFAULT_LIMITS)
        if watch_source == "pit":
            limits.append(
                "Universe(D) point-in-time: availability_from/until son REALES (barras D1); "
                "active_from/active_until y sector_at son aproximaciones DECLARADAS (no hay "
                "historial de listado/baja ni de sector). Ver meta.universeCoverage."
            )

        artifact = build_dia_d_auto_artifact(
            day=day,
            declared=declared,
            executed=executed,
            oos=oos,
            declared_detail={
                "tick": day_row,
                "replayTotals": replay.get("totals"),
                "replayHorizon": replay.get("horizon"),
                "watchA": replay.get("watchA"),
                "watchB": replay.get("watchB"),
            },
            executed_detail=executed_detail,
            meta={
                "bump": "2.11.104-beta",
                "phase": "V2.89 DIA-D AUTO SANDBOX",
                "nature": "INVESTIGACION",
                "account": str(args.account_id),
                "versionA": str(args.version_a),
                "venue": str(args.venue),
                "watchSize": len(watch),
                "watchSource": watch_source,
                "survivorBiasRisk": watch_source == "catalog",
                "universeCoverage": universe_coverage,
                "universeExcludedNoBars": (universe_coverage or {}).get("excludedNoBars"),
                "historyDays": int(args.history_days),
                "horizonDays": int(args.horizon_days),
                "replayStart": replay.get("startDay"),
                "replayEnd": replay.get("endDay"),
                "realPriceForcedOff": True,
            },
            limits=limits,
        )
        return artifact
    finally:
        await engine.dispose()


def _print_text(artifact: dict[str, Any]) -> None:
    print(f"DÍA-D AUTO · SANDBOX READ-ONLY · {artifact['day']}")
    print("=" * 64)
    summary = artifact["summary"]
    print(f"veredicto global          {summary['verdict']}")
    print(f"pasos                     match={summary['match']} divergent={summary['divergent']} n/d={summary['notMeasured']}")
    print()
    print("PASO                 DECLARADO     EJECUTADO     VEREDICTO")
    print("-" * 64)
    for row in artifact["comparison"]:
        print(
            f"{row['step']:<20} {str(row['declared']):<13} {str(row['executed']):<13} {row['verdict']}"
        )
    oos = artifact.get("oos") or {}
    print()
    print(f"OOS real del ciclo de D   cerrados={oos.get('closedCount')} vivos={oos.get('openCount')} R={oos.get('realizedRTotal')}")
    if artifact.get("limits"):
        print()
        print("LÍMITES DECLARADOS")
        for item in artifact["limits"]:
            print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", required=True, help="día D (YYYY-MM-DD) que se opera como si fuese hoy")
    parser.add_argument("--watch", default=None, help="instrumentos separados por coma (si falta, catálogo)")
    parser.add_argument(
        "--universe",
        default="catalog",
        choices=("catalog", "pit"),
        help="fuente del watch si no hay --watch: 'catalog' (actual, con sesgo declarado) o 'pit' (Universe(D))",
    )
    parser.add_argument("--watch-size", type=int, default=20, help="tamaño del watch derivado")
    parser.add_argument("--min-bars", type=int, default=60, help="barras D1 mínimas en el watch derivado")
    parser.add_argument("--history-days", type=int, default=_DEFAULT_HISTORY_DAYS, help="días previos a D simulados (contexto)")
    parser.add_argument("--horizon-days", type=int, default=_DEFAULT_HORIZON_DAYS, help="días posteriores a D simulados (OOS)")
    parser.add_argument("--edge", type=float, default=_DEFAULT_EDGE, help="valor declarado del seam de edge")
    parser.add_argument("--account-id", default=_DEFAULT_ACCOUNT, help="cuenta de la ventana (etiqueta y hechos durables)")
    parser.add_argument("--version-a", default=_DEFAULT_VERSION_A, help="versión A de la ventana")
    parser.add_argument("--venue", default="paper", choices=("paper", "simulated"))
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    args = parser.parse_args(argv)

    if int(args.watch_size) <= 0 or int(args.min_bars) <= 0:
        print("# uso incorrecto: --watch-size y --min-bars deben ser > 0", file=sys.stderr)
        return 1
    if int(args.history_days) < 1 or int(args.horizon_days) < 0:
        print("# uso incorrecto: --history-days >= 1 y --horizon-days >= 0", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    try:
        artifact = asyncio.run(_run(args))
    except Exception as error:  # noqa: BLE001 — sin PG/mercado no hay evidencia: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo ejercitar el DÍA-D AUTO ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    out_path = pathlib.Path(args.out) if args.out else _REPO_ROOT / _OUT_SUBDIR / f"dia-d-auto-{artifact['day']}.json"
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
