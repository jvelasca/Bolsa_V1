"""PAPER-2 — evidencia durable PAPER sobre PostgreSQL real (adaptador + conciliación).

Qué certifica este fichero, y por qué solo se puede certificar contra PG real:

1. **La evidencia se compone de filas durables de verdad.** Un ciclo con fills con ``cycle_id``
   y un cierre durable ``auto_cycle_settlement`` escritos por OTRA sesión reaparecen en el DTO:
   ``closedCycles``/``settlementsTotal``/``settlementsReconciled`` medidos y el criterio
   ``closure_reconciliation`` evaluado sobre el material real.
2. **Ausencia ⇒ declarado, nunca ``0`` fingido.** Una cuenta sin material declara la ventana y
   los recuentos como ceros MEDIDOS (no huecos) y ``non_contradiction`` sin contradicciones.
3. **Un cierre contradictorio se DECLARA.** Un settlement cuyo PnL discrepa del FIFO produce una
   contradicción y degrada ``non_contradiction``: la evidencia completa no se puede falsear.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``PAPER_EVIDENCE_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "PAPER_EVIDENCE_PG_REQUIRED"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la evidencia PAPER pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (evidencia PAPER) no disponible: {exc}")


@pytest_asyncio.fixture
async def paper_pg_factory() -> async_sessionmaker[AsyncSession]:
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
        for table in ("sim_fill_finance_context", "decision_journal_entries"):
            await session.execute(
                text(f"DELETE FROM {table} WHERE account_id = :account_id"),
                {"account_id": account_id},
            )
        await session.commit()


async def _wipe_cycle_settlements(
    factory: async_sessionmaker[AsyncSession], cycle_id: str
) -> None:
    """Borra los cierres del ciclo SIN filtrar por cuenta (cubre ``account_id`` nulo u otra cuenta)."""
    from bolsa_application.auto_cycle_journal import cycle_decision_id

    decision_id = cycle_decision_id(cycle_id)
    async with factory() as session:
        await session.execute(
            text("DELETE FROM decision_journal_entries WHERE decision_id = :decision_id"),
            {"decision_id": decision_id},
        )
        await session.commit()


async def _seed_fill(
    session: AsyncSession,
    *,
    account_id: str,
    cycle_id: str,
    instrument: str,
    side: str,
    price: float,
    execution_id: str,
    version: str = "orb-1",
) -> None:
    from bolsa_application.sim_durable_store import (
        PostgresSimFillFinanceContextStore,
        SimFillFinanceContext,
    )

    store = PostgresSimFillFinanceContextStore(session, autocommit=False)
    await store.save(
        SimFillFinanceContext(
            execution_id=execution_id,
            instrument_id=instrument,
            side=side,
            quantity=Decimal("10"),
            price=Decimal(str(price)),
            reference_mid=Decimal(str(price)),
            account_id=account_id,
            strategy_version_id=version,
            cycle_id=cycle_id,
            created_at=datetime(2026, 10, 1, 15, 0, tzinfo=UTC),
        )
    )


async def _seed_settlement(
    session: AsyncSession,
    *,
    account_id: str | None,
    cycle_id: str,
    instrument: str,
    pnl: float,
) -> None:
    from bolsa_application.auto_operational_audit import build_cycle_settlement_entry
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    entry = build_cycle_settlement_entry(
        settlement_id=f"SET-{uuid.uuid4().hex[:10]}",
        instrument_id=instrument,
        side="sell",
        closed_qty=10,
        pnl=pnl,
        settled_at="2026-10-01T15:05:00Z",
        exit_reason="T2",
        price_source="simulated",
        cycle_id=cycle_id,
        actor="auto-sim",
        as_of="2026-10-01T15:05:00Z",
        account_id=account_id,
    )
    assert entry is not None
    await SqlAlchemyJournalRepository(session).append(entry)


def _criterion(dto: dict, criterion_id: str) -> dict:
    return next(item for item in dto["criteria"] if item["id"] == criterion_id)


@pytest.mark.asyncio
async def test_evidence_is_composed_from_real_durable_rows(
    paper_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_application.paper_evidence_reader import read_paper_evidence

    account_id = f"acc-paper-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    instrument = "AAA"
    await _wipe(paper_pg_factory, account_id)
    try:
        async with paper_pg_factory() as session:
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument=instrument,
                side="buy",
                price=100.0,
                execution_id=f"EX-{suffix}-buy",
            )
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument=instrument,
                side="sell",
                price=110.0,
                execution_id=f"EX-{suffix}-sell",
            )
            await _seed_settlement(
                session, account_id=account_id, cycle_id=cycle_id, instrument=instrument, pnl=100.0
            )
            await session.commit()

        # Otra sesión (el endpoint) lee lo que acaba de quedar durable.
        async with paper_pg_factory() as session:
            dto = await read_paper_evidence(session, account_id, versions=["orb-1"])

        rec = dto["reconciliation"]
        assert rec["fillsLoaded"] is True
        assert rec["closedCycles"] == 1
        assert rec["settlementsTotal"] == 1
        assert rec["settlementsReconciled"] == 1
        assert rec["contradictions"] == []
        assert _criterion(dto, "closure_reconciliation")["status"] == "unmet"  # < 32: no promociona
        assert _criterion(dto, "non_contradiction")["status"] == "met"
        assert dto["verdict"] == "NO_CONFIRMED"
        assert re.search(r"\bCONFIRMED\b", json.dumps(dto)) is None
    finally:
        await _wipe(paper_pg_factory, account_id)


@pytest.mark.asyncio
async def test_an_empty_account_declares_measured_zeros_not_gaps(
    paper_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_application.paper_evidence_reader import read_paper_evidence

    account_id = f"acc-paper-{uuid.uuid4().hex[:10]}"
    await _wipe(paper_pg_factory, account_id)
    try:
        async with paper_pg_factory() as session:
            dto = await read_paper_evidence(session, account_id)

        rec = dto["reconciliation"]
        assert rec["fillsLoaded"] is True
        assert rec["fillsTotal"] == 0
        assert rec["closedCycles"] == 0
        assert dto["fillsTotalForAccount"] == 0
        assert _criterion(dto, "window")["status"] == "unmet"
        assert _criterion(dto, "non_contradiction")["status"] == "met"
        assert dto["verdict"] == "NO_CONFIRMED"
    finally:
        await _wipe(paper_pg_factory, account_id)


@pytest.mark.asyncio
async def test_a_contradictory_closure_is_declared_and_never_looks_complete(
    paper_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_application.paper_evidence_reader import read_paper_evidence

    account_id = f"acc-paper-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    await _wipe(paper_pg_factory, account_id)
    try:
        async with paper_pg_factory() as session:
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument="BBB",
                side="buy",
                price=100.0,
                execution_id=f"EX-{suffix}-buy",
            )
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument="BBB",
                side="sell",
                price=110.0,
                execution_id=f"EX-{suffix}-sell",
            )
            # El FIFO mide 100; el cierre declara 90 ⇒ contradicción declarada.
            await _seed_settlement(
                session, account_id=account_id, cycle_id=cycle_id, instrument="BBB", pnl=90.0
            )
            await session.commit()

        async with paper_pg_factory() as session:
            dto = await read_paper_evidence(session, account_id, versions=["orb-1"])

        rec = dto["reconciliation"]
        assert rec["settlementsDivergent"] == 1
        assert any(c.startswith("settlement_pnl_mismatch") for c in dto["contradictions"])
        assert _criterion(dto, "non_contradiction")["status"] == "unmet"
        assert dto["verdict"] == "NO_CONFIRMED"
    finally:
        await _wipe(paper_pg_factory, account_id)


@pytest.mark.asyncio
async def test_a_settlement_without_account_is_excluded_and_declared(
    paper_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Un cierre durable SIN cuenta no entra en el ámbito: se declara, no se lee como favorable."""
    from bolsa_application.paper_evidence_reader import read_paper_evidence

    account_id = f"acc-paper-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    await _wipe(paper_pg_factory, account_id)
    try:
        async with paper_pg_factory() as session:
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument="CCC",
                side="buy",
                price=100.0,
                execution_id=f"EX-{suffix}-buy",
            )
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument="CCC",
                side="sell",
                price=110.0,
                execution_id=f"EX-{suffix}-sell",
            )
            # Cierre SIN cuenta (``account_id=None``) y cierre CON cuenta, mismo ciclo.
            await _seed_settlement(
                session, account_id=None, cycle_id=cycle_id, instrument="CCC", pnl=100.0
            )
            await _seed_settlement(
                session, account_id=account_id, cycle_id=cycle_id, instrument="CCC", pnl=100.0
            )
            await session.commit()

        async with paper_pg_factory() as session:
            dto = await read_paper_evidence(session, account_id, versions=["orb-1"])

        rec = dto["reconciliation"]
        assert rec["settlementsTotal"] == 1  # solo el cierre CON cuenta entra en el ámbito
        assert "unattributed_settlements_excluded" in dto["notes"]
        assert any(c.startswith("settlement_without_account") for c in dto["contradictions"])
        assert dto["verdict"] == "NO_CONFIRMED"
    finally:
        await _wipe(paper_pg_factory, account_id)
        await _wipe_cycle_settlements(paper_pg_factory, cycle_id)


