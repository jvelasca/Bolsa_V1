"""V2.86 · AUTO-MATERIAL-14 — Replay OOS de viabilidad del motor AUTO (INVESTIGACIÓN).

Mueve la barra temporal: sitúa el motor AUTO **congelado** en una fecha pasada, ejecuta la
operativa día a día sobre el **mismo** watch/cuenta/versión de la ventana PAPER y puntúa el
resultado contra barras futuras **ya conocidas**. Es el patrón walk-forward/OOS estándar.

Qué es
------
1. **Paso 0 · censo** (read-only): por cada día ``D`` de la historia, régimen del watch con
   barras ``timestamp <= D`` (reutiliza el clasificador y el agregado conservador del motor)
   y si ese día habría permitido un LONG.
2. **Paso 2 · replay hermético**: ``AutoSimulationWorker`` congelado, cableado con
   ``regime_source``/``atr_source`` acotados a ``as_of``, reloj y ``price_script``
   históricos, y **stores en memoria** ⇒ **cero escrituras a PostgreSQL**.
3. **Paso 3 · puntuación OOS**: R realizado de cada ida y vuelta con el stop del motor,
   acierto de signo y distribución. Todo hueco se declara ``n/d``.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO sustituye la ventana PAPER.** El cubo de calendario sale del **reloj de pared**
  (``sim_fill_finance_context.created_at``), así que un replay nunca fabrica cubos durables.
* **NO cierra ``P3-2``/``P3-3``**: es evidencia de **investigación**, clase distinta.
* **Aproximación D1**: un día = un tick.
* No se baja ningún umbral, no se fuerza régimen, no se backdatea, no se escribe en la BD.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_86_replay_oos_viability.py --json
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
from datetime import UTC, datetime
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"
_SYMBOLS_ENV = "AUTO_ENGINE_SIMULATED_WATCH"

#: Cuenta y versión de la ventana PAPER (para que los números sean contrastables con D1).
_DEFAULT_ACCOUNT = "1484e253d2d54645945a6b1d7"
_DEFAULT_VERSION_A = "v283-window-a"

#: Valor del seam de edge: NO es una medición, es un dato declarado (la BD no se escribe).
_DEFAULT_EDGE = 0.9

logger = logging.getLogger("v2_86_replay_oos_viability")


# ── Env del motor (mismas env del productor V2.76; SIN forzar régimen) ─────────────


def _configure_env(*, watch: list[str], venue: str, edge: float) -> None:
    """Fija las env del motor. NO fija ``AUTO_ENGINE_SIM_V2_REGIME`` (el régimen son barras)."""
    os.environ.update(
        {
            "AUTO_SIMULATION_WORKER_ENABLED": "1",
            "AUTO_ENGINE_SIM_SPINE_AUTO": "0",
            "AUTO_ENGINE_SIM_V2": "1",
            "AUTO_ENGINE_SIM_V2_EQUITY": "100000",
            "AUTO_ENGINE_SIM_V2_TOP_N": "5",
            # Sin ATR real la geometría no se sostiene: el símbolo sin barras se veta (se declara).
            "AUTO_ENGINE_SIM_V2_ATR_REQUIRED": "1",
            "AUTO_ENGINE_SIM_LOT_QTY": "100",
            "AUTO_ENGINE_SIMULATED_WATCH": ",".join(watch),
            "AUTO_ENGINE_SIMULATED_VENUE": venue,
            # El gate PAPER se corre con esta venue.
            "BROKER_VENUE": "paper",
        }
    )
    # Regla dura del plan: NADA de régimen forzado (forzarlo colapsaría todo a un episodio).
    os.environ.pop("AUTO_ENGINE_SIM_V2_REGIME", None)
    os.environ["AUTO_ENGINE_SIM_REPLAY_EDGE"] = str(edge)


def _watch_from_cli(raw: str | None) -> list[str]:
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


def _load_v76_module() -> Any:
    """Carga el runner de ``v2.76`` para reutilizar su MISMA derivación de watch del catálogo."""
    path = pathlib.Path(__file__).with_name("v2_76_forward_market_material.py")
    spec = importlib.util.spec_from_file_location("v2_76_forward_market_material", path)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ── Lecturas read-only ───────────────────────────────────────────────────────────


async def _read_bars(factory: Any, watch: list[str]) -> dict[str, list[Any]]:
    """Barras D1 COMPLETAS por símbolo (read-only). El acotado a ``as_of`` es del loader."""
    from bolsa_infrastructure.database.repositories.ohlcv_repository import (
        SqlAlchemyOhlcvRepository,
    )

    out: dict[str, list[Any]] = {}
    async with factory() as session:
        repo = SqlAlchemyOhlcvRepository(session)
        for symbol in watch:
            try:
                out[str(symbol)] = list(await repo.get_bars(symbol, limit=None))
            except Exception:  # noqa: BLE001 — sin barras el símbolo queda fuera del censo.
                logger.exception("no se pudieron leer barras de %s", symbol)
                out[str(symbol)] = []
    return out


async def _load_sectors(factory: Any, watch: list[str]) -> dict[str, str]:
    """Sector del catálogo por símbolo (read-only): sin él el motor veta ``sector_unknown``."""
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import InstrumentRow

    async with factory() as session:
        rows = (
            await session.execute(
                select(InstrumentRow.id, InstrumentRow.sector).where(
                    InstrumentRow.id.in_(list(watch))
                )
            )
        ).all()
    return {str(row[0]): str(row[1]) for row in rows if row[1]}


def _trading_days(bars_by_symbol: dict[str, list[Any]]) -> list[str]:
    days = {day for bars in bars_by_symbol.values() for bar in bars if (day := _bar_day(bar))}
    return sorted(days)


def _bar_day(bar: Any) -> str:
    from bolsa_application.replay_oos import bar_day

    return bar_day(bar)


def _opens_by_symbol(bars_by_symbol: dict[str, list[Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for symbol, bars in bars_by_symbol.items():
        table: dict[str, float] = {}
        for bar in bars:
            day = _bar_day(bar)
            try:
                table[day] = float(bar.open)
            except (AttributeError, TypeError, ValueError):
                continue
        out[str(symbol)] = table
    return out


# ── Paso 2 · harness hermético (cero escrituras a PG) ────────────────────────────


class _RecordingContextStore:
    """Envoltorio en memoria: registra los fills en ORDEN para materializar el día.

    Delega en ``InMemorySimFillFinanceContextStore`` (cuarentena: cero PG) y solo añade una
    lista ordenada de inserción, que el harness usa para saber qué fills ocurrieron en cada
    tick. No altera ninguna semántica del store.
    """

    def __init__(self) -> None:
        from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore

        self._inner = InMemorySimFillFinanceContextStore()
        self.order: list[Any] = []

    async def save(self, context: Any) -> None:
        await self._inner.save(context)
        self.order.append(context)

    async def get(self, execution_id: str) -> Any:
        return await self._inner.get(execution_id)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def _hold_decider(source: str) -> Any:
    from bolsa_application.decision_contract import DecisionPackage

    def _decide(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0, source=source)

    return _decide


class _ConfirmingFinanceApplier:
    """Applier de dinero hermético: CONFIRMA cada fill (no mueve dinero, retira la captura).

    El replay no escribe en PostgreSQL, así que las capturas de ``execution_events`` nunca
    se materializan por el camino durable. Sin un applier que las CONFIRME, cada captura
    sigue contando como capital PENDIENTE para siempre y el libro de compromisos se infla
    hasta vetar todas las aperturas (``risk_budget_exceeded``/``open_orders_unmeasurable``),
    truncando el replay a su primer episodio. Es el mismo patrón que usan los tests del
    camino de dinero (``_MoneyApplier`` en ``test_auto_v2_partial_fills``).
    """

    def __init__(self) -> None:
        self.applied: list[str] = []

    async def __call__(self, execution: Any) -> bool:
        self.applied.append(str(getattr(execution, "execution_id", "")))
        return True


def _edge_source(edge: float) -> Any:
    """``EdgeReportSource`` con lector en memoria (el edge es un DATO declarado, no una medición)."""
    from bolsa_application.auto_v2_entry import EdgeReportSource

    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return float(edge)

    return EdgeReportSource(reader=_read)


async def _run_replay(
    *,
    watch: list[str],
    bars_by_symbol: dict[str, list[Any]],
    sectors: dict[str, str],
    days: list[str],
    start_index: int,
    max_ticks: int,
    edge: float,
    account_id: str,
    version_a: str,
    engine_id: str,
) -> dict[str, Any]:
    """Replay hermético sobre el worker CONGELADO. Devuelve los ticks materializados."""
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
    from bolsa_application.auto_forward_deciders import build_forward_pair_decider, split_watch
    from bolsa_application.auto_v2_entry import (
        AUTO_ENTRY_DIRECTION,
        AtrSource,
        DiscoveryRegimeSource,
    )
    from bolsa_application.execution_event import InMemoryExecutionEventStore
    from bolsa_application.replay_oos import (
        ReplayCursor,
        ReplayFill,
        ReplayTick,
        make_as_of_bar_loader,
        score_replay,
    )
    from bolsa_application.reservation_store import InMemoryReservationStore
    from bolsa_application.sim_durable_store import (
        InMemorySimAutoPositionStore,
        InMemorySimConsumedSignalStore,
    )

    cursor = ReplayCursor(days, _opens_by_symbol(bars_by_symbol), start_index=start_index)
    loader = make_as_of_bar_loader(_ReadOnlyBarPort(bars_by_symbol), watch, cursor.as_of)
    regime_source = DiscoveryRegimeSource(bars_provider=loader)
    atr_source = AtrSource(bars_provider=loader)
    contexts = _RecordingContextStore()

    worker = AutoSimulationWorker(
        engine_id=engine_id,
        account_id=account_id,
        # Hermético: la cuenta no se toca en PG, así que no se exige su presencia.
        require_account_id=False,
        price_script=cursor.price_script,
        clock=cursor.clock,
        regime_source=regime_source,
        atr_source=atr_source,
        sector_source=lambda symbol: sectors.get(str(symbol)),
        liquidity_source=lambda _symbol: 1_000_000.0,
        edge_source=_edge_source(edge),
        kill_switch_source=lambda: False,
        exec_store=InMemoryExecutionEventStore(),
        context_store=contexts,
        position_store=InMemorySimAutoPositionStore(),
        consumed_signal_store=InMemorySimConsumedSignalStore(),
        # AUTO-1b: las reservas son la AUTORIDAD del capital/riesgo comprometido. Sin este
        # libro el camino hermético deriva el pendiente de ``execution_events`` y el libro
        # se vuelve INMEDIBLE ⇒ el motor veta aperturas (``open_orders_unmeasurable``).
        reservation_store=InMemoryReservationStore(),
        # Y las capturas hay que RETIRARLAS: sin applier de dinero la cola de compromisos
        # crece sin fin y el motor deja de abrir (``risk_budget_exceeded``). Applier
        # confirmador: no mueve dinero, solo cierra la captura. Sigue siendo 100% memoria.
        finance_applier=_ConfirmingFinanceApplier(),
    )
    watch_a, watch_b = split_watch(watch, a_share=0.5)
    # Versión B = HOLD: cargar la ACTIVE exigiría su propia fuente de barras acotada; se declara.
    pair = build_forward_pair_decider(
        watch_a=list(watch) if not watch_b else watch_a,
        version_a=version_a,
        decider_b=_hold_decider("replay:no-secondary"),
        held_quantity=lambda symbol: float(worker._open.get(symbol, 0)),  # noqa: SLF001 — cableado.
        lot_qty=100.0,
    )
    worker._decider = pair  # noqa: SLF001 — cableado (el worker no se edita).

    ticks: list[ReplayTick] = []
    totals = {"decided": 0, "proposals": 0, "vetoes": 0, "orders": 0, "fills": 0}
    consumed = 0
    end = len(days) if int(max_ticks) <= 0 else min(len(days), start_index + int(max_ticks))
    for index in range(start_index, end):
        cursor.set_index(index)
        report = await worker.auto_turn()
        for key in totals:
            totals[key] += int(getattr(report, key, 0) or 0)
        rows = contexts.order[consumed:]
        consumed = len(contexts.order)
        fills = tuple(
            ReplayFill(
                day=cursor.current_day(),
                symbol=str(row.instrument_id),
                side=str(row.side),
                quantity=float(row.quantity),
                price=float(row.price),
                strategy_version=row.strategy_version_id,
                cycle_id=row.cycle_id,
                # La dirección sale de la ÚNICA fuente del motor (no de un literal).
                direction=AUTO_ENTRY_DIRECTION,
            )
            for row in rows
        )
        ticks.append(
            ReplayTick(
                day=cursor.current_day(),
                regime=regime_source(),
                prices={str(s): cursor.price_script(str(s)) for s in watch},
                open_positions={
                    str(s): float(q) for s, q in worker._open.items() if q > 0  # noqa: SLF001
                },
                entry_prices={
                    str(s): float(p) for s, p in worker._entry_price.items()  # noqa: SLF001
                },
                stops=dict(worker._v2_stop_map()),  # noqa: SLF001 — lectura de estado.
                fill_rows=fills,
                proposals=int(getattr(report, "proposals", 0) or 0),
                vetoes=int(getattr(report, "vetoes", 0) or 0),
                orders=int(getattr(report, "orders", 0) or 0),
                fills=int(getattr(report, "fills", 0) or 0),
            )
        )
        done = len(ticks)
        if done % 50 == 0 or done == (end - start_index):
            print(
                f"  [replay] {done}/{end - start_index} días · {cursor.current_day()} · "
                f"fills={totals['fills']} vetoes={totals['vetoes']}",
                flush=True,
            )

    score = score_replay(ticks)
    regimes: dict[str, int] = {}
    per_day: list[dict[str, Any]] = []
    for tick in ticks:
        key = str(tick.regime or "UNKNOWN")
        regimes[key] = regimes.get(key, 0) + 1
        row: dict[str, Any] = {
            "day": tick.day,
            "regime": tick.regime,
            "proposals": tick.proposals,
            "vetoes": tick.vetoes,
            "orders": tick.orders,
            "fills": tick.fills,
            "open": len(tick.open_positions),
        }
        if tick.fill_rows:
            # Detalle SOLO de los días con fills (acota el artefacto) con el stop VIGENTE de
            # cada símbolo implicado: es lo que permite auditar el denominador de R.
            row["fillRows"] = [
                {
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "quantity": fill.quantity,
                    "price": fill.price,
                    "stop": tick.stops.get(fill.symbol),
                    "version": fill.strategy_version,
                }
                for fill in tick.fill_rows
            ]
        per_day.append(row)

    # Motivos de veto por FAMILIA (read-only): es lo que explica por qué el motor deja de
    # proponer (régimen, gobernador, drawdown, datos, ...) y evita leer "0 propuestas" como
    # "sin señal". Reutiliza el lector del journal de operabilidad (mismo vocabulario).
    journal_reasons: dict[str, int] = {}
    try:
        from bolsa_application.market_operability import (
            ENTRY_DECISION_EVENT,
            collect_journal_reasons,
        )

        journal_reasons = dict(
            collect_journal_reasons(
                list(getattr(worker, "_v2_journal", ()) or ()),
                events=frozenset({ENTRY_DECISION_EVENT}),
            )
        )
    except Exception:  # noqa: BLE001 — sin lectura del journal se declara el hueco (no se finge).
        logger.exception("no se pudieron leer los motivos del journal")

    return {
        "startDay": days[start_index] if 0 <= start_index < len(days) else None,
        "endDay": ticks[-1].day if ticks else None,
        "totals": totals,
        "regimeCounts": regimes,
        "journalReasons": journal_reasons,
        "perDay": per_day,
        "daysWithFills": sum(1 for tick in ticks if tick.fill_rows),
        "watchA": list(watch_a),
        "watchB": list(watch_b),
        "pairActive": False,
        "score": score.to_dict(),
        "ticks": len(ticks),
    }


class _ReadOnlyBarPort:
    """Port read-only de barras en memoria: sirve el histórico y acota por ``date_to``.

    Sustituye al repositorio para que el harness sea hermético por construcción (ni una
    consulta durante el replay) y para que el ``as_of`` se aplique de forma determinista.
    """

    def __init__(self, bars_by_symbol: dict[str, list[Any]]) -> None:
        self._bars = {str(k): list(v) for k, v in bars_by_symbol.items()}

    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: Any = None,
        limit: int | None = None,
        date_to: str | None = None,
    ) -> list[Any]:
        rows = list(self._bars.get(str(instrument_id), []))
        if date_to:
            rows = [bar for bar in rows if _bar_day(bar) and _bar_day(bar) <= str(date_to)[:10]]
        if limit is not None and int(limit) > 0:
            rows = rows[-int(limit) :]
        return rows


# ── Informe ──────────────────────────────────────────────────────────────────────


def _print_census(census: dict[str, Any]) -> None:
    """Render del censo a partir del ``dict`` que publica ``CensusReport.to_dict()``.

    ``main`` le pasa ``evidence["census"]``, que es ``census.to_dict()`` — **no** el objeto
    ``CensusReport``. Leer atributos aquí reventaba el modo texto sin ``--json`` con
    ``AttributeError: 'dict' object has no attribute 'watch'`` (el ``--out`` se escribe antes,
    así que el artefacto sobrevivía y el fallo pasaba desapercibido).
    """
    print("PASO 0 · CENSO DE DÍAS OPERABLES (read-only, sin lookahead)")
    print("-" * 64)
    print(f"watch                     {census.get('watch')} símbolos")
    print(f"días de historia          {census.get('totalDays')}")
    print(f"días OPERABLES (long)     {census.get('operableDays')}")
    print(f"  por eje operativo       {census.get('operableByOperational')}")
    print(f"racha operable máxima     {census.get('maxOperableStreak')}")
    print(f"distribución de régimen   {census.get('aggregateCounts')}")
    print("  (muestra de días operables, máx. 10)")
    shown = 0
    for row in census.get("days") or ():
        if not row.get("entriesAllowedLong"):
            continue
        print(f"    {row['day']}  {row['operational']:16s} {dict(row.get('counts') or {})}")
        shown += 1
        if shown >= 10:
            break
    if shown == 0:
        print("    (ninguno)")


def _print_replay(replay: dict[str, Any]) -> None:
    print()
    print("PASO 2/3 · REPLAY HERMÉTICO Y PUNTUACIÓN OOS")
    print("-" * 64)
    print(f"ventana simulada          {replay['startDay']} → {replay['endDay']} ({replay['ticks']} ticks)")
    print(f"turn totals               {replay['totals']}")
    print(f"régimen por tick          {replay['regimeCounts']}")
    if replay.get("journalReasons"):
        print(f"motivos de veto (journal) {replay['journalReasons']}")
    score = replay["score"]
    print(f"idas y vueltas cerradas   {score['realizedCount']}")
    print(f"R realizado (total)       {score['realizedRTotal']}")
    print(f"R medio / mediano         {score['meanR']} / {score['medianR']}")
    print(f"acierto de signo (R>0)    {score['positiveShare']}")
    print(f"por versión               {score['byVersion']}")
    print(f"abiertas al cierre        {len(score['openPositions'])}")
    if score["unmeasured"]:
        print(f"huecos declarados (n/d)   {score['unmeasuredCount']} · {score['unmeasuredReasons']}")


def _print_verdict(evidence: dict[str, Any]) -> None:
    census = evidence["census"]
    print()
    print("VEREDICTO")
    print("-" * 64)
    if census["operableDays"] == 0:
        print("FRACASO HONESTO: NINGÚN día de la historia habría permitido un LONG.")
        print("El entregable ES este hallazgo: el bloqueo no es del sincronizador ni de la")
        print("ventana, es ESTRUCTURAL (la agregación conservadora exige que NINGÚN símbolo")
        print("del watch sea trend_down/high_vol-vol para permitir un long).")
        print("NO se fuerza régimen, NO se bajan umbrales, NO se inventa operativa.")
    else:
        print(f"El censo encuentra {census['operableDays']} días operables en la historia.")
    print("NOTA: evidencia de INVESTIGACIÓN. NO sustituye la ventana PAPER (el cubo de")
    print("      calendario sale del reloj de pared) y NO cierra P3-2/P3-3 (siguen ABIERTAS).")


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.replay_oos import census_operable_days
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    try:
        watch = _watch_from_cli(args.watch)
        if not watch:
            v76 = _load_v76_module()
            watch = await v76._watch_from_catalog(  # noqa: SLF001 — MISMA derivación del watch.
                factory, int(args.watch_size), min_bars=int(args.min_bars)
            )
        if not watch:
            raise RuntimeError("el catálogo no aportó ningún instrumento con sector e historia")
        _configure_env(watch=watch, venue=str(args.venue), edge=float(args.edge))

        bars_by_symbol = await _read_bars(factory, watch)
        days = _trading_days(bars_by_symbol)
        if int(args.history_days) > 0:
            days = days[-int(args.history_days) :]
        if not days:
            raise RuntimeError("no hay barras D1 para censar")

        census = census_operable_days(bars_by_symbol, days)
        evidence: dict[str, Any] = {
            "bump": "2.11.0-beta",
            "phase": "V2.86 AUTO-MATERIAL-14 REPLAY OOS VIABILIDAD",
            "nature": "INVESTIGACION",
            "venue": str(args.venue),
            "account": str(args.account_id),
            "versionA": str(args.version_a),
            "watch": list(watch),
            "watchSize": len(watch),
            "historyDays": len(days),
            "census": census.to_dict(),
            "replay": None,
            "limits": [
                "NO sustituye la ventana PAPER: el cubo de calendario sale del reloj de pared.",
                "NO cierra P3-2/P3-3: es evidencia de INVESTIGACION.",
                "Aproximacion D1: un dia = un tick.",
                "Version B = HOLD (la ACTIVE exigiria su propia fuente de barras acotada).",
                f"Edge = {float(args.edge)} (dato declarado del seam, NO una medicion).",
                "Liquidez = 1e6 plana (dato declarado del seam, NO una medicion).",
                "Cero escrituras a PostgreSQL: stores en memoria (cuarentena).",
            ],
        }

        if not args.no_replay and census.operable_days > 0:
            start_index = int(args.start_index)
            if start_index < 0:
                first_full = next(
                    (
                        index
                        for index, row in enumerate(census.days)
                        if len(watch) > 0 and row.measured_symbols == len(watch)
                    ),
                    None,
                )
                start_index = (first_full + 1) if first_full is not None else 1
            sectors = await _load_sectors(factory, watch)
            evidence["sectorsKnown"] = len(sectors)
            evidence["replay"] = await _run_replay(
                watch=watch,
                bars_by_symbol=bars_by_symbol,
                sectors=sectors,
                days=days,
                start_index=max(1, start_index),
                max_ticks=int(args.max_ticks),
                edge=float(args.edge),
                account_id=str(args.account_id),
                version_a=str(args.version_a),
                engine_id=f"replay-oos-{os.urandom(3).hex()}",
            )
        elif not args.no_replay:
            evidence["replaySkipped"] = "census_gate: 0 dias operables (el paso 2 no aporta)"
        return evidence
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", default=None, help="instrumentos separados por coma (si falta, catálogo)")
    parser.add_argument("--watch-size", type=int, default=20, help="tamaño del watch derivado")
    parser.add_argument("--min-bars", type=int, default=60, help="barras D1 mínimas en el watch derivado")
    parser.add_argument("--history-days", type=int, default=0, help="acota a los últimos N días (0 = todo)")
    parser.add_argument(
        "--start-index",
        type=int,
        default=-1,
        help="índice del primer día simulado (-1 = automático: tras el warm-up de régimen)",
    )
    parser.add_argument("--max-ticks", type=int, default=0, help="tope de ticks (0 = todos)")
    parser.add_argument("--edge", type=float, default=_DEFAULT_EDGE, help="valor declarado del seam de edge")
    parser.add_argument("--no-replay", action="store_true", help="solo el censo (paso 0)")
    parser.add_argument("--account-id", default=_DEFAULT_ACCOUNT, help="cuenta de la ventana (solo etiqueta)")
    parser.add_argument("--version-a", default=_DEFAULT_VERSION_A, help="versión A de la ventana")
    parser.add_argument("--venue", default="paper", choices=("paper", "simulated"))
    parser.add_argument("--json", action="store_true", help="emite el payload como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    args = parser.parse_args(argv)

    if int(args.watch_size) <= 0 or int(args.min_bars) <= 0:
        print("# uso incorrecto: --watch-size y --min-bars deben ser > 0", file=sys.stderr)
        return 1

    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    try:
        evidence = asyncio.run(_run(args))
    except Exception as error:  # noqa: BLE001 — sin PG/mercado no hay evidencia: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo ejercitar el replay ({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    payload = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    if args.out:
        pathlib.Path(args.out).write_text(payload + "\n", encoding="utf-8")
    if args.json:
        print(payload)
    else:
        print(f"REPLAY OOS · VIABILIDAD DEL MOTOR AUTO (V2.86 · AUTO-MATERIAL-14) · {datetime.now(UTC):%Y-%m-%d}")
        print("=" * 64)
        print(f"cuenta / versión A        {evidence['account']} / {evidence['versionA']}")
        print(f"watch                     {evidence['watchSize']} símbolos")
        _print_census(evidence["census"])
        if evidence.get("replay"):
            _print_replay(evidence["replay"])
        _print_verdict(evidence)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
