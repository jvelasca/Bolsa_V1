"""Worker — encola la operativa diaria del universo ESTUDIO (job ``estudio_daily``).

Antes (v2.88) este worker era un **tick vacío**: no tenía universo de servidor y el batch
solo se podía disparar por HTTP. Ahora:

* Una vez al día UTC y por la cuenta por defecto del owner, ENCOLA el job ``estudio_daily``
  en ``auto_ops_jobs`` (índice único parcial ⇒ nunca hay dos jobs activos del mismo día).
* El trabajo real lo ejecuta ``auto_ops_job_worker`` (universo ESTUDIO → opiniones
  ``eod_batch`` → propuestas dry-run), con progreso y desenlace durables.
* Dedupe de día: si ya hay un job del día en ``queued|running|completed`` no se repite; si
  falló se reintenta hasta ``_MAX_ATTEMPTS_PER_DAY`` veces.

Interruptor: ``ESTUDIO_EOD_OPINION_ENABLED`` (ON por defecto; opt-out documentado).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.auto_ops_jobs import EnqueueAutoOpsJob
from bolsa_domain.entities.auto_ops_job import (
    JOB_KIND_ESTUDIO_DAILY,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
)
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
    SqlAlchemyAutoOpsJobRepository,
)

__all__ = [
    "enqueue_daily_estudio_job",
    "estudio_eod_opinion_worker_loop",
    "start_estudio_eod_opinion_worker",
]

logger = logging.getLogger(__name__)

#: Reintentos máximos del día si el job falla (evita un bucle horario de fallos).
_MAX_ATTEMPTS_PER_DAY = 3


async def enqueue_daily_estudio_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime | None = None,
) -> str | None:
    """Encola el job del día si procede. Devuelve el id encolado o ``None``."""
    moment = now or datetime.now(UTC)
    day = moment.date().isoformat()
    async with session_factory() as session:
        account_id = await SqlAlchemyAccountRepository(
            session
        ).resolve_default_account_for_owner()
        if not account_id:
            logger.info(
                "ESTUDIO_EOD_OPINION sin cuenta activa del owner: no se encola el job diario"
            )
            return None

        repo = SqlAlchemyAutoOpsJobRepository(session)
        existing = await repo.list_for_day(
            kind=JOB_KIND_ESTUDIO_DAILY, day=day, account_id=account_id
        )
        if existing:
            latest = existing[0]
            if latest.status in (
                JOB_STATUS_QUEUED,
                JOB_STATUS_RUNNING,
                JOB_STATUS_COMPLETED,
            ):
                logger.debug(
                    "ESTUDIO_EOD_OPINION job del %s ya en estado %s; no se duplica",
                    day,
                    latest.status,
                )
                return None
            if len(existing) >= _MAX_ATTEMPTS_PER_DAY:
                logger.warning(
                    "ESTUDIO_EOD_OPINION %s intento(s) fallidos el %s: no se reintenta hoy",
                    len(existing),
                    day,
                )
                return None

        job = await EnqueueAutoOpsJob(repo).execute(
            kind=JOB_KIND_ESTUDIO_DAILY,
            account_id=account_id,
            day=day,
            payload={"enqueuedBy": "scheduler", "accountId": account_id},
        )
        await session.commit()
        logger.info(
            "ESTUDIO_EOD_OPINION encolado job %s (%s · cuenta %s)",
            job.id,
            day,
            account_id,
        )
        return job.id


async def estudio_eod_opinion_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(300, int(settings.estudio_eod_opinion_interval_seconds))
    logger.info(
        "Worker ESTUDIO_EOD_OPINION iniciado — comprueba/encola 1/día cada %ds", interval
    )
    while True:
        try:
            await enqueue_daily_estudio_job(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — el cron no muere por un fallo de BD
            logger.exception("ESTUDIO_EOD_OPINION: no se pudo encolar el job diario")
        await asyncio.sleep(interval)


def start_estudio_eod_opinion_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    settings = get_settings()
    if not settings.estudio_eod_opinion_enabled:
        logger.info(
            "Worker ESTUDIO_EOD_OPINION desactivado (ESTUDIO_EOD_OPINION_ENABLED=false)"
        )
        return None
    return asyncio.create_task(estudio_eod_opinion_worker_loop(session_factory))