@pytest.mark.asyncio
async def test_a_settlement_of_another_account_is_not_admitted(
    paper_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Un cierre de OTRA cuenta no aparece en el DTO de esta cuenta."""
    from bolsa_application.paper_evidence_reader import read_paper_evidence

    account_id = f"acc-paper-{uuid.uuid4().hex[:10]}"
    other_account = f"acc-other-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    await _wipe(paper_pg_factory, account_id)
    try:
        async with paper_pg_factory() as session:
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument="DDD",
                side="buy",
                price=100.0,
                execution_id=f"EX-{suffix}-buy",
            )
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument="DDD",
                side="sell",
                price=110.0,
                execution_id=f"EX-{suffix}-sell",
            )
            await _seed_settlement(
                session,
                account_id=other_account,
                cycle_id=cycle_id,
                instrument="DDD",
                pnl=100.0,
            )
            await session.commit()

        async with paper_pg_factory() as session:
            dto = await read_paper_evidence(session, account_id, versions=["orb-1"])

        rec = dto["reconciliation"]
        assert rec["settlementsTotal"] == 0
        assert "unattributed_settlements_excluded" not in dto["notes"]
    finally:
        await _wipe(paper_pg_factory, account_id)
        await _wipe_cycle_settlements(paper_pg_factory, cycle_id)


@pytest.mark.asyncio
async def test_a_read_failure_is_declared_and_never_favorable(
    paper_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Con filas reales presentes, un fallo de LECTURA no se transforma en evidencia favorable."""
    from bolsa_application.paper_evidence_reader import read_paper_evidence

    account_id = f"acc-paper-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    await _wipe(paper_pg_factory, account_id)
    try:
        async with paper_pg_factory() as session:
            await _seed_fill(
                session,
                account_id=account_id,
                cycle_id=cycle_id,
                instrument="EEE",
                side="buy",
                price=100.0,
                execution_id=f"EX-{suffix}-buy",
            )
            await session.commit()

        async def _boom(self: object, account_id: object, *, limit: int = 500) -> list[str]:
            raise RuntimeError("durable fills unavailable")

        monkeypatch.setattr(
            "bolsa_application.sim_durable_store.PostgresSimFillFinanceContextStore.list_recent_cycle_ids",
            _boom,
        )

        async with paper_pg_factory() as session:
            dto = await read_paper_evidence(session, account_id, versions=["orb-1"])

        rec = dto["reconciliation"]
        assert rec["fillsLoaded"] is False
        assert "fills_not_loaded" in dto["notes"]
        assert "non_contradiction" in dto["unknownCriterionIds"]
        assert dto["verdict"] == "NO_CONFIRMED"
    finally:
        await _wipe(paper_pg_factory, account_id)
        await _wipe_cycle_settlements(paper_pg_factory, cycle_id)
