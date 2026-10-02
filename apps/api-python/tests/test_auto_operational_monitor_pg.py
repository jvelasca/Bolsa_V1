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


def _reservation(
    *,
    reservation_id: str,
    cycle_id: str,
    account_id: str,
    instrument: str,
    release_reason: str | None = None,
    status: str = "OPEN",
) -> Any:
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
        release_reason=release_reason,
        status=status,
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
    price_source: str | None = None,
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
            # v2.88.25 — la FUENTE que construyó el precio (migración 047).
            price_source=price_source,
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
                # El motor que produce la decisión (A4): el header la lee scoped por
                # ``account_id + engine_id``.
                "engineId": _ENGINE_ID,
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

        # ``lastDecisionAt`` sale de la lectura GLOBAL del spine, no de los ciclos visibles.
        assert dto["header"]["lastDecisionAt"] == "2026-10-01T09:00:00Z"
        assert dto["header"]["lastDecisionMeasurement"] == "COMPLETE"

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


@pytest.mark.asyncio
async def test_monitor_claim_counts_come_from_the_aggregate_not_the_page(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Con más claims que la página, ``claimAttempts`` es el TOTAL real (COMPLETE), no la página.

    Es la grieta que la auditoría v2.88.22 señaló: ``limit`` truncaba el universo y el DTO podía
    declararlo ``COMPLETE``. El agregado en base cuenta TODO el universo sin cargar los eventos;
    el desglose de carrera se declara ``PARTIAL`` porque ningún claim declaró ``conflict``.
    """
    from bolsa_application.auto_operational_audit import build_reservation_claim_entry
    from bolsa_application.auto_operational_monitor import read_operational_monitor
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    total_claims = 120
    await _wipe(monitor_pg_factory, account_id)
    try:
        async with monitor_pg_factory() as session:
            repository = SqlAlchemyJournalRepository(session)
            for index in range(total_claims):
                claim = build_reservation_claim_entry(
                    reservation_id=f"RES-agg-{index}",
                    cycle_id=None,
                    claimed=False,
                    actor="auto-sim",
                    session_id="sess-a",
                    as_of=f"2026-10-01T09:{index % 60:02d}:00Z",
                    account_id=account_id,
                    instrument_id="CCC",
                )
                assert claim is not None
                await repository.append(claim)
            await session.commit()

        # ``limit=1`` ⇒ la página de ``list_entries`` trae 100 filas (< 120): si el conteo saliera
        # de la página, mentiría. El agregado debe dar el total real.
        async with monitor_pg_factory() as session:
            dto = await read_operational_monitor(
                session, account_id, engine_id=_ENGINE_ID, limit=1, grace_seconds=61.0
            )

        concurrency = dto["concurrency"]
        assert concurrency["claimAttempts"] == total_claims
        assert concurrency["claimAttemptsMeasurement"] == "COMPLETE"
        assert concurrency["lostClaims"] == total_claims
        # Ninguno declaró ``conflict``: la carrera NO se mide (PARTIAL), nunca un 0 afirmado.
        assert concurrency["raceConflicts"] == 0
        assert concurrency["raceConflictsMeasurement"] == "PARTIAL"
    finally:
        await _wipe(monitor_pg_factory, account_id)


@pytest.mark.asyncio
async def test_monitor_forced_releases_come_from_the_aggregate(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``forcedReleases`` es el conteo GLOBAL: con la ventana truncada sigue siendo el total."""
    from bolsa_application.auto_operational_monitor import read_operational_monitor
    from bolsa_application.reservation_store import PostgresReservationStore

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    total_forced = 5
    await _wipe(monitor_pg_factory, account_id)
    try:
        async with monitor_pg_factory() as session:
            reservations = PostgresReservationStore(session, autocommit=True)
            for index in range(total_forced):
                await reservations.save(
                    _reservation(
                        reservation_id=f"RES-fr-{index}",
                        cycle_id=f"cyc-fr-{index}",
                        account_id=account_id,
                        instrument="DDD",
                        release_reason="cancel",
                        status="RELEASED_BY_CANCEL",
                    )
                )

        # ``limit=1`` ⇒ la ventana de reservas trae 1 de 5: si el conteo saliera de la ventana
        # mentiría. El agregado en base da el universo completo.
        async with monitor_pg_factory() as session:
            dto = await read_operational_monitor(
                session, account_id, engine_id=_ENGINE_ID, limit=1, grace_seconds=61.0
            )

        concurrency = dto["concurrency"]
        assert concurrency["forcedReleases"] == total_forced
        assert concurrency["forcedReleasesMeasurement"] == "COMPLETE"
    finally:
        await _wipe(monitor_pg_factory, account_id)


@pytest.mark.asyncio
async def test_monitor_truncated_fill_window_does_not_affirm_cycle_closed(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """(A1) Con la ventana de fills truncada NO se afirma ``CYCLE_CLOSED`` ni el PnL.

    Se siembran 251 fills del mismo ciclo: 200 forman 100 round-trips cerrados y 51 son compras
    abiertas posteriores. La lectura (``limit=1`` ⇒ ventana de 200) solo ve el prefijo —que
    ``cycles_from_fills`` reconstruiría como ciclo CERRADO— y el agregado por ciclo declara
    ``251`` existentes. Sin la corrección, ese prefijo afirmaría un cierre falso; con ella, el
    ciclo se declara ``PARTIAL`` y ``closed``/``result`` no se afirman.
    """
    from bolsa_application.auto_operational_monitor import read_operational_monitor

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    await _wipe(monitor_pg_factory, account_id)
    try:
        async with monitor_pg_factory() as session:
            for index in range(100):
                await _seed_fill(
                    session,
                    account_id=account_id,
                    cycle_id=cycle_id,
                    instrument="EEE",
                    side="buy",
                    price=100.0,
                    reference_mid=100.0,
                    execution_id=f"EX-{suffix}-{index:03d}-buy",
                )
                await _seed_fill(
                    session,
                    account_id=account_id,
                    cycle_id=cycle_id,
                    instrument="EEE",
                    side="sell",
                    price=101.0,
                    reference_mid=101.0,
                    execution_id=f"EX-{suffix}-{index:03d}-sell",
                )
            for index in range(100, 151):
                await _seed_fill(
                    session,
                    account_id=account_id,
                    cycle_id=cycle_id,
                    instrument="EEE",
                    side="buy",
                    price=100.0,
                    reference_mid=100.0,
                    execution_id=f"EX-{suffix}-{index:03d}-buy",
                )
            await session.commit()

        async with monitor_pg_factory() as session:
            dto = await read_operational_monitor(
                session,
                account_id,
                engine_id=_ENGINE_ID,
                cycle_id=cycle_id,
                limit=1,
                grace_seconds=61.0,
            )

        cycle = dto["cycles"][0]
        steps = {step["id"]: step for step in cycle["steps"]}
        assert steps["FILL"]["measurement"] == "PARTIAL"
        assert "fill_window_truncated" in (steps["FILL"]["note"] or "")
        assert steps["CYCLE_CLOSED"]["state"] == "unknown"
        assert steps["CYCLE_CLOSED"]["measurement"] == "PARTIAL"
        assert steps["CYCLE_CLOSED"]["note"] == "cycle_closed_window_truncated"
        assert cycle["closed"] is None
        assert cycle["closedMeasurement"] == "PARTIAL"
        assert cycle["result"] is None
    finally:
        await _wipe(monitor_pg_factory, account_id)


@pytest.mark.asyncio
async def test_monitor_aggregate_zero_is_measured_complete(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """(A2) El agregado ejecutado con 0 eventos es ``COMPLETE`` (cero medido), no ``UNKNOWN``."""
    from bolsa_application.auto_operational_monitor import read_operational_monitor

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    await _wipe(monitor_pg_factory, account_id)
    try:
        async with monitor_pg_factory() as session:
            dto = await read_operational_monitor(
                session, account_id, engine_id=_ENGINE_ID, grace_seconds=61.0
            )

        concurrency = dto["concurrency"]
        assert concurrency["claimAttempts"] == 0
        assert concurrency["claimAttemptsMeasurement"] == "COMPLETE"
        assert concurrency["reconciliations"] == 0
        assert concurrency["reconciliationsMeasurement"] == "COMPLETE"
    finally:
        await _wipe(monitor_pg_factory, account_id)


@pytest.mark.asyncio
async def test_list_entries_tiebreaks_equal_timestamps_deterministically(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """(A3) Con ``created_at`` empatado, ``ORDER BY created_at DESC, id DESC`` decide."""
    from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    await _wipe(monitor_pg_factory, account_id)
    try:
        async with monitor_pg_factory() as session:
            repository = SqlAlchemyJournalRepository(session)
            for entry_id in ("JNL-000001", "JNL-000002"):
                await repository.append(
                    DecisionJournalEntryRecord(
                        id=entry_id,
                        decision_id="dec-tie",
                        event_type="auto_entry_decision",
                        actor="auto-sim",
                        created_at="2026-10-01T09:00:00Z",
                        account_id=account_id,
                    )
                )
            await session.commit()

        async with monitor_pg_factory() as session:
            repository = SqlAlchemyJournalRepository(session)
            rows, total = await repository.list_entries(
                account_id=account_id, event_type="auto_entry_decision", limit=1
            )
            assert total == 2
            assert rows[0].id == "JNL-000002"
    finally:
        await _wipe(monitor_pg_factory, account_id)


@pytest.mark.asyncio
async def test_monitor_last_decision_is_scoped_by_engine(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """(A4) ``lastDecisionAt`` es la decisión de ESTE motor, no la de otro de la misma cuenta."""
    from bolsa_application.auto_operational_monitor import read_operational_monitor
    from bolsa_domain.entities.cognitive_artifacts import DecisionJournalEntryRecord
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    await _wipe(monitor_pg_factory, account_id)
    try:
        async with monitor_pg_factory() as session:
            repository = SqlAlchemyJournalRepository(session)
            # Motor A: decisión más vieja. Motor B: decisión más nueva (no debe ganar para A).
            await repository.append(
                DecisionJournalEntryRecord(
                    id="JNL-engine-a",
                    decision_id="dec-engine-a",
                    event_type="auto_entry_decision",
                    actor="auto-sim",
                    created_at="2026-10-01T09:00:00Z",
                    account_id=account_id,
                    payload={"engineId": "engine-a", "cycleId": "cyc-a"},
                )
            )
            await repository.append(
                DecisionJournalEntryRecord(
                    id="JNL-engine-b",
                    decision_id="dec-engine-b",
                    event_type="auto_entry_decision",
                    actor="auto-sim",
                    created_at="2026-10-01T18:00:00Z",
                    account_id=account_id,
                    payload={"engineId": "engine-b", "cycleId": "cyc-b"},
                )
            )
            await session.commit()

        async with monitor_pg_factory() as session:
            dto = await read_operational_monitor(
                session, account_id, engine_id="engine-a", grace_seconds=61.0
            )
        assert dto["header"]["lastDecisionAt"] == "2026-10-01T09:00:00Z"

        async with monitor_pg_factory() as session:
            dto_b = await read_operational_monitor(
                session, account_id, engine_id="engine-b", grace_seconds=61.0
            )
        assert dto_b["header"]["lastDecisionAt"] == "2026-10-01T18:00:00Z"
    finally:
        await _wipe(monitor_pg_factory, account_id)


# ── v2.88.25 — hechos durables: ENTRY_ORDER, SETTLEMENT y price_source (migración 047) ──


def _fact_value(step: dict[str, Any], key: str) -> dict[str, Any]:
    return next(fact for fact in step["facts"] if fact["key"] == key)


def _migration_047_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "py"
        / "infrastructure"
        / "alembic"
        / "versions"
        / "047_fill_price_source.py"
    )


@pytest.mark.asyncio
async def test_fill_price_source_is_durable_and_projected(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """La FUENTE de precio sobrevive el roundtrip por PG y el monitor la proyecta por fill."""
    from bolsa_application.auto_operational_monitor import read_operational_monitor
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    instrument = "FFF"
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
                price_source="MARKET_CLOSE",
            )
            # En minúsculas: la normalización del dataclass la deja canónica al persistir.
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument=instrument,
                side="sell",
                price=110.0,
                reference_mid=110.1,
                execution_id=f"EX-{suffix}-sell",
                price_source="market_close",
            )
            await session.commit()
            store = PostgresSimFillFinanceContextStore(session, autocommit=False)
            rows = await store.list_by_cycle_ids(account_id, [cycle_id])
            assert rows and all(row.price_source == "MARKET_CLOSE" for row in rows)

        async with monitor_pg_factory() as session:
            dto = await read_operational_monitor(
                session, account_id, engine_id=_ENGINE_ID, cycle_id=cycle_id, grace_seconds=61.0
            )
        fill_step = next(
            step for step in dto["cycles"][0]["steps"] if step["id"] == "FILL"
        )
        sources = _fact_value(fill_step, "priceSources")
        assert sources["value"] == {"MARKET_CLOSE": 2}
        assert sources["measurement"] == "COMPLETE"
    finally:
        await _wipe(monitor_pg_factory, account_id)


@pytest.mark.asyncio
async def test_monitor_projects_durable_entry_order_and_settlement(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Con los dos eventos en el spine, ``ORDER`` y ``SETTLEMENT`` alcanzan (ya no ``unknown``)."""
    from bolsa_application.auto_operational_audit import (
        build_cycle_settlement_entry,
        build_entry_order_entry,
    )
    from bolsa_application.auto_operational_monitor import read_operational_monitor
    from bolsa_application.reservation_store import PostgresReservationStore
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    account_id = f"acc-monitor-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    instrument = "GGG"
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
                price_source="MARKET_CLOSE",
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
                price_source="MARKET_CLOSE",
            )
            await _seed_journal(
                session, account_id=account_id, cycle_id=cycle_id, instrument=instrument
            )
            repository = SqlAlchemyJournalRepository(session)
            entry_order = build_entry_order_entry(
                order_id="ORD-1",
                instrument_id=instrument,
                side="buy",
                requested_qty=10,
                applied_qty=10,
                partial=False,
                price_source="MARKET_CLOSE",
                cycle_id=cycle_id,
                actor="auto-sim",
                as_of="2026-10-01T15:00:00Z",
                account_id=account_id,
            )
            settlement = build_cycle_settlement_entry(
                settlement_id="SET-1",
                instrument_id=instrument,
                side="sell",
                closed_qty=10,
                pnl=100.0,
                settled_at="2026-10-01T16:00:00Z",
                exit_reason="time_exit",
                price_source="MARKET_CLOSE",
                cycle_id=cycle_id,
                actor="auto-sim",
                as_of="2026-10-01T16:00:00Z",
                account_id=account_id,
            )
            assert entry_order is not None and settlement is not None
            await repository.append(entry_order)
            await repository.append(settlement)
            await session.commit()

        async with monitor_pg_factory() as session:
            dto = await read_operational_monitor(
                session, account_id, engine_id=_ENGINE_ID, cycle_id=cycle_id, grace_seconds=61.0
            )
        steps = {step["id"]: step for step in dto["cycles"][0]["steps"]}
        assert steps["ORDER"]["state"] == "reached"
        assert steps["ORDER"]["note"] is None
        assert _fact_value(steps["ORDER"], "entryOrder")["value"]["orderId"] == "ORD-1"
        assert steps["SETTLEMENT"]["state"] == "reached"
        assert _fact_value(steps["SETTLEMENT"], "settlementId")["value"] == "SET-1"
        pnl = _fact_value(steps["SETTLEMENT"], "pnl")
        assert pnl["value"] == 100.0
        assert pnl["measurement"] == "COMPLETE"
    finally:
        await _wipe(monitor_pg_factory, account_id)


@pytest.mark.asyncio
async def test_migration_047_price_source_upgrade_downgrade_is_idempotent(
    monitor_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """La 047 es simétrica e idempotente: ``upgrade``/``downgrade`` pueden repetirse.

    Se ejercita dentro de una transacción que se REVIERTE al final: no altera el esquema
    compartido (PostgreSQL soporta DDL transaccional).
    """
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = _migration_047_path()
    spec = importlib.util.spec_from_file_location("mig047_price_source", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "047_fill_price_source"
    assert module.down_revision == "046_fill_reference_mid"

    table = "sim_fill_finance_context"
    column = "price_source"

    async with monitor_pg_factory() as session:
        conn = await session.connection()

        def _exercise(sync_conn: Any) -> None:
            module.op = Operations(MigrationContext.configure(sync_conn))
            # La columna ya existe (``ensure_migrated``): upgrade idempotente (no-op).
            module.upgrade()
            assert module._column_exists(sync_conn, table, column)
            module.downgrade()
            assert not module._column_exists(sync_conn, table, column)
            module.downgrade()  # segundo downgrade: no-op
            module.upgrade()
            assert module._column_exists(sync_conn, table, column)

        await conn.run_sync(_exercise)
        # Se revierte todo: el esquema de la base compartida queda intacto.
        await session.rollback()

