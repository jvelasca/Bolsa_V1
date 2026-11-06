"""D-4 (auditoría 2) — encolado concurrente de ``auto_ops_jobs`` sobre PostgreSQL REAL.

El contrato de ``created`` no se puede certificar con dobles: la carrera la resuelve el
índice único PARCIAL ``auto_ops_jobs_active_job_key`` sobre
``(kind, coalesce(account_id, ''), day) WHERE status IN ('queued','running')``. Este módulo
mide en la base real:

* dos peticiones concurrentes del MISMO hueco producen UN solo job: una lo crea
  (``created=True``) y la otra recibe ESE job (``created=False``), nunca un 500;
* un job terminado libera el hueco y una reejecución declarada SÍ se encola
  (``created=True`` con id nuevo).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_OPS_JOBS_OUTCOME_PG_REQUIRED=1`` un skip es FALLO DURO.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.auto_ops_jobs import EnqueueOutcome
from bolsa_domain.entities.auto_ops_job import JOB_KIND_DIA_D_VALUE_REPLAY

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "AUTO_OPS_JOBS_OUTCOME_PG_REQUIRED"
_DAY = "2026-10-18"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            "PostgreSQL requerido para el encolado concurrente de auto_ops_jobs pero no "
            f"disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (encolado concurrente) no disponible: {exc}")


@pytest_asyncio.fixture
async def outcome_pg_factory() -> async_sessionmaker[AsyncSession]:
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


async def _enqueue(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    symbol: str,
) -> EnqueueOutcome:
    from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
        SqlAlchemyAutoOpsJobRepository,
    )

    async with factory() as session:
        outcome = await SqlAlchemyAutoOpsJobRepository(session).enqueue_with_outcome(
            kind=JOB_KIND_DIA_D_VALUE_REPLAY,
            day=_DAY,
            account_id=account_id,
            payload={"symbol": symbol},
        )
        await session.commit()
    return outcome


async def _cleanup(factory: async_sessionmaker[AsyncSession], account_id: str) -> None:
    from bolsa_infrastructure.database.models import AutoOpsJobRow

    async with factory() as session:
        await session.execute(
            delete(AutoOpsJobRow).where(AutoOpsJobRow.account_id == account_id)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_two_concurrent_requests_create_exactly_one_job(
    outcome_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """D-4 — la carrera del índice único converge: un creador y un reutilizador.

    Sin el ``SAVEPOINT`` + reintento, la petición perdedora re-lanzaba ``IntegrityError``
    (500) o presentaba el job ajeno como propio.
    """
    factory = outcome_pg_factory
    account_id = f"d4-{uuid.uuid4().hex[:12]}"

    try:
        first, second = await asyncio.gather(
            _enqueue(factory, account_id=account_id, symbol="AAA"),
            _enqueue(factory, account_id=account_id, symbol="BBB"),
        )

        assert sorted([first.created, second.created]) == [False, True]
        # El perdedor devuelve el MISMO job (y con el símbolo del ganador, no el suyo).
        assert first.job.id == second.job.id
        creator = first if first.created else second
        reused = second if first.created else first
        assert reused.job.payload["symbol"] == creator.job.payload["symbol"]
    finally:
        await _cleanup(factory, account_id)


@pytest.mark.asyncio
async def test_a_finished_job_frees_the_slot_for_a_declared_rerun(
    outcome_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """D-4 — el índice es PARCIAL: un job terminado libera el hueco y se vuelve a encolar."""
    from bolsa_infrastructure.database.models import AutoOpsJobRow

    factory = outcome_pg_factory
    account_id = f"d4-{uuid.uuid4().hex[:12]}"

    try:
        first = await _enqueue(factory, account_id=account_id, symbol="AAA")
        assert first.created is True

        async with factory() as session:
            row = await session.get(AutoOpsJobRow, first.job.id)
            assert row is not None
            row.status = "completed"
            await session.commit()

        again = await _enqueue(factory, account_id=account_id, symbol="AAA")
        assert again.created is True
        assert again.job.id != first.job.id
    finally:
        await _cleanup(factory, account_id)
