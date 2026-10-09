"""PAPER-2 — REINICIO REAL de proceso para la cadena de evidencia durable PAPER (PG real).

Qué certifica este fichero, y por qué solo se puede certificar contra PostgreSQL real y con un
**proceso nuevo**:

1. La evidencia PAPER vive en filas **durables** (``sim_fill_finance_context`` +
   ``decision_journal_entries``): el veredicto que compone un proceso NO depende de estado en
   memoria. Tras cerrar el proceso, un proceso NUEVO reconstruye **el mismo** DTO.
2. El reinicio no puede fabricar ni degradar la evidencia: ``closedCycles``,
   ``settlementsReconciled``, el estado de los siete criterios y el veredicto reservado
   (``NO_CONFIRMED``) coinciden entre el proceso original y el nuevo.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``PAPER_EVIDENCE_RESTART_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el
bridge LIVE.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess  # noqa: S404 — proceso real, objeto del test.
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

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"
_REQUIRED_ENV = "PAPER_EVIDENCE_RESTART_PG_REQUIRED"

#: Script del proceso NUEVO: lee el material durable y publica una firma compacta por STDOUT.
#: No comparte nada con el proceso del test salvo la base de datos.
_RESTART_SCRIPT = """
import asyncio
import json
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv

load_dotenv(os.environ.get("PAPER_ENV_FILE", ".env"), override=False)


async def main() -> None:
    from bolsa_application.paper_evidence_reader import read_paper_evidence
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            dto = await read_paper_evidence(
                session, os.environ["PAPER_ACCOUNT"], versions=["orb-1"]
            )
    finally:
        await engine.dispose()
    rec = dto["reconciliation"]
    print(json.dumps({
        "closedCycles": rec["closedCycles"],
        "settlementsTotal": rec["settlementsTotal"],
        "settlementsReconciled": rec["settlementsReconciled"],
        "contradictions": rec["contradictions"],
        "statuses": {item["id"]: item["status"] for item in dto["criteria"]},
        "verdict": dto["verdict"],
    }))


asyncio.run(main())
"""


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para el reinicio de la evidencia PAPER pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (reinicio evidencia PAPER) no disponible: {exc}")


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


def _signature(dto: dict) -> dict:
    rec = dto["reconciliation"]
    return {
        "closedCycles": rec["closedCycles"],
        "settlementsTotal": rec["settlementsTotal"],
        "settlementsReconciled": rec["settlementsReconciled"],
        "contradictions": list(rec["contradictions"]),
        "statuses": {item["id"]: item["status"] for item in dto["criteria"]},
        "verdict": dto["verdict"],
    }


def _run_in_new_process(account_id: str, env_file: Path) -> dict:
    """Lee la evidencia en un proceso NUEVO y devuelve su firma."""
    env = os.environ.copy()
    env["PAPER_ACCOUNT"] = account_id
    env["PAPER_ENV_FILE"] = str(env_file)
    result = subprocess.run(  # noqa: S603 — intérprete Python con guion fijo del repo.
        [sys.executable, "-c", _RESTART_SCRIPT],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"el proceso NUEVO no pudo leer la evidencia PAPER (exit={result.returncode}):\n"
            f"{result.stdout}\n{result.stderr}"
        )
    lines = [line for line in result.stdout.splitlines() if line.strip().startswith("{")]
    assert lines, f"el proceso NUEVO no publicó la firma esperada:\n{result.stdout}"
    return json.loads(lines[-1])


@pytest.mark.asyncio
async def test_the_evidence_survives_a_real_process_restart(
    paper_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sembrar → leer en el proceso del test → releer en un proceso NUEVO ⇒ misma evidencia."""
    from bolsa_application.paper_evidence_reader import read_paper_evidence

    account_id = f"acc-paper-restart-{uuid.uuid4().hex[:10]}"
    suffix = uuid.uuid4().hex[:10]
    cycle_id = f"cyc-{suffix}"
    instrument = "RRR"
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

        # Proceso ORIGINAL (el del test) compone la evidencia.
        async with paper_pg_factory() as session:
            original = await read_paper_evidence(session, account_id, versions=["orb-1"])
        signature = _signature(original)
        assert signature["verdict"] == "NO_CONFIRMED"
        assert signature["closedCycles"] == 1
        assert signature["settlementsReconciled"] == 1
        assert signature["contradictions"] == []

        # Proceso NUEVO: sin estado compartido, misma base durable ⇒ MISMA evidencia.
        restarted = _run_in_new_process(account_id, _DOTENV)

        assert restarted == signature
    finally:
        await _wipe(paper_pg_factory, account_id)
        await _wipe_cycle_settlements(paper_pg_factory, cycle_id)
