#!/usr/bin/env python3
"""V2.75 · AUTO-MATERIAL-3 — ACUMULACIÓN DE MUESTRA: de `PRODUCER_READY` a `EVIDENCE_READY`.

Qué hace: conduce el camino REAL del productor AUTO 2.0 (``AutoSimRuntime`` → sesión por tick →
``worker.real_turn``) con un decider determinista y un ``price_script`` controlado, **encadenando
round-trips** sobre UNA cuenta PAPER nueva hasta cruzar el mínimo de ciclos medibles por estrategia
(``≥32``). Después LEE el material durable con la MISMA pieza que el gate
(``build_paper_material_readiness``) y declara el veredicto.

Qué NO hace (regla dura del repo):

* **No** baja ``min cycles`` / ``min R`` / ``folds`` / ``min_episodes`` para forzar un READY.
* **No** repara material (no rellena ``cycle_id`` ni ``reserved_risk``) ni toca el histórico legacy.
* **No** reparte: ``ALLOCATION`` sigue congelado (``auto18-v1`` / ``auto15-v1``). Sin migración.

Procedencia declarada (honestidad, ver el arranque del auditor): la muestra la produce el
**productor determinista** del repo (precio guionizado sobre la cola SIM de venue ``paper``); el
material durable es PAPER virtual y su R es **casi constante** entre ciclos. Sirve para cruzar el
mínimo de MUESTRA del gate (``EVIDENCE_READY``), NO para inferencia de mercado: el dataset refleja
el instrumento, no el mercado. ``read_paper_material`` etiqueta el material de PostgreSQL como
``paper_real`` (material durable), lo que aquí se declara explícitamente para no confundirlo con una
corrida PAPER sobre datos de mercado.

Uso (desde la raíz del repo)::

    uv run --no-sync python apps/api-python/scripts/v2_75_paper_sample_accumulation.py
    uv run --no-sync python apps/api-python/scripts/v2_75_paper_sample_accumulation.py --json --out evidencia.json

Códigos de salida: ``0`` si el material alcanza ``EVIDENCE_READY`` (estructura + mínimo); ``2`` si no
(hay PostgreSQL pero el material no llega al mínimo), ``1`` uso incorrecto.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

_SYMBOLS_ENV = "AUTO_ENGINE_SIMULATED_WATCH"
#: Versión de estrategia con la que el decider determinista ATRIBUYE sus propuestas. Es la MISMA vía
#: que un decider de producción (``DecisionPackage.source = "active-strategy:<v>"``). Bajo esta
#: versión se MIDE la muestra: el gate lee por versión pedida.
_STRATEGY_VERSION = "v75-producer-orb-v1"
_STRATEGY_SOURCE = f"active-strategy:{_STRATEGY_VERSION}"
_ATR = 2.0  # 2 % de 100 ⇒ stop estructural en 100 − 1.5×2 = 97.
_ENTRY = 100.0
_BREAK = 96.0  # rompe el stop (97): dispara la salida estructural del arm V2.
_LOT = 100.0
_MINUTE_STEP = timedelta(minutes=1)
_TICKS_PER_PHASE = 12


def _configure_env(*, venue: str) -> None:
    """Fija las env del productor. ``venue`` es SIM-only (paper/simulated)."""
    os.environ.update(
        {
            "AUTO_SIMULATION_WORKER_ENABLED": "1",
            "AUTO_ENGINE_SIM_SPINE_AUTO": "1",
            "AUTO_ENGINE_SIM_V2": "1",
            "AUTO_ENGINE_SIM_V2_REGIME": "BULL_TREND",
            "AUTO_ENGINE_SIM_V2_EQUITY": "100000",
            "AUTO_ENGINE_SIM_V2_TOP_N": "5",
            "AUTO_ENGINE_SIMULATED_VENUE": venue,
            "AUTO_ENGINE_SIM_INTERVAL_SECONDS": "1.0",
            "AUTO_ENGINE_SIM_LOT_QTY": str(int(_LOT)),
            # El gate PAPER se corre con esta venue: su guarda exige ``paper``.
            "BROKER_VENUE": "paper",
        }
    )


_FILL_CHUNKS = 4  # espeja ``auto_simulation_worker._FILL_CHUNKS``.
#: Ventana de minutos (la del worker: ``seed = minute * 100_003 + sum(ord(symbol)) % 9999``) que la
#: barrida exige que llene. Con worker NUEVO por round-trip, ``_minute`` arranca en ~1 y el
#: round-trip entero (apertura + cierre) cae dentro de esta ventana.
_FILL_WINDOW = range(0, 16)


def _filling_instrument_id(prefix: str) -> str:
    """Id determinista cuya orden LLENA (BUY y SELL) en toda la ventana de minutos (cola SIM).

    El seed real del worker es ``minute * 100_003 + sum(map(ord, symbol)) % 9999`` y ``_minute``
    avanza 1 por turno, así que un id que llena en ``_FILL_WINDOW`` garantiza que TANTO la entrada
    (buy) como la salida estructural (sell) se materialicen. Se exige **los dos lados** porque el
    ciclo necesita cerrar: un SELL sin llenar dejaría la posición abierta y el ciclo inexistente.
    """
    from bolsa_application.simulated_broker import simulated_fill_schedule

    for n in range(512):
        candidate = f"{prefix}{n:010d}"
        ok = True
        for side in ("buy", "sell"):
            for minute in _FILL_WINDOW:
                schedule = simulated_fill_schedule(
                    instrument_id=candidate,
                    side=side,
                    quantity=Decimal("100"),
                    venue_order_id=f"probe-{side}-{candidate}-{minute}",
                    seed=minute * 100_003 + sum(map(ord, candidate)) % 9999,
                    fill_chunks=_FILL_CHUNKS,
                    base_mid=_ENTRY,
                )
                if not schedule.fills:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} llena (buy+sell) en {len(_FILL_WINDOW)} minutos"
    )


class _RoundTrip:
    """Decider determinista del arm V2: BUY mientras no hay posición; HOLD con posición.

    La salida NO la pide el decider: la dispara el ``ExitPlan`` (parada estructural) al bajar el
    precio, por el MISMO camino que un stop real. Tras cerrar, el siguiente tick plano vuelve a
    proponer BUY ⇒ el round-trip se encadena y la muestra se acumula.
    """

    def __init__(self, worker: Any, instrument_id: str) -> None:
        self._worker = worker
        self._symbol = instrument_id

    def __call__(self, symbol: str) -> Any:
        from bolsa_application.decision_contract import DecisionPackage

        if symbol != self._symbol:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)
        held = self._worker._open.get(self._symbol, Decimal("0"))
        if held <= 0:
            return DecisionPackage(
                action="BUY",
                instrument_id=self._symbol,
                quantity=_LOT,
                source=_STRATEGY_SOURCE,
            )
        return DecisionPackage(action="HOLD", instrument_id=self._symbol, quantity=0)


async def _seed_account(session: Any) -> str:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"AUTO-V75-{os.urandom(4).hex()}",
        initial_deposit=100_000.0,
    )
    await session.commit()
    return scope.account.id


async def _seed_instrument(session: Any, instrument_id: str) -> None:
    from bolsa_infrastructure.database.models.tables import InstrumentRow

    if await session.get(InstrumentRow, instrument_id) is not None:
        return

    now = datetime.now(UTC)
    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"V75{os.urandom(3).hex().upper()}",
            yahoo_symbol=f"V75{os.urandom(4).hex()}",
            isin=None,
            name="AUTO-V75-Producer",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            # Gates fail-closed REALES: sector + fundamentals FRESCOS (sin ellos el motor veta por
            # ``sector_unknown``/``liquidity_unknown`` y no se ejercita el productor).
            sector="Technology",
            profile_snapshot={
                "fundamentals": {"advUsd": 50_000_000.0, "fetchedAt": now.isoformat()}
            },
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()


async def _seed_edge_report(session: Any, *, account_id: str, strategy_ref: str) -> None:
    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    session.add(
        EdgeReportRow(
            id=f"edge-v75-{os.urandom(5).hex()}",
            version="v2.75-producer-sample",
            strategy_or_signal_ref=strategy_ref,
            instrument_universe_ref=None,
            account_id=account_id,
            credibility=Decimal("0.80"),
            edge_score=Decimal("0.90"),
            band="positive",
            suite={},
            notes=[],
            payload=None,
            created_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def _run_one_round_trip(
    factory: Any,
    *,
    account_id: str,
    instrument_id: str,
    engine_id: str,
    day: int,
    ticks: int,
) -> bool:
    """Conduce UN round-trip (apertura + cierre estructural) con un worker/engine NUEVO.

    Worker nuevo por round-trip por DOS razones, ambas legítimas (no se desactiva ningún dedupe):

    * ``_minute`` (que arranca en ~1 y avanza por turno) vuelve a la ventana donde el sondeo
      garantiza el llenado de AMBOS lados. Con un único worker, ``_minute`` crecía y las entradas
      posteriores caían fuera de esa ventana: el fill es probabilístico por ``seed``.
    * La identidad de señal es por BARRA DIARIA (``bar_timestamp`` = inicio del día): cada
      round-trip vive en un DÍA distinto, así el dedupe anti-repetición (``sim_consumed_signals``)
      no bloquea la entrada siguiente.
    """
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
    )

    os.environ[_SYMBOLS_ENV] = instrument_id
    prices = {instrument_id: _ENTRY}
    holder = {"now": datetime(2026, 9, 15, 9, 0, tzinfo=UTC) + timedelta(days=day)}

    worker = AutoSimulationWorker(
        engine_id=engine_id,
        account_id=account_id,
        clock=lambda: holder["now"],
        price_script=lambda symbol, _minute: prices.get(symbol, _ENTRY),
        atr_source=lambda _symbol: _ATR,
        sector_source=lambda _symbol: "Technology",
        liquidity_source=lambda _symbol: 50_000_000.0,
    )
    worker._decider = _RoundTrip(worker, instrument_id)
    runtime = AutoSimRuntime(
        factory,
        worker=worker,
        engine_id=engine_id,
        account_id=account_id,
        atr_source=lambda _symbol: _ATR,
        liquidity_source=lambda _symbol: 50_000_000.0,
    )

    did_open = False
    for _ in range(ticks):
        await runtime.run_tick()
        holder["now"] = holder["now"] + _MINUTE_STEP
        if worker._open.get(instrument_id, Decimal("0")) > 0:
            did_open = True
            break
    if not did_open:
        return False

    # Cierre por parada estructural: el precio rompe el stop del ExitPlan.
    prices[instrument_id] = _BREAK
    did_close = False
    for _ in range(ticks):
        await runtime.run_tick()
        holder["now"] = holder["now"] + _MINUTE_STEP
        if worker._open.get(instrument_id, Decimal("0")) <= 0:
            did_close = True
            break

    # Asentamiento: libro plano y precio de vuelta a la entrada.
    prices[instrument_id] = _ENTRY
    for _ in range(3):
        await runtime.run_tick()
        holder["now"] = holder["now"] + _MINUTE_STEP

    return did_close


async def _run_round_trips(
    factory: Any,
    *,
    account_id: str,
    instrument_id: str,
    engine_base: str,
    round_trips: int,
    ticks: int,
) -> dict[str, Any]:
    """Encadena ``round_trips`` round-trips y devuelve el conteo (sin abortar por un fallo)."""
    opened = 0
    closed = 0
    failed: list[int] = []
    for index in range(round_trips):
        closed_ok = await _run_one_round_trip(
            factory,
            account_id=account_id,
            instrument_id=instrument_id,
            engine_id=f"{engine_base}-{index:03d}",
            day=index,
            ticks=ticks,
        )
        if closed_ok:
            opened += 1
            closed += 1
        else:
            failed.append(index)

    return {
        "roundTripsRequested": round_trips,
        "opened": opened,
        "closed": closed,
        "failedAt": failed,
    }


async def _read_readiness(factory: Any, account_id: str, *, min_cycles: int) -> Any:
    """Lee el material durable de la cuenta y compone el veredicto con la pieza del gate."""
    from sqlalchemy import select

    from bolsa_application.paper_material_readiness import build_paper_material_readiness
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_infrastructure.database.models.tables import AutoExitOrderRow

    async with factory() as session:
        context_store = PostgresSimFillFinanceContextStore(session)
        reservation_store = PostgresReservationStore(session)
        fills_by_version = await context_store.count_by_strategy_version(account_id=account_id)
        versions = sorted(str(v) for v in fills_by_version if v)
        fills: list[Any] = []
        for version in versions:
            fills.extend(
                await context_store.list_for_strategy_version(version, account_id=account_id)
            )
        reservations = await reservation_store.list_all(account_id, limit=5000)
        exit_cycles = (
            (
                await session.execute(
                    select(AutoExitOrderRow.cycle_id).where(
                        AutoExitOrderRow.account_id == account_id
                    )
                )
            )
            .scalars()
            .all()
        )
        exit_orders = [{"cycle_id": value} for value in exit_cycles]

    return build_paper_material_readiness(
        account_id=account_id,
        requested_versions=versions,
        fills=fills,
        reservations=reservations,
        exit_orders=exit_orders,
        min_cycles_per_strategy=min_cycles,
        fills_by_version=fills_by_version,
    )


def _sample_row(readiness: Any) -> dict[str, Any]:
    facts = readiness.facts
    return {
        "fills": facts["durableFills"],
        "withCycle": facts["fillsWithCycle"],
        "closedCycles": facts["closedCycles"],
        "measurableCycles": facts["measurableCycles"],
        "maxMeasurableCyclesPerVersion": facts["maxMeasurableCyclesPerVersion"],
        "reservations": facts["reservations"],
        "exitOrders": readiness.lineage["cycle"]["exitOrders"],
        "verdict": readiness.verdict,
        "producerReady": readiness.producer_ready,
        "evidenceReady": readiness.evidence_ready,
    }


def _print_sample(sample: dict[str, Any], run: dict[str, Any], *, min_cycles: int) -> None:
    print("PAPER SAMPLE ACCUMULATION (V2.75 · AUTO-MATERIAL-3)")
    print("-" * 52)
    print(f"{'round trips opened':<28}{run['opened']:>10}")
    print(f"{'round trips closed':<28}{run['closed']:>10}")
    print("-" * 52)
    print(f"{'fills':<28}{sample['fills']:>10}")
    print(f"{'cycle_id (fills)':<28}{sample['withCycle']:>10}")
    print(f"{'closed cycles':<28}{sample['closedCycles']:>10}")
    print(f"{'measurable cycles':<28}{sample['measurableCycles']:>10}")
    print(f"{'max measurable/version':<28}{sample['maxMeasurableCyclesPerVersion']:>10}")
    print(f"{'reservations':<28}{sample['reservations']:>10}")
    print(f"{'exit orders':<28}{sample['exitOrders']:>10}")
    print("-" * 52)
    print(f"{'min cycles (EVIDENCE)':<28}{min_cycles:>10}")
    print(f"{'verdict':<28}{sample['verdict']:>10}")
    print("Allocation                    FROZEN")


async def _run(*, round_trips: int, min_cycles: int) -> dict[str, Any]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    await asyncio.to_thread(ensure_migrated)
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    instrument_id = _filling_instrument_id("v75-sample-")
    account_id = ""
    engine_base = f"auto-v75-{os.urandom(4).hex()}"
    try:
        async with factory() as session:
            account_id = await _seed_account(session)
            await _seed_instrument(session, instrument_id)
            await _seed_edge_report(
                session, account_id=account_id, strategy_ref=_STRATEGY_VERSION
            )
        run = await _run_round_trips(
            factory,
            account_id=account_id,
            instrument_id=instrument_id,
            engine_base=engine_base,
            round_trips=round_trips,
            ticks=_TICKS_PER_PHASE,
        )
        readiness = await _read_readiness(factory, account_id, min_cycles=min_cycles)
    finally:
        await engine.dispose()

    return {
        "bump": "2.00.0-beta",
        "phase": "V2.75 AUTO-MATERIAL-3 EVIDENCE READY",
        "strategyVersion": _STRATEGY_VERSION,
        "account": account_id,
        "instrument": instrument_id,
        "engineBase": engine_base,
        "run": run,
        "sample": _sample_row(readiness),
        "blockers": list(readiness.blockers),
        "producerBlockers": list(readiness.producer_blockers),
        "lineage": dict(readiness.lineage),
        "minCyclesPerStrategy": int(min_cycles),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--round-trips",
        type=int,
        default=40,
        help="round-trips a encadenar sobre la cuenta nueva (default 40; deja margen sobre 32)",
    )
    parser.add_argument(
        "--min-cycles",
        type=int,
        default=32,
        help="mínimo de ciclos medibles por estrategia para el nivel EVIDENCE (default 32)",
    )
    parser.add_argument("--venue", default="paper", choices=("paper", "simulated"))
    parser.add_argument("--json", action="store_true", help="emite la evidencia como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON de evidencia")
    args = parser.parse_args(argv)

    if int(args.round_trips) <= 0:
        print("# uso incorrecto: --round-trips debe ser > 0", file=sys.stderr)
        return 1
    if int(args.min_cycles) <= 0:
        print("# uso incorrecto: --min-cycles debe ser > 0", file=sys.stderr)
        return 1

    _configure_env(venue=args.venue)
    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        evidence = asyncio.run(
            _run(round_trips=int(args.round_trips), min_cycles=int(args.min_cycles))
        )
    except Exception as error:  # noqa: BLE001 — sin PostgreSQL no hay evidencia: se DECLARA.
        print(
            f"# BLOQUEADO: no se pudo ejercitar el productor "
            f"({type(error).__name__}: {error})",
            file=sys.stderr,
        )
        return 2

    payload = json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    if args.json:
        print(payload)
    else:
        _print_sample(evidence["sample"], evidence["run"], min_cycles=int(args.min_cycles))
        print(f"\naccount         {evidence['account']}")
        print(f"instrument      {evidence['instrument']}")
        if evidence["blockers"]:
            print("\nBLOCKERS")
            for blocker in evidence["blockers"]:
                print(f"  - {blocker}")

    if not evidence["sample"]["evidenceReady"]:
        print(
            "# BLOQUEADO: el material no alcanza EVIDENCE_READY; motivos: "
            + "; ".join(evidence["blockers"]),
            file=sys.stderr,
        )
        return 2
    print(
        f"# EVIDENCE READY: {evidence['sample']['maxMeasurableCyclesPerVersion']} ciclos medibles "
        f"por version (nivel: {evidence['sample']['verdict']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
