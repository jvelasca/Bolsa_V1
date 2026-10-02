"""AUTO Operational Monitor (``M1``+``M2``) sobre PostgreSQL real.

Qué certifica este fichero, y por qué solo se puede certificar contra PG real:

1. **La cadena durable se proyecta de verdad.** Una reserva, sus fills (con ``cycle_id``) y
   las entradas del spine (``auto_entry_decision``/``auto_reservation_claim``/
   ``auto_reservation_reconciliation``) escritas por OTRA sesión reaparecen en el DTO del
   monitor: ``SIGNAL``/``TOP_N``/``RISK`` alcanzados con su ``rank``, ``RESERVATION``/
   ``FILL``/``CYCLE_CLOSED`` con su PnL, y el ownership/concurrencia medidos.
2. **Ausencia ⇒ ``unknown`` declarado, nunca ``0``.** Un ciclo con reserva pero SIN journal
   ni claim se declara: ``SIGNAL`` ``unknown``, ``ownerSession`` ``None`` + ``UNKNOWN`` y las
   notas del DTO. Es la regla de honestidad del monitor medida contra filas reales.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_OPERATIONAL_MONITOR_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre
el bridge LIVE (todo es SIMULATED).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_OPERATIONAL_MONITOR_PG_REQUIRED"
_ENGINE_ID = "auto-sim-monitor-pg"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para el monitor AUTO pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (monitor AUTO) no disponible: {exc}")


@pytest_asyncio.fixture
async def monitor_pg_factory() -> async_sessionmaker[AsyncSession]:
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


async def _wipe(factory: async_sessionmaker[AsyncSession], account_id: str) -> None:
    async with factory() as session:
        for table in (
            "sim_fill_finance_context",
            "portfolio_reservations",
            "decision_journal_entries",
        ):
            await session.execute(
                text(f"DELETE FROM {table} WHERE account_id = :account_id"),
                {"account_id": account_id},
            )
        await session.commit()


def _reservation(*, reservation_id: str, cycle_id: str, account_id: str, instrument: str) -> Any:
    from bolsa_analytics.cognitive.portfolio_reservation import PortfolioReservation

    return PortfolioReservation(
        reservation_id=reservation_id,
        account_id=account_id,
        instrument_id=instrument,
        side="buy",
        quantity=10.0,
        entry=100.0,
        stop=95.0,
        reserved_cash=1000.0,
        reserved_risk=250.0,
        strategy_version_id="orb-1",
        created_at="2026-10-01T09:00:00+00:00",
        cycle_id=cycle_id,
    )


async def _seed_fill(
    session: AsyncSession,
    *,
    account_id: str,
    cycle_id: str,
    instrument: str,
    side: str,
    price: float,
    reference_mid: float,
    execution_id: str | None = None,
) -> None:
    from bolsa_application.sim_durable_store import (
        PostgresSimFillFinanceContextStore,
        SimFillFinanceContext,
    )

    store = PostgresSimFillFinanceContextStore(session, autocommit=False)
    await store.save(
        SimFillFinanceContext(
            # ``execution_id`` determinista: el store sella su propio ``created_at`` (``_now()``),
            # así que ``cycles_from_fills`` ordena por ``(created_at, execution_id)``. Un id
            # aleatorio podía hacer leer la venta antes de su compra y descartar el ciclo (test
            # flaky); prefijar ``...-buy``/``...-sell`` fija el orden FIFO.
            execution_id=execution_id or f"EX-{uuid.uuid4().hex[:12]}",
            instrument_id=instrument,
            side=side,
            quantity=Decimal("10"),
            price=Decimal(str(price)),
            reference_mid=Decimal(str(reference_mid)),
            account_id=account_id,
            cycle_id=cycle_id,
            created_at=datetime(2026, 10, 1, 15, 0, tzinfo=UTC),
        )
    )


async def _seed_journal(
    session: AsyncSession,
    *,
    account_id: str,
    cycle_id: str,
    instrument: str,
) -> None:
    from bolsa_application.auto_operational_audit import (
        REASON_GRACE_WINDOW_KEEP,
        RECONCILIATION_KEEP,
        build_reservation_claim_entry,
        build_reservation_reconciliation_entry,
    )
    from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    repository = SqlAlchemyJournalRepository(session)
    suffix = cycle_id.removeprefix("cyc-")
    await repository.append(
        DecisionJournalEntryRecord(
            id=f"JNL-{uuid.uuid4().hex[:12]}",
            decision_id=f"dec-{suffix}",
            event_type="auto_entry_decision",
            actor="auto-sim",
            created_at="2026-10-01T09:00:00Z",
            # ``session_id`` apunta por FK a ``decision_sessions``; la sesión del motor vive en
            # el ``caller`` de los claims (ver ``auto_operational_audit``).
            session_id=None,
            account_id=account_id,
            instrument_id=instrument,
            payload={
                "event": "auto_entry_decision",
                "cycleId": cycle_id,
                "instrumentId": instrument,
                "strategyVersion": "orb-1",
                "rank": 1,
                "opportunityScore": 0.9,
            },
        )
    )
    claim = build_reservation_claim_entry(
        reservation_id=f"RES-dec-{suffix}",
        cycle_id=cycle_id,
        claimed=True,
        actor="auto-sim",
        session_id="sess-owner",
        as_of="2026-10-01T09:00:00Z",
        account_id=account_id,
        instrument_id=instrument,
    )
    assert claim is not None
    await repository.append(claim)
    reconciliation = build_reservation_reconciliation_entry(
        reservation_id=f"RES-dec-{suffix}",
        cycle_id=cycle_id,
        decision=RECONCILIATION_KEEP,
        reason=REASON_GRACE_WINDOW_KEEP,
        mine=False,
        aged=False,
        grace_window_seconds=61.0,
        actor="auto-sim",
        session_id="sess-owner",
        as_of="2026-10-01T09:10:00Z",
        account_id=account_id,
        instrument_id=instrument,
    )
    assert reconciliation is not None
    await repository.append(reconciliation)
    await session.commit()


@pytest.mark.asyncio
async def test_monitor_projects_a_real_durable_chain(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_application.auto_operational_monitor import read_operational_monitor
    from bolsa_application.reservation_store import PostgresReservationStore

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    instrument = "AAA"
    await _wipe(monitor_pg_factory, account_id)
    try:
        async with monitor_pg_factory() as session:
            reservations = PostgresReservationStore(session, autocommit=True)
            assert await reservations.save_claim(
                _reservation(
                    reservation_id=f"RES-dec-{suffix}",
                    cycle_id=cycle_id,
                    account_id=account_id,
                    instrument=instrument,
                )
            )
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument=instrument,
                side="buy",
                price=100.0,
                reference_mid=99.9,
                execution_id=f"EX-{suffix}-buy",
            )
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument=instrument,
                side="sell",
                price=110.0,
                reference_mid=110.1,
                execution_id=f"EX-{suffix}-sell",
            )
            await _seed_journal(
                session, account_id=account_id, cycle_id=cycle_id, instrument=instrument
            )

        # Otra sesión (el monitor) lee lo que acaba de quedar durable.
        async with monitor_pg_factory() as session:
            dto = await read_operational_monitor(
                session, account_id, engine_id=_ENGINE_ID, cycle_id=cycle_id, grace_seconds=61.0
            )

        cycle = dto["cycles"][0]
        steps = {step["id"]: step for step in cycle["steps"]}
        assert steps["SIGNAL"]["state"] == "reached"
        assert steps["TOP_N"]["state"] == "reached"
        assert any(fact["key"] == "rank" and fact["value"] == 1 for fact in steps["TOP_N"]["facts"])
        assert steps["RESERVATION"]["state"] == "reached"
        assert steps["FILL"]["state"] == "reached"
        assert cycle["closed"] is True
        assert steps["CYCLE_CLOSED"]["state"] == "reached"
        # Un ciclo cerrado NO demuestra settlement durable: se declara, no se finge.
        assert steps["SETTLEMENT"]["state"] == "unknown"
        assert steps["SETTLEMENT"]["note"] == "settlement_not_durable"

        reservation = dto["reservations"][0]
        assert reservation["ownerSession"] == "sess-owner"
        assert reservation["ownerMeasurement"] == "COMPLETE"
        concurrency = dto["concurrency"]
        assert concurrency["claimAttempts"] == 1
        assert concurrency["successfulClaims"] == 1
        assert concurrency["lostClaims"] == 0
        assert concurrency["raceConflicts"] == 0
        assert concurrency["claimAttemptsMeasurement"] == "COMPLETE"
        assert concurrency["graceWindowKeeps"] == 1
        assert concurrency["graceWindowKeepsMeasurement"] == "COMPLETE"
        assert "decision_journal_not_durable" not in dto["notes"]
        assert "claim_audit_not_durable" not in dto["notes"]
    finally:
        await _wipe(monitor_pg_factory, account_id)


@pytest.mark.asyncio
async def test_monitor_declares_absence_when_the_spine_has_no_trace(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Una reserva real sin journal ni claim: los pasos y el dueño se declaran ``unknown``."""
    from bolsa_application.auto_operational_monitor import read_operational_monitor
    from bolsa_application.reservation_store import PostgresReservationStore

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    await _wipe(monitor_pg_factory, account_id)
    try:
        async with monitor_pg_factory() as session:
            reservations = PostgresReservationStore(session, autocommit=True)
            assert await reservations.save_claim(
                _reservation(
                    reservation_id=f"RES-dec-{suffix}",
                    cycle_id=cycle_id,
                    account_id=account_id,
                    instrument="BBB",
                )
            )

        async with monitor_pg_factory() as session:
            dto = await read_operational_monitor(
                session, account_id, engine_id=_ENGINE_ID, cycle_id=cycle_id, grace_seconds=61.0
            )

        steps = {step["id"]: step for step in dto["cycles"][0]["steps"]}
        assert steps["SIGNAL"]["state"] == "unknown"
        assert steps["SIGNAL"]["measurement"] == "UNKNOWN"
        assert steps["SIGNAL"]["note"] is not None
        reservation = dto["reservations"][0]
        assert reservation["ownerSession"] is None
        assert reservation["ownerMeasurement"] == "UNKNOWN"
        assert "decision_journal_not_durable" in dto["notes"]
        assert "owner_session_not_durable" in dto["notes"]
    finally:
        await _wipe(monitor_pg_factory, account_id)
