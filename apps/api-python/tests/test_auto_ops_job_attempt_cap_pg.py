"""Tope de intentos de la cola ``auto_ops_jobs`` (H-145-5) sobre PostgreSQL REAL.

Certifica el desenlace que faltaba: un job que agota ``max_attempts`` **no se reclama para
siempre ni se queda mudo en la cola** — ``fail_exhausted`` lo cierra ``failed`` con
``max_attempts_exceeded:<n>``. Y el control NEGATIVO del tope: un job ``running`` con latido
VIVO no se toca (está trabajando; podría completarse en este mismo tick).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_OPS_JOB_ATTEMPT_CAP_PG_REQUIRED=1`` un skip es FALLO DURO.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "AUTO_OPS_JOB_ATTEMPT_CAP_PG_REQUIRED"
_MAX_ATTEMPTS = 5


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            "PostgreSQL requerido para el tope de intentos de auto_ops_jobs pero no "
            f"disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (tope de intentos) no disponible: {exc}")


@pytest_asyncio.fixture
async def attempt_cap_pg_factory() -> async_sessionmaker[AsyncSession]:
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


@pytest.mark.asyncio
async def test_claim_stops_at_the_attempt_cap_and_fail_exhausted_closes_the_job(
    attempt_cap_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    from bolsa_domain.entities.auto_ops_job import (
        JOB_KIND_ESTUDIO_DAILY,
        JOB_STATUS_FAILED,
    )
    from bolsa_infrastructure.database.models import AutoOpsJobRow
    from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
        SqlAlchemyAutoOpsJobRepository,
    )

    factory = attempt_cap_pg_factory
    account_id = f"cap-{uuid.uuid4().hex[:12]}"
    day = "2099-01-01"
    job_id: str | None = None
    base = datetime.now(UTC)

    # Aislamiento: la cola es global (``claim_next`` no filtra por cuenta) y este gate corre
    # en un job DEDICADO sin scheduler. Se parte de una cola vacía para que el reclamo sea
    # determinista y no dependa de residuos de otras corridas.
    async with factory() as session:
        await session.execute(delete(AutoOpsJobRow))
        await session.commit()

    try:
        async with factory() as session:
            repo = SqlAlchemyAutoOpsJobRepository(session)
            job = await repo.enqueue(
                kind=JOB_KIND_ESTUDIO_DAILY, day=day, account_id=account_id
            )
            job_id = job.id
            await session.commit()

        # Cada reclamo observa un instante posterior: el latido del anterior queda obsoleto
        # (mismo camino que un worker que abandona el job). N reclamos exitosos = tope.
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            now = base + timedelta(minutes=attempt * 2)
            async with factory() as session:
                repo = SqlAlchemyAutoOpsJobRepository(session)
                claimed = await repo.claim_next(
                    stale_after_seconds=60, max_attempts=_MAX_ATTEMPTS, now=now
                )
                await session.commit()
            assert claimed is not None, f"el reclamo {attempt} debía existir"
            assert claimed.id == job_id
            assert claimed.attempt == attempt

        # Control NEGATIVO: el job está ``running`` con latido vivo ⇒ NO se toca.
        async with factory() as session:
            repo = SqlAlchemyAutoOpsJobRepository(session)
            closed = await repo.fail_exhausted(
                max_attempts=_MAX_ATTEMPTS, stale_after_seconds=60, now=base
            )
            await session.commit()
        assert closed == 0
        async with factory() as session:
            row = await session.get(AutoOpsJobRow, job_id)
        assert row is not None
        assert row.status == "running"

        # Ya no se puede reclamar: el tope lo excluye de la selección.
        async with factory() as session:
            repo = SqlAlchemyAutoOpsJobRepository(session)
            assert (
                await repo.claim_next(
                    stale_after_seconds=60,
                    max_attempts=_MAX_ATTEMPTS,
                    now=base + timedelta(minutes=60),
                )
                is None
            )
            await session.commit()

        # Latido obsoleto + intentos agotados ⇒ desenlace durable declarado.
        async with factory() as session:
            repo = SqlAlchemyAutoOpsJobRepository(session)
            closed = await repo.fail_exhausted(
                max_attempts=_MAX_ATTEMPTS,
                stale_after_seconds=60,
                now=base + timedelta(minutes=60),
            )
            await session.commit()
        assert closed == 1

        async with factory() as session:
            row = await session.get(AutoOpsJobRow, job_id)
        assert row is not None
        assert row.status == JOB_STATUS_FAILED
        assert row.error == f"max_attempts_exceeded:{_MAX_ATTEMPTS}"
        assert row.finished_at is not None

        # Un job fallido libera el hueco activo: se puede reencolar el mismo trabajo.
        async with factory() as session:
            repo = SqlAlchemyAutoOpsJobRepository(session)
            again = await repo.enqueue(
                kind=JOB_KIND_ESTUDIO_DAILY, day=day, account_id=account_id
            )
            await session.commit()
        assert again.id != job_id
    finally:
        async with factory() as session:
            await session.execute(delete(AutoOpsJobRow))
            await session.commit()
