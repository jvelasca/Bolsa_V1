"""AUTO-3 cierre de fiabilidad (V2.43.3) — identidad de salida y parada dura en PG real.

Qué certifica este fichero, y por qué solo se puede certificar contra PostgreSQL real:

1. **La migración 043 es aditiva y reversible** — ``downgrade`` a ``042`` retira
    ``auto_kill_state``, ``auto_exit_orders``, sus tres índices y la columna
    ``portfolio_reservations.exit_order_id`` (con su índice); ``upgrade head`` lo recrea.
    Sin roundtrip, "reversible" sería una lectura del código, no un hecho medido.
2. **El INTENT de salida sobrevive al reinicio** — la identidad (``exit_order_id``) la
    escribe un proceso y la ve OTRO (otra sesión) con su estado y su cola. Es el cierre del
    P0-2: antes la identidad era un contador de proceso que volvía a 0.
3. **El HALT durable sobrevive al reinicio** — ``engaged=True`` escrito en una sesión lo lee
    la siguiente; la liberación exige ``reconciliation_id`` y también queda persistida. Es
    el cierre del P0-1: ``WORKER 1 → KILL → CRASH → WORKER 2`` ya no olvida la parada.
4. **La reserva enlaza con su INTENT y la reconciliación los casa** — la columna
    ``exit_order_id`` viaja por el store; un fill parcial de la reserva de salida deja el
    intent ``PARTIAL`` (``filled``/``remaining`` separadas) sin mintear un segundo intent.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_RESERVATION_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el
bridge LIVE (todo es SIMULATED).
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
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_RESERVATION_PG_REQUIRED"
_PREVIOUS_REVISION = "042_portfolio_reservations"
_ENGINE_ID = "auto-sim"
_KILL_TABLE = "auto_kill_state"
_EXIT_TABLE = "auto_exit_orders"
_RESERVATIONS = "portfolio_reservations"
_EXIT_ORDER_COLUMN = "exit_order_id"
_TABLES: tuple[str, ...] = (_KILL_TABLE, _EXIT_TABLE)
_INDICES: tuple[str, ...] = (
    "auto_kill_state_account_engaged_idx",
    "auto_exit_orders_account_state_idx",
    "auto_exit_orders_account_instrument_idx",
    "portfolio_reservations_exit_order_id_idx",
)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la identidad de salida AUTO-3 pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (identidad de salida AUTO-3) no disponible: {exc}")


@pytest_asyncio.fixture
async def exit_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

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


def _index_present(connection: Any, name: str) -> bool:
    return (
        connection.execute(
            text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
            {"n": name},
        ).scalar_one_or_none()
        is not None
    )


def _table_present(connection: Any, name: str) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=:t"
            ),
            {"t": name},
        ).scalar_one_or_none()
        is not None
    )


def _column_present(connection: Any, table: str, column: str) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
            ),
            {"t": table, "c": column},
        ).scalar_one_or_none()
        is not None
    )


def _exit_order_id() -> str:
    return f"EXIT-pg-{uuid.uuid4().hex[:12]}"


def _build_order(*, exit_order_id: str, account_id: str, instrument_id: str) -> Any:
    from bolsa_analytics.cognitive.exit_order import build_exit_order

    order = build_exit_order(
        exit_order_id=exit_order_id,
        instrument_id=instrument_id,
        side="sell",
        requested_qty=100.0,
        account_id=account_id,
        engine_id=_ENGINE_ID,
        created_at="2026-09-15T09:01:00Z",
        updated_at="2026-09-15T09:01:00Z",
    )
    assert order is not None
    return order


def _sell_reservation(*, exit_order_id: str, account_id: str, instrument_id: str) -> Any:
    from bolsa_analytics.cognitive.portfolio_reservation import build_reservation

    return build_reservation(
        reservation_id=f"exit:{exit_order_id}",
        account_id=account_id,
        tick_id="2026-09-15T09:01:00Z",
        instrument_id=instrument_id,
        side="sell",
        quantity=100.0,
        entry=100.0,
        sector="tech",
        reserved_cash=0.0,
        reserved_risk=0.0,
        created_at="2026-09-15T09:01:00Z",
        exit_order_id=exit_order_id,
    )


async def _insert_sell_trace(
    session: AsyncSession,
    *,
    execution_id: str,
    account_id: str,
    instrument_id: str,
    qty: Decimal,
    at: datetime,
) -> None:
    """Traza duradera de un fill de VENTA (identidad + contexto financiero), APPLIED."""
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        SimFillFinanceContextRow,
    )

    session.add(
        ExecutionEventRow(
            execution_id=execution_id,
            order_id=f"ord-{execution_id}",
            venue="simulated",
            account_id=account_id,
            venue_order_id=f"sim-{execution_id}",
            fill_seq=1,
            qty=qty,
            captured_at=at,
            status="APPLIED",
            applied_at=at,
        )
    )
    session.add(
        SimFillFinanceContextRow(
            execution_id=execution_id,
            instrument_id=instrument_id,
            side="sell",
            quantity=qty,
            price=Decimal("100"),
            account_id=account_id,
            venue="simulated",
            created_at=at,
        )
    )
    await session.commit()


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    execution_ids: tuple[str, ...] = (),
) -> None:
    from bolsa_infrastructure.database.models.tables import (
        AutoExitOrderRow,
        AutoKillStateRow,
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
                delete(ExecutionEventRow).where(
                    ExecutionEventRow.execution_id.in_(execution_ids)
                )
            )
        await session.execute(
            delete(PortfolioReservationRow).where(
                PortfolioReservationRow.account_id == account_id
            )
        )
        await session.execute(
            delete(AutoExitOrderRow).where(AutoExitOrderRow.account_id == account_id)
        )
        await session.execute(
            delete(AutoKillStateRow).where(AutoKillStateRow.account_id == account_id)
        )
        await session.commit()


def _worker(session: AsyncSession, *, account_id: str) -> Any:
    """Worker mínimo con los stores reales que la reconciliación necesita (sin turno)."""
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
    from bolsa_application.execution_event import PostgresExecutionEventStore
    from bolsa_application.exit_order_store import PostgresExitOrderStore
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

    return AutoSimulationWorker(
        engine_id=_ENGINE_ID,
        account_id=account_id,
        exec_store=PostgresExecutionEventStore(session),
        context_store=PostgresSimFillFinanceContextStore(session),
        reservation_store=PostgresReservationStore(session),
        exit_order_store=PostgresExitOrderStore(session),
    )


# ── 1) La migración 043 es aditiva y reversible ───────────────────────────────────


@pytest.mark.asyncio
async def test_migration_043_roundtrip_creates_and_drops_kill_state_and_exit_identity(
    exit_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``downgrade`` a 042 retira tablas, índices y columna; ``upgrade head`` los recrea."""
    pytest.importorskip("alembic")
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)

    from alembic import command
    from sqlalchemy import create_engine

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import _alembic_config, alembic_head

    get_settings.cache_clear()
    settings = get_settings()
    url = settings.database_url
    assert url is not None
    url = url.replace("postgresql://", "postgresql+psycopg://", 1).split("?", 1)[0]

    engine = create_engine(url)
    cfg = _alembic_config()
    try:
        with engine.connect() as connection:
            for table in _TABLES:
                assert _table_present(connection, table), f"043 debe crear {table}"
            for index_name in _INDICES:
                assert _index_present(connection, index_name), f"falta {index_name}"
            assert _column_present(connection, _RESERVATIONS, _EXIT_ORDER_COLUMN), (
                "043 debe enlazar la reserva con su intent"
            )

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, _PREVIOUS_REVISION)
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            for table in _TABLES:
                assert not _table_present(connection, table), f"downgrade retira {table}"
            assert not _column_present(connection, _RESERVATIONS, _EXIT_ORDER_COLUMN), (
                "downgrade retira la columna exit_order_id"
            )
            for index_name in _INDICES:
                assert not _index_present(connection, index_name), (
                    f"downgrade debe retirar {index_name}"
                )

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            for table in _TABLES:
                assert _table_present(connection, table), f"upgrade recrea {table}"
            for index_name in _INDICES:
                assert _index_present(connection, index_name), (
                    f"upgrade debe recrear {index_name}"
                )
        assert alembic_head() != _PREVIOUS_REVISION
    finally:
        engine.dispose()


