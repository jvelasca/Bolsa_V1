"""AUTO-1b — reservas durables de cartera sobre PostgreSQL real (migración 042).

Qué certifica este fichero, y por qué solo se puede certificar contra PG real:

1. **La migración 042 es aditiva y reversible** — ``downgrade`` a ``041`` retira la tabla
   y sus tres índices (más el índice ``(account_id, status)`` de ``execution_events``) y
   ``upgrade head`` los vuelve a crear. Sin roundtrip, "reversible" sería una afirmación
   de lectura del código, no un hecho medido.
2. **La reserva SOBREVIVE al reinicio** — una reserva escrita por un store muere con el
   PROCESO, no con la BD: otro store (otra sesión) la ve viva con sus siete dimensiones.
   Es exactamente el compromiso que V2.40.4 no podía afirmar (la reserva era intra-tick y
   anónima y moría al volver de ``plan_v2_tick``).
3. **La reconciliación de arranque la libera al materializar** — un ``APPLIED`` posterior
   al alta libera por fill; con fill parcial la liberación es parcial y la cola sigue
   siendo capital comprometido.
4. **``RETRY`` sigue siendo capital RESERVADO** — con una traza no aplicada, la
   reconciliación NO libera (la orden está en vuelo) y el capital se cuenta UNA vez: la
   reserva cubre la traza en lugar de sumarse a ella.
5. **Una orden que murió sin llenarse libera el capital** — sin traza ninguna, la reserva
   se libera por reinicio. Y la liberación es idempotente: nunca se libera dos veces.

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
_PREVIOUS_REVISION = "041_unique_natural_keys"
_TABLE = "portfolio_reservations"
_INDICES: tuple[str, ...] = (
    "portfolio_reservations_account_status_idx",
    "portfolio_reservations_account_sector_idx",
    "portfolio_reservations_account_created_idx",
    "execution_events_account_status_idx",
)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para las reservas de cartera pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (reservas AUTO-1) no disponible: {exc}")


@pytest_asyncio.fixture
async def reservation_pg_factory() -> async_sessionmaker[AsyncSession]:
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
    found = connection.execute(
        text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
        {"n": name},
    ).scalar_one_or_none()
    return found is not None


def _table_present(connection: Any, name: str) -> bool:
    found = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=:t"
        ),
        {"t": name},
    ).scalar_one_or_none()
    return found is not None


def _reservation_id() -> str:
    return f"RES-pg-{uuid.uuid4().hex[:12]}"


def _reservation(
    *,
    account_id: str,
    instrument_id: str,
    created_at: datetime,
    quantity: float = 100.0,
    entry: float = 100.0,
    risk: float = 600.0,
    sector: str = "banca",
    side: str = "buy",
    cycle_id: str | None = None,
) -> Any:
    """Una reserva de compra cuantificada, con la forma exacta del tick real."""
    from bolsa_analytics.cognitive.portfolio_reservation import build_reservation

    return build_reservation(
        reservation_id=_reservation_id(),
        account_id=account_id,
        tick_id=created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        instrument_id=instrument_id,
        side=side,
        sector=sector,
        quantity=quantity,
        entry=entry,
        stop=entry - 6.0,
        reserved_cash=round(quantity * entry, 4),
        reserved_risk=risk,
        created_at=created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        cycle_id=cycle_id,
    )


async def _insert_trace(
    session: AsyncSession,
    *,
    execution_id: str,
    account_id: str,
    instrument_id: str,
    qty: Decimal,
    status: str,
    at: datetime,
) -> None:
    """Traza duradera del fill (identidad + contexto financiero), como el settlement."""
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
            status=status,
            applied_at=at if status == "APPLIED" else None,
        )
    )
    session.add(
        SimFillFinanceContextRow(
            execution_id=execution_id,
            instrument_id=instrument_id,
            side="buy",
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
    execution_ids: tuple[str, ...],
) -> None:
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
        await session.execute(
            delete(PortfolioReservationRow).where(PortfolioReservationRow.account_id == account_id)
        )
        await session.commit()


def _store(session: AsyncSession) -> Any:
    from bolsa_application.reservation_store import PostgresReservationStore

    return PostgresReservationStore(session)


def _worker(session: AsyncSession, *, account_id: str) -> Any:
    """Worker mínimo con los tres stores reales que la reconciliación necesita.

    No se conduce un turno (no hay decider ni gate): se ejercita el punto de entrada de
    la reconciliación de arranque, que es lo que AUTO-1b pone bajo certificación. El
    ``AutoSimulationWorker`` real usa estos mismos stores por sesión (``real_turn``).
    """
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
    from bolsa_application.execution_event import PostgresExecutionEventStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

    return AutoSimulationWorker(
        engine_id="auto-sim",
        account_id=account_id,
        exec_store=PostgresExecutionEventStore(session),
        context_store=PostgresSimFillFinanceContextStore(session),
        reservation_store=_store(session),
    )


# ── 1) La migración es aditiva y reversible ───────────────────────────────────────


@pytest.mark.asyncio
async def test_migration_042_roundtrip_creates_and_drops_the_reservation_book(
    reservation_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``downgrade`` a 041 retira tabla e índices; ``upgrade head`` los recrea."""
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
            assert _table_present(connection, _TABLE), "042 debe dejar la tabla creada"
            for index_name in _INDICES:
                assert _index_present(connection, index_name), f"falta {index_name}"

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, _PREVIOUS_REVISION)
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            assert not _table_present(connection, _TABLE), "downgrade retira la tabla"
            for index_name in _INDICES:
                assert not _index_present(connection, index_name), (
                    f"downgrade debe retirar {index_name}"
                )

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            assert _table_present(connection, _TABLE), "upgrade recrea la tabla"
            for index_name in _INDICES:
                assert _index_present(connection, index_name), f"upgrade debe recrear {index_name}"
        assert alembic_head() != _PREVIOUS_REVISION
    finally:
        engine.dispose()


