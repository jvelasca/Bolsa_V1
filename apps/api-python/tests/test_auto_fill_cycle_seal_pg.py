"""Cierre del ÚLTIMO punto abierto de auditoría: el sello ``executionId -> cycle_id``.

La auditoría no pudo OBSERVAR el sellado del ciclo en la fila durable
``sim_fill_finance_context.cycle_id`` porque nunca corrió un ciclo AUTO real en la BD.
Esta suite lo CIERRA sin mercado vivo y sin proceso de scheduler:

1. **Sello del settle (columna física).** Dado un ``cycle_id`` CONOCIDO, el camino real de
   liquidación (``submit_simulated_order`` hacia ``apply_simulated_order_once`` hacia
   ``persist_fill_finance_context``) escribe, ANTES de mover dinero, una fila por fill cuya
   columna ``sim_fill_finance_context.cycle_id`` es EXACTAMENTE ese valor (no nulo). Se lee
   desde una sesión NUEVA: certifica la COLUMNA DURABLE, no la RAM del proceso.
2. **La liberación ``BY_FILL`` se apoya en ese contexto.** La reconciliación durable
   (``_v2_reconcile_reservations``, regla 1) solo libera ``RELEASED_BY_FILL`` a partir de los
   hechos que produce ``read_applied_fill_facts``, que **dropea** todo evento ``APPLIED`` cuya
   fila de contexto falte. Con el contexto persistido hay liberación por fill; sin él, el
   MISMO fill ``APPLIED`` NO produce una liberación por fill (ni un fill fabricado).
3. **Modo estructural (``context_store is None``).** Se PINNEA la asimetría del sospechoso: con
   ``finance_applier=None`` el schedule confirmado cuenta como ``applied`` en RAM y libera la
   reserva ``RELEASED_BY_FILL``, pero NO hay fila ``APPLIED`` ni contexto durable. Es
   alcanzable solo por composición inyectada (el runtime de producción compone applier y
   contexto JUNTOS en ``_compose_real_stores``); se declara su comportamiento observable en vez
   de fingir que el ledger lo ve.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_FILL_CYCLE_SEAL_PG_REQUIRED=1`` un skip silencioso es un FALLO DURO. NUNCA abre el
bridge LIVE (venue ``paper``). Limpia TODO lo que crea, incluidas las RESERVAS (la auditoría
encontró ``portfolio_reservations`` huérfanas por tests PG que borraban fills pero no
reservas).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import bolsa_api.background.auto_simulation_worker as worker_module
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_FILL_CYCLE_SEAL_PG_REQUIRED"

#: Mismo troceo que el worker real (``_FILL_CHUNKS``): el schedule del probe es el del motor.
_FILL_CHUNKS = int(getattr(worker_module, "_FILL_CHUNKS", 4))
_QTY = Decimal("100")
_ENTRY = Decimal("100")


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para el sello del ciclo AUTO pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (sello del ciclo AUTO) no disponible: {exc}")


@pytest_asyncio.fixture
async def seal_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    if _DOTENV.exists():
        load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


class _MoneyApplier:
    """Applier hermético: confirma cada fill una sola vez (materializa en el ledger durable)."""

    def __init__(self) -> None:
        self.applied: list[str] = []

    async def __call__(self, execution: Any) -> bool:
        self.applied.append(execution.execution_id)
        return True


def _filling_seed(
    instrument_id: str,
    *,
    side: str = "buy",
    quantity: Decimal = _QTY,
) -> int:
    """Seed determinista cuya orden LLEGA A LLENAR (barrido puro, sin BD ni proceso).

    El ruido del venue depende SOLO de ``(seed, side, instrument_id)``: buscar aquí el seed
    es la MISMA aritmética que corre ``submit_simulated_order``, no una copia de la fórmula.
    """
    from bolsa_application.simulated_broker import simulated_fill_schedule

    for seed in range(500):
        result = simulated_fill_schedule(
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            venue_order_id=f"probe-{seed}",
            seed=seed,
            fill_chunks=_FILL_CHUNKS,
            base_mid=float(_ENTRY),
        )
        if result.fills:
            return seed
    raise AssertionError(
        f"ningún seed <500 llena {instrument_id!r} ({side}); revisar draw_queue_noise"
    )


def _filling_symbol_for_tick(tick: int, *, side: str = "buy") -> str:
    """Símbolo cuyo fill (seed del MOTOR = ``fill_seed(tick, symbol)``) sí llena.

    Es el análogo de ``_filling_instrument_id`` de los tests PG, pero anclado al tick de
    barra que calcula el propio worker (no a un literal de reloj).
    """
    from bolsa_application.simulated_broker import fill_seed, simulated_fill_schedule

    for n in range(256):
        candidate = f"sealsym{n:04d}"
        result = simulated_fill_schedule(
            instrument_id=candidate,
            side=side,
            quantity=_QTY,
            venue_order_id=f"probe-{candidate}",
            seed=fill_seed(tick, candidate),
            fill_chunks=_FILL_CHUNKS,
            base_mid=float(_ENTRY),
        )
        if result.fills:
            return candidate
    raise AssertionError(
        f"ningún símbolo llena en el tick de barra {tick} ({side}); revisar fill_seed/noise"
    )


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    *,
    execution_ids: tuple[str, ...],
    reservation_ids: tuple[str, ...],
) -> None:
    """Borra EXACTAMENTE lo creado: fills, contextos y (sobre todo) RESERVAS.

    La auditoría encontró ``portfolio_reservations`` huérfanas porque algunos tests PG
    borraban sus fills pero no sus reservas. Aquí las reservas son de primera clase.
    """
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        PortfolioReservationRow,
        SimFillFinanceContextRow,
    )

    async with factory() as session:
        if execution_ids:
            await session.execute(
                delete(SimFillFinanceContextRow).where(
                    SimFillFinanceContextRow.execution_id.in_(execution_ids)
                )
            )
            await session.execute(
                delete(ExecutionEventRow).where(ExecutionEventRow.execution_id.in_(execution_ids))
            )
        if reservation_ids:
            await session.execute(
                delete(PortfolioReservationRow).where(
                    PortfolioReservationRow.reservation_id.in_(reservation_ids)
                )
            )
        await session.commit()


def _reservation(reservation_id: str, *, account_id: str, instrument_id: str, cycle_id: str) -> Any:
    """Reserva viva de COMPRA, fechada una hora atrás (dentro de la ventana del fill)."""
    from bolsa_analytics.cognitive.portfolio_reservation import build_reservation

    created = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    return build_reservation(
        reservation_id=reservation_id,
        account_id=account_id,
        tick_id=created,
        instrument_id=instrument_id,
        side="buy",
        sector="tech",
        quantity=float(_QTY),
        entry=float(_ENTRY),
        reserved_cash=float(_QTY * _ENTRY),
        reserved_risk=50.0,
        created_at=created,
        cycle_id=cycle_id,
    )


async def _reconcile(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    engine_id: str,
    instrument_id: str,
    cycle_id: str,
    reservation_id: str,
    context_store: Any,
    exec_store: Any,
) -> None:
    """Reconcilia (regla 1) la reserva indicada con los stores PG de la sesión viva."""
    from bolsa_application.reservation_store import PostgresReservationStore

    async with factory() as session:
        reservation_store = PostgresReservationStore(session)
        stored = await reservation_store.get(reservation_id)
        assert stored is not None, "la reserva debe existir antes de reconciliar"
        worker = AutoSimulationWorker(
            engine_id=engine_id,
            account_id=account_id,
            exec_store=exec_store,
            context_store=context_store,
            reservation_store=reservation_store,
        )
        worker._v2_owned_reservations = {reservation_id}  # noqa: SLF001 — es de esta sesión.
        worker._v2_reservations = (stored,)  # noqa: SLF001
        await worker._v2_reconcile_reservations(  # noqa: SLF001
            startup=True,
            attribute_fills=True,
            only_ids=frozenset({reservation_id}),
        )


@pytest.mark.asyncio
async def test_settlement_stamps_cycle_id_on_the_durable_finance_row(
    seal_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """(a) El settle persiste, por fill, ``sim_fill_finance_context.cycle_id`` EXACTO.

    El ``cycle_id`` es un literal CONOCIDO (como el ``cyc-<hash>`` que acuña
    ``auto_v2_entry`` y reenvía ``_settle``); la aserción se hace sobre la COLUMNA FÍSICA
    leída desde una sesión nueva.
    """
    from bolsa_application.execution_event import PostgresExecutionEventStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_application.simulated_settlement import submit_simulated_order
    from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

    account_id = f"acc-seal-{uuid.uuid4().hex[:10]}"
    engine_id = f"eng-seal-{uuid.uuid4().hex[:10]}"
    instrument_id = f"inst-seal-{uuid.uuid4().hex[:10]}"
    cycle_id = f"cyc-{uuid.uuid4().hex[:16]}"
    seed = _filling_seed(instrument_id)
    execution_ids: tuple[str, ...] = ()
    try:
        async with seal_pg_factory() as session:
            exec_store = PostgresExecutionEventStore(session)
            context_store = PostgresSimFillFinanceContextStore(session)
            result, outcomes = await submit_simulated_order(
                exec_store,
                instrument_id=instrument_id,
                side="buy",
                quantity=_QTY,
                account_id=account_id,
                venue="paper",
                seed=seed,
                base_mid=float(_ENTRY),
                fill_chunks=_FILL_CHUNKS,
                order_id="seal-order",
                engine_id=engine_id,
                logical_order_id="seal-logical",
                owner="seal-test",
                apply_finance=_MoneyApplier(),
                context_store=context_store,
                strategy_version_id="ver-seal",
                cycle_id=cycle_id,
            )
            assert result.fills, "la fixture debe producir al menos un fill determinista"
            execution_ids = tuple(f.execution_id for f in result.fills)
            assert all(
                outcomes.get(execution_id) in {"applied", "already_applied"}
                for execution_id in execution_ids
            ), f"el fill debe materializar dinero: {outcomes}"

        # ── Columna DURABLE, leída desde una sesión NUEVA ─────────────────────────
        async with seal_pg_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(SimFillFinanceContextRow).where(
                            SimFillFinanceContextRow.execution_id.in_(execution_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(rows) == len(execution_ids), (
            "debe haber UNA fila de contexto por fill liquidado "
            f"(esperadas={len(execution_ids)}, reales={len(rows)})"
        )
        assert {row.cycle_id for row in rows} == {cycle_id}, (
            "cada fila debe declarar EXACTAMENTE el cycle_id del settle "
            f"(real={sorted({row.cycle_id for row in rows})!r})"
        )
        assert all(row.cycle_id for row in rows), "el cycle_id sellado NUNCA es nulo"
        assert {row.side for row in rows} == {"buy"}
        assert {row.account_id for row in rows} == {account_id}
    finally:
        await _cleanup(seal_pg_factory, execution_ids=execution_ids, reservation_ids=())


@pytest.mark.asyncio
async def test_by_fill_release_is_driven_by_the_persisted_cycle_context(
    seal_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """(b) POSITIVO — con el contexto persistido, la reconciliación libera ``BY_FILL``.

    El fill va por el camino REAL de liquidación (contexto + dinero): la regla 1 de la
    reconciliación lo ve vía ``read_applied_fill_facts`` y libera la reserva de SU ciclo con
    ``RELEASED_BY_FILL``.
    """
    from bolsa_application.applied_fills import read_applied_fill_facts
    from bolsa_application.execution_event import PostgresExecutionEventStore
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_application.simulated_settlement import submit_simulated_order

    account_id = f"acc-sealpos-{uuid.uuid4().hex[:10]}"
    engine_id = f"eng-sealpos-{uuid.uuid4().hex[:10]}"
    instrument_id = f"inst-sealpos-{uuid.uuid4().hex[:10]}"
    cycle_id = f"cyc-{uuid.uuid4().hex[:16]}"
    reservation_id = f"RES-sealpos-{uuid.uuid4().hex[:10]}"
    seed = _filling_seed(instrument_id)
    execution_ids: tuple[str, ...] = ()
    try:
        async with seal_pg_factory() as session:
            exec_store = PostgresExecutionEventStore(session)
            context_store = PostgresSimFillFinanceContextStore(session)
            result, outcomes = await submit_simulated_order(
                exec_store,
                instrument_id=instrument_id,
                side="buy",
                quantity=_QTY,
                account_id=account_id,
                venue="paper",
                seed=seed,
                base_mid=float(_ENTRY),
                fill_chunks=_FILL_CHUNKS,
                order_id="sealpos-order",
                engine_id=engine_id,
                logical_order_id="sealpos-logical",
                owner="seal-test",
                apply_finance=_MoneyApplier(),
                context_store=context_store,
                cycle_id=cycle_id,
            )
            assert result.fills, "la fixture debe producir al menos un fill"
            execution_ids = tuple(f.execution_id for f in result.fills)
            filled_total = sum((abs(f.qty_delta) for f in result.fills), Decimal("0"))
            await PostgresReservationStore(session).save(
                _reservation(
                    reservation_id,
                    account_id=account_id,
                    instrument_id=instrument_id,
                    cycle_id=cycle_id,
                )
            )

            # El hecho durable existe y lleva el ciclo: `read_applied_fill_facts` lo ve.
            read = await read_applied_fill_facts(exec_store, context_store, account_id)
            assert read.measurement == "COMPLETE", read.error
            assert len(read.facts) == len(execution_ids)
            assert {fact.cycle_id for fact in read.facts} == {cycle_id}, (
                "el hecho leído por el ledger debe declarar el ciclo persistido"
            )

            await _reconcile(
                seal_pg_factory,
                account_id=account_id,
                engine_id=engine_id,
                instrument_id=instrument_id,
                cycle_id=cycle_id,
                reservation_id=reservation_id,
                context_store=context_store,
                exec_store=exec_store,
            )

        async with seal_pg_factory() as session:
            released = await PostgresReservationStore(session).get(reservation_id)
        assert released is not None
        assert released.status == "RELEASED_BY_FILL", (
            f"con contexto persistido la liberación debe ser BY_FILL (real={released.status})"
        )
        assert released.release_reason == "fill"
        assert Decimal(str(released.released_qty)) == filled_total, (
            "la liberación por fill cubre EXACTAMENTE lo materializado del ciclo"
        )
    finally:
        await _cleanup(
            seal_pg_factory,
            execution_ids=execution_ids,
            reservation_ids=(reservation_id,),
        )


@pytest.mark.asyncio
async def test_missing_context_does_not_yield_a_by_fill_release(
    seal_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """(b) NEGATIVO — sin fila de contexto, el fill ``APPLIED`` NO libera ``BY_FILL``.

    Mismo camino de dinero, pero SIN ``context_store``: ``read_applied_fill_facts`` dropea el
    evento (contexto ausente hacia medición no afirmable), así que la reconciliación no puede
    fabricar un fill del ciclo y la reserva NO se libera por fill.
    """
    from bolsa_application.applied_fills import read_applied_fill_facts
    from bolsa_application.execution_event import PostgresExecutionEventStore
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore
    from bolsa_application.simulated_settlement import submit_simulated_order

    account_id = f"acc-sealneg-{uuid.uuid4().hex[:10]}"
    engine_id = f"eng-sealneg-{uuid.uuid4().hex[:10]}"
    instrument_id = f"inst-sealneg-{uuid.uuid4().hex[:10]}"
    cycle_id = f"cyc-{uuid.uuid4().hex[:16]}"
    reservation_id = f"RES-sealneg-{uuid.uuid4().hex[:10]}"
    seed = _filling_seed(instrument_id)
    execution_ids: tuple[str, ...] = ()
    try:
        async with seal_pg_factory() as session:
            exec_store = PostgresExecutionEventStore(session)
            context_store = PostgresSimFillFinanceContextStore(session)
            # Dinero SÍ se mueve, pero el CONTEXTO no se persiste (``context_store=None``).
            result, outcomes = await submit_simulated_order(
                exec_store,
                instrument_id=instrument_id,
                side="buy",
                quantity=_QTY,
                account_id=account_id,
                venue="paper",
                seed=seed,
                base_mid=float(_ENTRY),
                fill_chunks=_FILL_CHUNKS,
                order_id="sealneg-order",
                engine_id=engine_id,
                logical_order_id="sealneg-logical",
                owner="seal-test",
                apply_finance=_MoneyApplier(),
                context_store=None,
                cycle_id=cycle_id,
            )
            assert result.fills, "la fixture debe producir al menos un fill"
            execution_ids = tuple(f.execution_id for f in result.fills)
            assert all(
                outcomes.get(execution_id) in {"applied", "already_applied"}
                for execution_id in execution_ids
            ), "el fill materializa dinero aunque no haya contexto"

            await PostgresReservationStore(session).save(
                _reservation(
                    reservation_id,
                    account_id=account_id,
                    instrument_id=instrument_id,
                    cycle_id=cycle_id,
                )
            )

            # La lectura del ledger NO es afirmable y NO produce fact: el contexto falta.
            read = await read_applied_fill_facts(exec_store, context_store, account_id)
            assert read.measurement != "COMPLETE", (
                "un APPLIED sin contexto NO puede leerse como libro completo"
            )
            assert read.facts == (), (
                "el ledger no puede fabricar un hecho a partir de un fill sin contexto"
            )

            await _reconcile(
                seal_pg_factory,
                account_id=account_id,
                engine_id=engine_id,
                instrument_id=instrument_id,
                cycle_id=cycle_id,
                reservation_id=reservation_id,
                context_store=context_store,
                exec_store=exec_store,
            )

        async with seal_pg_factory() as session:
            after = await PostgresReservationStore(session).get(reservation_id)
        assert after is not None
        assert after.status != "RELEASED_BY_FILL", (
            "sin contexto durable la reserva NO puede declararse liberada POR FILL "
            f"(real={after.status!r})"
        )
        assert float(after.released_qty) == 0.0, "no se libera un lote sin hecho durable"
    finally:
        await _cleanup(
            seal_pg_factory,
            execution_ids=execution_ids,
            reservation_ids=(reservation_id,),
        )


@pytest.mark.asyncio
async def test_structural_mode_releases_by_fill_without_durable_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(3) Modo ESTRUCTURAL: se PINNEA la asimetría ``context_store is None`` (hermético).

    ``finance_applier=None`` ⇒ ``_settle`` declara ``structural=True`` y cuenta el schedule
    confirmado como ``applied``: la reserva se libera ``RELEASED_BY_FILL`` por el camino
    caliente. Pero NO hay fila ``APPLIED`` ni contexto durable (el evento queda en ``RETRY`` y
    ``read_applied_fill_facts`` no ve NADA). Es alcanzable solo por composición inyectada: el
    runtime de producción (``_compose_real_stores``) compone SIEMPRE applier + contexto, de
    modo que este hueco no se abre en el motor real. Se fija aquí para que un cambio de
    comportamiento (p.ej. negarse a liberar por fill sin contexto) sea visible.
    """
    from bolsa_application.applied_fills import read_applied_fill_facts
    from bolsa_application.execution_event import InMemoryExecutionEventStore
    from bolsa_application.reservation_store import InMemoryReservationStore
    from bolsa_application.sim_durable_store import InMemorySimFillFinanceContextStore

    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    account_id = f"acc-sealstruct-{uuid.uuid4().hex[:10]}"
    engine_id = f"eng-sealstruct-{uuid.uuid4().hex[:10]}"
    cycle_id = f"cyc-{uuid.uuid4().hex[:16]}"
    reservation_id = f"RES-sealstruct-{uuid.uuid4().hex[:10]}"

    exec_store = InMemoryExecutionEventStore()
    reservation_store = InMemoryReservationStore()
    contexts = InMemorySimFillFinanceContextStore()
    worker = AutoSimulationWorker(
        engine_id=engine_id,
        account_id=account_id,
        exec_store=exec_store,
        context_store=None,  # el sospechoso: sin contexto durable...
        reservation_store=reservation_store,  # ...pero con libro de reservas.
        finance_applier=None,  # ...y sin dinero: modo ESTRUCTURAL.
    )
    instrument_id = _filling_symbol_for_tick(worker._v2_bar_tick())  # noqa: SLF001
    reservation = _reservation(
        reservation_id,
        account_id=account_id,
        instrument_id=instrument_id,
        cycle_id=cycle_id,
    )
    await reservation_store.save(reservation)
    worker._v2_owned_reservations = {reservation_id}  # noqa: SLF001
    worker._v2_reservations = (reservation,)  # noqa: SLF001

    settlement = await worker._settle(  # noqa: SLF001
        "buy", instrument_id, _QTY, cycle_id=cycle_id
    )
    assert settlement.structural is True, "sin finance_applier el settle es estructural"
    assert settlement.applied, "el schedule confirmado cuenta como applied en estructural"

    await worker._v2_release_reservations_for_fill(  # noqa: SLF001
        symbol=instrument_id,
        filled_qty=settlement.applied_qty,
        at="2026-09-17T09:00:00Z",
        side="buy",
    )

    released = await reservation_store.get(reservation_id)
    assert released is not None
    # Comportamiento OBSERVABLE y (hoy) DECLARADO: libera por fill sin hecho durable.
    assert released.status == "RELEASED_BY_FILL", (
        "el modo estructural libera por fill aunque no exista contexto durable"
    )
    assert released.release_reason == "fill"

    # La otra cara: NADA durable respalda ese fill. La fila queda en RETRY (no APPLIED) y la
    # lectura del ledger no ve ningún hecho (ni un fill fabricado).
    listed = await exec_store.list_applied(account_id, limit=10)
    assert listed == [], "el modo estructural no materializa filas APPLIED"
    read = await read_applied_fill_facts(exec_store, contexts, account_id)
    assert read.facts == (), "sin contexto durable el ledger no ve el fill"
    # Sin filas APPLIED el libro está vacío (COMPLETE de vacío): lo que se certifica es que la
    # reserva declaró un fill que el ledger durable NO puede ver.
    assert read.ledger.facts_applied == 0, "el ledger durable no cuenta el fill estructural"