# ── 2) El INTENT de salida sobrevive al reinicio ──────────────────────────────────


@pytest.mark.asyncio
async def test_exit_intent_survives_a_restart_and_keeps_its_queue(
    exit_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Un proceso escribe el INTENT; otro (otra sesión) lo ve con estado y cola."""
    from bolsa_application.exit_order_store import PostgresExitOrderStore

    account_id = f"acc-exit-{uuid.uuid4().hex[:10]}"
    instrument_id = f"inst-exit-{uuid.uuid4().hex[:10]}"
    exit_order_id = _exit_order_id()
    order = _build_order(
        exit_order_id=exit_order_id, account_id=account_id, instrument_id=instrument_id
    )
    reservation_id = f"exit:{exit_order_id}"
    try:
        # Proceso 1: mintea la identidad y la reserva (INTENT → RESERVED).
        async with exit_pg_factory() as session:
            store = PostgresExitOrderStore(session)
            assert await store.save(order) is True, "el alta es la primera escritura"
            assert await store.save(order) is False, "el re-alta es idempotente (UPDATE)"
            await store.save(order.with_reserved(reservation_id, at="2026-09-15T09:01:05Z"))
            await session.commit()

        # Proceso 2 (reinicio): otra sesión ve el INTENT con su cola comprometida.
        async with exit_pg_factory() as session:
            store = PostgresExitOrderStore(session)
            restored = await store.get(exit_order_id)
            assert restored is not None, "la identidad duradera sobrevive al reinicio"
            assert restored.state == "RESERVED"
            assert restored.reservation_id == reservation_id
            assert restored.requested_qty == pytest.approx(100.0)
            assert restored.remaining_qty == pytest.approx(100.0)
            open_orders = await store.list_open(account_id)
            assert [row.exit_order_id for row in open_orders] == [exit_order_id]

        # Un fill PARCIAL (40 de 100) deja el INTENT con la cola viva.
        async with exit_pg_factory() as session:
            store = PostgresExitOrderStore(session)
            restored = await store.get(exit_order_id)
            assert restored is not None
            await store.save(restored.apply_fill(40.0, at="2026-09-15T09:02:00Z"))
            await session.commit()

        async with exit_pg_factory() as session:
            store = PostgresExitOrderStore(session)
            partial = await store.get(exit_order_id)
            assert partial is not None
            assert partial.state == "PARTIAL"
            assert partial.filled_qty == pytest.approx(40.0)
            assert partial.remaining_qty == pytest.approx(60.0)
            assert partial.is_open is True
            # Sigue habiendo UNA identidad: el reinicio no mintea una segunda.
            assert len(await store.list_open(account_id)) == 1
    finally:
        await _cleanup(exit_pg_factory, account_id=account_id)


# ── 3) El HALT durable sobrevive al reinicio y la liberación es persistida ───────


@pytest.mark.asyncio
async def test_kill_state_survives_a_restart_and_release_is_persisted(
    exit_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``WORKER 1 → KILL → CRASH → WORKER 2`` ya no olvida la parada (P0-1)."""
    from bolsa_analytics.cognitive.hard_kill_switch import HardKillSwitch
    from bolsa_application.kill_switch_store import (
        KillState,
        PostgresKillSwitchStore,
    )

    account_id = f"acc-kill-{uuid.uuid4().hex[:10]}"
    try:
        async with exit_pg_factory() as session:
            store = PostgresKillSwitchStore(session)
            assert await store.load(account_id, _ENGINE_ID) is None, (
                "sin fila = la parada nunca se activó (la ausencia es información)"
            )
            await store.save(
                KillState(
                    account_id=account_id,
                    engine_id=_ENGINE_ID,
                    engaged=True,
                    reason="RECONCILIATION_FAILURE",
                    engaged_at="2026-09-15T09:00:00Z",
                    engagement_id="eng-1",
                    reengagements=0,
                    updated_at="2026-09-15T09:00:00Z",
                )
            )
            await session.commit()

        # Proceso 2 (reinicio): el HALT se restaura desde la BD.
        async with exit_pg_factory() as session:
            state = await PostgresKillSwitchStore(session).load(account_id, _ENGINE_ID)
            assert state is not None
            assert state.engaged is True
            assert state.reason == "RECONCILIATION_FAILURE"
            assert state.engagement_id == "eng-1"
            # El latch durable rehidrata el ``HardKillSwitch`` puro con su motivo.
            latch = HardKillSwitch.from_persisted(
                engaged=state.engaged,
                reason=state.reason,
                engagement_id=state.engagement_id,
                reengagements=state.reengagements,
            )
            assert latch.engaged is True

        # La liberación exige reconciliación explícita y también se persiste.
        async with exit_pg_factory() as session:
            store = PostgresKillSwitchStore(session)
            state = await store.load(account_id, _ENGINE_ID)
            assert state is not None
            await store.save(
                KillState(
                    account_id=account_id,
                    engine_id=_ENGINE_ID,
                    engaged=False,
                    reason=state.reason,
                    engaged_at=state.engaged_at,
                    engagement_id=state.engagement_id,
                    reengagements=state.reengagements,
                    released_at="2026-09-15T09:10:00Z",
                    release_actor="operator",
                    release_reconciliation_id="recon-42",
                    updated_at="2026-09-15T09:10:00Z",
                )
            )
            await session.commit()

        async with exit_pg_factory() as session:
            released = await PostgresKillSwitchStore(session).load(account_id, _ENGINE_ID)
            assert released is not None
            assert released.engaged is False
            assert released.release_reconciliation_id == "recon-42"
            assert released.release_actor == "operator"
    finally:
        await _cleanup(exit_pg_factory, account_id=account_id)


# ── 4) La reserva enlaza con su INTENT y la reconciliación los casa ───────────────


@pytest.mark.asyncio
async def test_reservation_links_to_its_intent_and_partial_fill_updates_it_once(
    exit_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Un fill parcial de la reserva de salida deja el INTENT ``PARTIAL`` sin duplicarlo."""
    from bolsa_application.exit_order_store import PostgresExitOrderStore
    from bolsa_application.reservation_store import PostgresReservationStore

    account_id = f"acc-link-{uuid.uuid4().hex[:10]}"
    instrument_id = f"inst-link-{uuid.uuid4().hex[:10]}"
    exit_order_id = _exit_order_id()
    reservation_id = f"exit:{exit_order_id}"
    execution_id = f"{instrument_id}-sell-1"
    created = datetime.now(UTC) - timedelta(minutes=5)
    order = _build_order(
        exit_order_id=exit_order_id, account_id=account_id, instrument_id=instrument_id
    )
    reservation = _sell_reservation(
        exit_order_id=exit_order_id, account_id=account_id, instrument_id=instrument_id
    )
    try:
        # Proceso 1: INTENT reservado + reserva de SALIDA con el enlace durable.
        async with exit_pg_factory() as session:
            await PostgresExitOrderStore(session).save(
                order.with_reserved(reservation_id, at="2026-09-15T09:01:05Z")
            )
            await PostgresReservationStore(session).save(reservation)
            await session.commit()

        # El enlace viaja por el store: la columna no se pierde en el roundtrip.
        async with exit_pg_factory() as session:
            live = await PostgresReservationStore(session).list_live(account_id)
            assert [row.reservation_id for row in live] == [reservation_id]
            assert live[0].exit_order_id == exit_order_id

        # Un fill de VENTA de 40 (posterior al alta) materializa parte de la salida.
        async with exit_pg_factory() as session:
            await _insert_sell_trace(
                session,
                execution_id=execution_id,
                account_id=account_id,
                instrument_id=instrument_id,
                qty=Decimal("40"),
                at=created + timedelta(minutes=1),
            )

        # Proceso 2 (reinicio): la reconciliación casa la reserva con el fill y actualiza
        # el INTENT por su identidad; la cola sigue siendo capital comprometido.
        async with exit_pg_factory() as session:
            worker = _worker(session, account_id=account_id)
            await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001
            live = await PostgresReservationStore(session).list_live(account_id)
            assert len(live) == 1
            assert live[0].remaining_qty == pytest.approx(60.0)
            assert live[0].released_qty == pytest.approx(40.0)

            store = PostgresExitOrderStore(session)
            intent = await store.get(exit_order_id)
            assert intent is not None
            assert intent.state == "PARTIAL"
            assert intent.filled_qty == pytest.approx(40.0)
            assert intent.remaining_qty == pytest.approx(60.0)
            assert len(await store.list_open(account_id)) == 1, (
                "un fill NO mintea una segunda identidad de salida"
            )
    finally:
        await _cleanup(
            exit_pg_factory, account_id=account_id, execution_ids=(execution_id,)
        )