# ── 2) La reserva sobrevive al reinicio y se libera por fill ──────────────────────


@pytest.mark.asyncio
async def test_reservation_survives_restart_and_is_released_by_the_materialized_fill(
    reservation_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    account_id = f"acc-res-{uuid.uuid4().hex[:10]}"
    instrument_id = f"inst-res-{uuid.uuid4().hex[:10]}"
    created = datetime.now(UTC) - timedelta(minutes=5)
    execution_ids = (
        f"{instrument_id}-fill-1",
        f"{instrument_id}-fill-2",
    )
    reservation = _reservation(
        account_id=account_id, instrument_id=instrument_id, created_at=created
    )
    try:
        # Proceso 1: el tick compromete el capital y lo hace DURABLE.
        async with reservation_pg_factory() as session:
            store = _store(session)
            assert await store.save(reservation) is True
            assert await store.save(reservation) is False, "el alta es idempotente"
            await session.commit()

        # Proceso 2 (reinicio): otro store ve la reserva VIVA con sus dimensiones.
        async with reservation_pg_factory() as session:
            live = await _store(session).list_live(account_id)
            assert [row.reservation_id for row in live] == [reservation.reservation_id]
            assert live[0].remaining_qty == pytest.approx(100.0)
            assert live[0].reserved_cash == pytest.approx(10_000.0)
            assert live[0].reserved_risk == pytest.approx(600.0)
            assert live[0].sector == "banca"

        # El fill materializa 40 de 100 (posterior al alta): liberación PARCIAL.
        async with reservation_pg_factory() as session:
            await _insert_trace(
                session,
                execution_id=execution_ids[0],
                account_id=account_id,
                instrument_id=instrument_id,
                qty=Decimal("40"),
                status="APPLIED",
                at=datetime.now(UTC),
            )

        async with reservation_pg_factory() as session:
            worker = _worker(session, account_id=account_id)
            await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001
            live = await _store(session).list_live(account_id)
            assert len(live) == 1
            assert live[0].remaining_qty == pytest.approx(60.0)
            assert live[0].released_qty == pytest.approx(40.0)
            assert live[0].reserved_cash == pytest.approx(6_000.0)
            assert live[0].is_live is True, "la cola sigue siendo capital comprometido"

        # El resto se materializa: la reserva se libera ENTERA por fill.
        async with reservation_pg_factory() as session:
            await _insert_trace(
                session,
                execution_id=execution_ids[1],
                account_id=account_id,
                instrument_id=instrument_id,
                qty=Decimal("60"),
                status="APPLIED",
                at=datetime.now(UTC),
            )

        async with reservation_pg_factory() as session:
            worker = _worker(session, account_id=account_id)
            await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001
            assert await _store(session).list_live(account_id) == []

        # La fila NO se borra: historia auditable con estado y cantidad liberada.
        async with reservation_pg_factory() as session:
            rows = await _store(session).list_all(account_id)
            assert len(rows) == 1
            assert rows[0].status == "RELEASED_BY_FILL"
            assert rows[0].released_qty == pytest.approx(100.0)
            assert rows[0].reserved_cash == pytest.approx(0.0)
    finally:
        await _cleanup(
            reservation_pg_factory,
            account_id=account_id,
            execution_ids=execution_ids,
        )


# ── 3) RETRY sigue siendo capital reservado (y no se cuenta dos veces) ────────────


@pytest.mark.asyncio
async def test_retry_trace_keeps_the_reservation_as_reserved_capital(
    reservation_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    account_id = f"acc-res-{uuid.uuid4().hex[:10]}"
    instrument_id = f"inst-res-{uuid.uuid4().hex[:10]}"
    created = datetime.now(UTC) - timedelta(minutes=5)
    execution_id = f"{instrument_id}-retry"
    reservation = _reservation(
        account_id=account_id, instrument_id=instrument_id, created_at=created
    )
    try:
        async with reservation_pg_factory() as session:
            await _store(session).save(reservation)

        async with reservation_pg_factory() as session:
            await _insert_trace(
                session,
                execution_id=execution_id,
                account_id=account_id,
                instrument_id=instrument_id,
                qty=Decimal("100"),
                status="RETRY",
                at=datetime.now(UTC),
            )

        async with reservation_pg_factory() as session:
            worker = _worker(session, account_id=account_id)
            await worker._v2_refresh_open_orders()  # noqa: SLF001 — libro de trazas.
            await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001
            live = await _store(session).list_live(account_id)
            assert len(live) == 1, "la orden sigue EN VUELO: no se libera"
            assert live[0].remaining_qty == pytest.approx(100.0)

            from bolsa_analytics.cognitive.open_order import summarize_open_orders

            book = worker._v2_pending_open_orders()  # noqa: SLF001
            summary = summarize_open_orders(book, equity=100_000.0)
            assert summary.reserved_cash == pytest.approx(10_000.0), (
                "la reserva cubre la traza: el mismo capital no se cuenta dos veces"
            )
            assert summary.pending_risk == pytest.approx(600.0)
            assert worker._v2_pending_book_measurement() == "COMPLETE"  # noqa: SLF001
    finally:
        await _cleanup(
            reservation_pg_factory,
            account_id=account_id,
            execution_ids=(execution_id,),
        )


# ── 4) Una orden que murió sin llenarse libera el capital (idempotente) ───────────


@pytest.mark.asyncio
async def test_reservation_of_a_dead_order_is_released_on_restart(
    reservation_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    account_id = f"acc-res-{uuid.uuid4().hex[:10]}"
    instrument_id = f"inst-res-{uuid.uuid4().hex[:10]}"
    created = datetime.now(UTC) - timedelta(minutes=5)
    reservation = _reservation(
        account_id=account_id, instrument_id=instrument_id, created_at=created
    )
    try:
        async with reservation_pg_factory() as session:
            await _store(session).save(reservation)

        async with reservation_pg_factory() as session:
            worker = _worker(session, account_id=account_id)
            await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001
            assert await _store(session).list_live(account_id) == []

        async with reservation_pg_factory() as session:
            rows = await _store(session).list_all(account_id)
            assert rows[0].status == "RELEASED_BY_RESTART"
            assert rows[0].remaining_qty == pytest.approx(0.0)
            assert rows[0].reserved_cash == pytest.approx(0.0)

        # Idempotente: la segunda pasada por el arranque no encuentra nada que liberar.
        async with reservation_pg_factory() as session:
            worker = _worker(session, account_id=account_id)
            await worker._v2_reconcile_reservations(startup=True)  # noqa: SLF001
            rows = await _store(session).list_all(account_id)
            assert len(rows) == 1
            assert rows[0].status == "RELEASED_BY_RESTART"
    finally:
        await _cleanup(reservation_pg_factory, account_id=account_id, execution_ids=())


# ── 5) AUTO-9 — el lector por ciclo devuelve el ciclo entero y no inventa huecos ──


@pytest.mark.asyncio
async def test_cycle_reader_returns_the_whole_cycle_and_declares_the_untraceable(
    reservation_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Paso 2 del plan ``v2.50``: leer el material de un ciclo por su ``cycle_id``.

    El lector no elige el denominador de R: devuelve la reserva de ENTRADA y la de SALIDA.
    Y no rellena huecos: un ciclo inexistente, un conjunto vacío o una fila sin ciclo
    (anterior a ``2.47``) devuelven ``[]``, para que el informe declare ``UNKNOWN``.
    """
    account_id = f"acc-cyc-{uuid.uuid4().hex[:10]}"
    instrument_id = f"inst-cyc-{uuid.uuid4().hex[:10]}"
    cycle_id = f"cyc-{uuid.uuid4().hex[:12]}"
    created = datetime.now(UTC) - timedelta(minutes=5)
    entry = _reservation(
        account_id=account_id,
        instrument_id=instrument_id,
        created_at=created,
        cycle_id=cycle_id,
    )
    exit_row = _reservation(
        account_id=account_id,
        instrument_id=instrument_id,
        created_at=created + timedelta(minutes=1),
        side="sell",
        risk=0.0,
        cycle_id=cycle_id,
    )
    historic = _reservation(
        account_id=account_id,
        instrument_id=instrument_id,
        created_at=created + timedelta(minutes=2),
    )
    try:
        async with reservation_pg_factory() as session:
            store = _store(session)
            assert await store.save(entry) is True
            assert await store.save(exit_row) is True
            assert await store.save(historic) is True
            await session.commit()

        async with reservation_pg_factory() as session:
            store = _store(session)
            rows = await store.list_by_cycle_ids(account_id, [cycle_id])
            assert [row.reservation_id for row in rows] == [
                entry.reservation_id,
                exit_row.reservation_id,
            ]
            assert {row.side for row in rows} == {"buy", "sell"}
            assert rows[0].reserved_risk == pytest.approx(600.0)

            # AUTO-20B — la lectura se puede PAGINAR sin saltos ni repeticiones: el orden es
            # total, así que concatenar páginas de 1== el universo completo (es la costura que
            # usa el exportador para no truncar reservas en silencio).
            paged = [
                row
                for offset in range(len(rows))
                for row in await store.list_by_cycle_ids(
                    account_id, [cycle_id], limit=1, offset=offset
                )
            ]
            assert [row.reservation_id for row in paged] == [row.reservation_id for row in rows]
            # ``offset`` más allá del material no repite las últimas páginas.
            assert (
                await store.list_by_cycle_ids(account_id, [cycle_id], limit=1, offset=99)
                == []
            )

        async with reservation_pg_factory() as session:
            store = _store(session)
            # Un ciclo que no existe NO se inventa; y el hueco tampoco se rellena con la
            # reserva histórica sin ciclo (``NULL`` no es un ciclo).
            assert await store.list_by_cycle_ids(account_id, [f"cyc-{uuid.uuid4().hex[:12]}"]) == []
            assert await store.list_by_cycle_ids(account_id, []) == []
            assert await store.list_by_cycle_ids(account_id, ["", "   "]) == []
            # El histórico sin ciclo sigue siendo legible por el canal que sí lo cubre.
            every = await store.list_all(account_id)
            assert len(every) == 3
    finally:
        await _cleanup(reservation_pg_factory, account_id=account_id, execution_ids=())
