"""Worker — job periódico de custodia (R-10 F4b).

Ejecuta ``RunCustodyJob`` en cada ciclo sobre todas las cuentas **activas**,
moviendo ``ApplyCustodyFees`` fuera del path de lectura (los GET de summary/tax ya
no mutan custodia). On-by-default: ``CUSTODY_JOB_ENABLED=true``.

Idempotente: ``ApplyCustodyFees`` ya devuelve ``False`` ante colisión UNIQUE/mutex
o periodo ya cobrado; un fallo puntual de ciclo se loggea y se reentra al siguiente.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.custody_job import RunCustodyJob
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.custody_obligation_repository import (
    CustodyObligationRepository,
)
from bolsa_infrastructure.database.repositories.ledger_repository import SqlAlchemyLedgerRepository
from bolsa_infrastructure.database.repositories.portfolio_repository import (
    SqlAlchemyPortfolioRepository,
)

logger = logging.getLogger(__name__)


async def _run_custody_job_once(session_factory: async_sessionmaker[AsyncSession]) -> dict[str, Any]:
    async with session_factory() as session:
        try:
            job = RunCustodyJob(
                SqlAlchemyAccountRepository(session),
                SqlAlchemyPortfolioRepository(session),
                SqlAlchemyLedgerRepository(session),
                CustodyObligationRepository(session),
            )
            result = await job.execute()
            await session.commit()
            logger.info(
                "Custodia job: scanned=%s applied=%s pending=%s skipped=%s",
                result.get("scanned"),
                result.get("applied_complete"),
                result.get("pending"),
                result.get("skipped"),
            )
            return result
        except Exception:
            await session.rollback()
            raise


async def custody_job_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(60, int(settings.custody_job_interval_seconds))
    logger.info("Worker custodia job iniciado — intervalo %ds", interval)
    while True:
        await asyncio.sleep(interval)
        try:
            await _run_custody_job_once(session_factory)
        except Exception:
            logger.exception("Error en worker custodia job")


def start_custody_job_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    settings = get_settings()
    if not settings.custody_job_enabled:
        logger.info("Custodia job worker desactivado (CUSTODY_JOB_ENABLED=false)")
        return None
    return asyncio.create_task(custody_job_worker_loop(session_factory))
