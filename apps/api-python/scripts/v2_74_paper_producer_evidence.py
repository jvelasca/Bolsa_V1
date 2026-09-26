#!/usr/bin/env python3
"""V2.74 · AUTO-MATERIAL-2 — PAPER PRODUCER: evidencia de que el camino V2 produce material.

Qué mide: que el productor AUTO 2.0 (``AUTO_ENGINE_SIM_V2=ON`` + decider + watch + régimen) hace
nacer material PAPER **nuevo y limpio** con ESTRUCTURA completa —``cycle_id`` en los fills,
reservas de riesgo (``reserved_risk``), intents de salida con ``cycle_id``, ciclos cerrados y R
medible— sobre una **cuenta PAPER nueva**, sin tocar el material legacy congelado.

Cómo: conduce el camino REAL (``AutoSimRuntime`` → sesión por tick → ``worker.real_turn``) con un
decider determinista y un ``price_script`` controlado. Abre round-trips y los cierra (parada
estructural en el arm V2; venta del decider en el arm legacy), y después LEE el material durable
con la MISMA pieza que el gate (``build_paper_material_readiness``).

A/B estructural (solo ESTRUCTURA, no rendimiento): corre dos brazos y compara

                        LEGACY      V2
    fills                 X          X
    cycle_id              X          X
    closed cycles         X          X
    reservations          X          X
    exit orders           X          X
    R measurable          X          X

El arm LEGACY solo aporta la referencia de "cómo se veía el material sin el pipeline V2"; no se
toca ningún material histórico ni se rellena ningún ``cycle_id``.

Uso (desde la raíz del repo)::

    uv run --no-sync python apps/api-python/scripts/v2_74_paper_producer_evidence.py
    uv run --no-sync python apps/api-python/scripts/v2_74_paper_producer_evidence.py --json --out evidencia.json

Códigos de salida: ``0`` si el arm V2 queda ``PRODUCER_READY`` (estructura completa); ``2`` si no
(hay PostgreSQL pero el productor no acuña la estructura), ``1`` uso incorrecto.
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
#: Versión de estrategia con la que el decider determinista ATRIBUYE sus propuestas. Es la
#: MISMA vía que un decider de producción: ``DecisionPackage.source = "active-strategy:<v>"``
#: (`_strategy_version_from_source`). Sin atribución el fill nace con ``strategy_version_id``
#: NULL y el gate —que lee por versión pedida— no puede MEDIRLO (el material existiría pero
#: sería indecidible por estrategia). No se inventa linaje: se declara la versión, como en real.
_STRATEGY_VERSION = "v74-producer-orb-v1"
_STRATEGY_SOURCE = f"active-strategy:{_STRATEGY_VERSION}"
_ATR = 2.0  # 2 % de 100 ⇒ stop estructural en 100 − 1.5×2 = 97.
_ENTRY = 100.0
_BREAK = 96.0  # rompe el stop (97): dispara la salida estructural del arm V2.
_LOT = 100.0
_MINUTE_STEP = timedelta(minutes=1)


def _configure_env(*, venue: str) -> None:
    """Fija las env del productor. ``venue`` es SIM-only (paper/simulated)."""
    os.environ.update(
        {
            "AUTO_SIMULATION_WORKER_ENABLED": "1",
            "AUTO_ENGINE_SIM_SPINE_AUTO": "1",
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


def _filling_instrument_id(prefix: str, *, side: str = "buy") -> str:
    """Id determinista cuya orden ``side`` LLENA en toda la ventana de ticks (cola SIM).

    Misma barrida que ``test_auto_v2_durable_pg``: sin esto el sorteo del venue puede dejar la
    entrada sin llenar y el rojo sería espurio (no un defecto del productor).
    """
    from bolsa_application.simulated_broker import simulated_fill_schedule

    for n in range(64):
        candidate = f"{prefix}{n:010d}"
        fills = [
            simulated_fill_schedule(
                instrument_id=candidate,
                side=side,
                quantity=Decimal("100"),
                venue_order_id=f"probe-{candidate}-{minute}",
                seed=minute * 100_003 + sum(map(ord, candidate)) % 9999,
                fill_chunks=4,
                base_mid=_ENTRY,
            ).fills
            for minute in range(0, 9)
        ]
        if all(fills):
            return candidate
    raise AssertionError(
        f"ningún id determinista de {prefix} llena en la ventana de minutos con la cola SIM"
    )


class _RoundTrip:
    """Decider determinista: BUY mientras no hay posición; cierra según el arm.

    * arm V2 — HOLD con posición: la salida la dispara el ``ExitPlan`` (parada estructural) al
      bajar el precio, por el MISMO camino que un stop real.
    * arm LEGACY — SELL con posición: sin pipeline V2 la salida la pide el propio decider (es el
      comportamiento legacy que produjo los 761 fills sin ``cycle_id``).
    """

    def __init__(self, worker: Any, instrument_id: str, *, v2: bool) -> None:
        self._worker = worker
        self._symbol = instrument_id
        self._v2 = v2

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
        if self._v2:
            return DecisionPackage(action="HOLD", instrument_id=self._symbol, quantity=0)
        return DecisionPackage(
            action="SELL",
            instrument_id=self._symbol,
            quantity=float(held),
            source=_STRATEGY_SOURCE,
        )


async def _seed_account(session: Any) -> str:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"AUTO-V74-{os.urandom(4).hex()}",
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
            symbol=f"V74{os.urandom(3).hex().upper()}",
            yahoo_symbol=f"V74{os.urandom(4).hex()}",
            isin=None,
            name="AUTO-V74-Producer",
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


async def _seed_edge_report(session: Any, *, account_id: str, strategy_ref: str) -> str:
    from bolsa_infrastructure.database.models.tables import EdgeReportRow

    report_id = f"edge-v74-{os.urandom(5).hex()}"
    session.add(
        EdgeReportRow(
            id=report_id,
            version="v2.74-producer-test",
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
    return report_id


async def _run_arm(
    factory: Any,
    *,
    account_id: str,
    instrument_id: str,
    engine_id: str,
    v2: bool,
    ticks: int,
) -> dict[str, Any]:
    """Abre y cierra un round-trip por el camino REAL y devuelve un resumen del arm."""
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
    )

    # El watch del tick se lee por env en cada turno: cada arm vigila SU instrumento.
    os.environ[_SYMBOLS_ENV] = instrument_id
    prices = {instrument_id: _ENTRY}
    holder = {"now": datetime(2026, 9, 15, 9, 0, tzinfo=UTC)}

    worker = AutoSimulationWorker(
        engine_id=engine_id,
        account_id=account_id,
        clock=lambda: holder["now"],
        price_script=lambda symbol, _minute: prices.get(symbol, _ENTRY),
        atr_source=lambda _symbol: _ATR,
        sector_source=lambda _symbol: "Technology",
        liquidity_source=lambda _symbol: 50_000_000.0,
    )
    worker._decider = _RoundTrip(worker, instrument_id, v2=v2)
    runtime = AutoSimRuntime(
        factory,
        worker=worker,
        engine_id=engine_id,
        account_id=account_id,
        atr_source=lambda _symbol: _ATR,
        liquidity_source=lambda _symbol: 50_000_000.0,
    )

    opened = False
    for _ in range(ticks):
        await runtime.run_tick()
        holder["now"] = holder["now"] + _MINUTE_STEP
        if worker._open.get(instrument_id, Decimal("0")) > 0:
            opened = True
            break
    if not opened:
        return {"opened": False, "closed": False}

    closed = False
    if not v2:
        # El arm legacy cierra con la venta del decider en el tick siguiente.
        for _ in range(ticks):
            await runtime.run_tick()
            holder["now"] = holder["now"] + _MINUTE_STEP
            if worker._open.get(instrument_id, Decimal("0")) <= 0:
                closed = True
                break
    else:
        # El arm V2 cierra por parada estructural: el precio rompe el stop del ExitPlan.
        prices[instrument_id] = _BREAK
        for _ in range(ticks):
            await runtime.run_tick()
            holder["now"] = holder["now"] + _MINUTE_STEP
            if worker._open.get(instrument_id, Decimal("0")) <= 0:
                closed = True
                break
        prices[instrument_id] = _ENTRY

    return {"opened": opened, "closed": closed}


async def _read_structure(factory: Any, account_id: str, *, min_cycles: int) -> Any:
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
            fills.extend(await context_store.list_for_strategy_version(version, account_id=account_id))
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


def _structural_row(readiness: Any) -> dict[str, Any]:
    facts = readiness.facts
    lineage = readiness.lineage
    return {
        "fills": facts["durableFills"],
        "withCycle": facts["fillsWithCycle"],
        "closedCycles": facts["closedCycles"],
        "reservations": facts["reservations"],
        "exitOrders": lineage["cycle"]["exitOrders"],
        "measurableR": facts["measurableCycles"],
        "verdict": readiness.verdict,
        "producerReady": readiness.producer_ready,
        "evidenceReady": readiness.evidence_ready,
    }


def _print_ab(legacy: dict[str, Any], v2: dict[str, Any]) -> None:
    print("PAPER PRODUCER A/B (estructura, no rendimiento)")
    print("-" * 52)
    print(f"{'':<22}{'LEGACY':>10}{'V2':>10}")
    for key, label in (
        ("fills", "fills"),
        ("withCycle", "cycle_id"),
        ("closedCycles", "closed cycles"),
        ("reservations", "reservations"),
        ("exitOrders", "exit orders"),
        ("measurableR", "R measurable"),
    ):
        print(f"{label:<22}{str(legacy[key]):>10}{str(v2[key]):>10}")
    print("-" * 52)
    print(f"V2 verdict             {v2['verdict']}")
    print("Allocation             FROZEN")


async def _run(min_cycles: int) -> dict[str, Any]:
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
    try:
        legacy_instrument = _filling_instrument_id("v74-leg-")
        v2_instrument = _filling_instrument_id("v74-v2-")
        async with factory() as session:
            legacy_account = await _seed_account(session)
            await _seed_instrument(session, legacy_instrument)
            await _seed_edge_report(session, account_id=legacy_account, strategy_ref=_STRATEGY_VERSION)
        async with factory() as session:
            v2_account = await _seed_account(session)
            await _seed_instrument(session, v2_instrument)
            await _seed_edge_report(session, account_id=v2_account, strategy_ref=_STRATEGY_VERSION)

        # Arm LEGACY: pipeline V2 OFF (camino que produjo el material sin linaje).
        os.environ["AUTO_ENGINE_SIM_V2"] = "0"
        legacy_run = await _run_arm(
            factory,
            account_id=legacy_account,
            instrument_id=legacy_instrument,
            engine_id=f"auto-v74-leg-{os.urandom(4).hex()}",
            v2=False,
            ticks=12,
        )
        legacy_readiness = await _read_structure(factory, legacy_account, min_cycles=min_cycles)

        # Arm V2: pipeline AUTO 2.0 ON (debe acuñar linaje, reservas y salidas).
        os.environ[_SYMBOLS_ENV] = v2_instrument
        os.environ["AUTO_ENGINE_SIM_V2"] = "1"
        v2_run = await _run_arm(
            factory,
            account_id=v2_account,
            instrument_id=v2_instrument,
            engine_id=f"auto-v74-v2-{os.urandom(4).hex()}",
            v2=True,
            ticks=12,
        )
        v2_readiness = await _read_structure(factory, v2_account, min_cycles=min_cycles)
    finally:
        await engine.dispose()

    legacy = _structural_row(legacy_readiness)
    v2 = _structural_row(v2_readiness)
    return {
        "bump": "1.99.0-beta",
        "phase": "V2.74 AUTO-MATERIAL-2 PAPER PRODUCER",
        "accounts": {"legacy": legacy_account, "v2": v2_account},
        "instruments": {"legacy": legacy_instrument, "v2": v2_instrument},
        "runs": {"legacy": legacy_run, "v2": v2_run},
        "ab": {"legacy": legacy, "v2": v2},
        "v2Lineage": dict(v2_readiness.lineage),
        "v2Verdict": v2_readiness.verdict,
        "v2ProducerReady": v2_readiness.producer_ready,
        "v2EvidenceReady": v2_readiness.evidence_ready,
        "v2Blockers": list(v2_readiness.blockers),
        "v2ProducersBlockers": list(v2_readiness.producer_blockers),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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

    if int(args.min_cycles) <= 0:
        print("# uso incorrecto: --min-cycles debe ser > 0", file=sys.stderr)
        return 1

    _configure_env(venue=args.venue)
    if sys.platform == "win32":  # pragma: no cover — psycopg async no soporta ProactorEventLoop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        evidence = asyncio.run(_run(int(args.min_cycles)))
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
        _print_ab(evidence["ab"]["legacy"], evidence["ab"]["v2"])
        print(f"\nlegacy account  {evidence['accounts']['legacy']}")
        print(f"v2 account      {evidence['accounts']['v2']}")
        if evidence["v2Blockers"]:
            print("\nBLOCKERS")
            for blocker in evidence["v2Blockers"]:
                print(f"  - {blocker}")

    if not evidence["v2ProducerReady"]:
        print(
            "# BLOQUEADO: el camino V2 no dejó material con estructura completa; motivos: "
            + "; ".join(evidence["v2Blockers"]),
            file=sys.stderr,
        )
        return 2
    print(
        f"# PRODUCER READY: material V2 con estructura completa (nivel: {evidence['v2Verdict']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
