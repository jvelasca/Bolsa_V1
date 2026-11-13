"""Cron del DÍA-D retrospectivo **as-run** (ADR-049) — OFF por defecto.

El método as-run es de **investigación**: mide la operativa real, no opera. Por eso su
encolado diario está apagado salvo que un despliegue lo pida explícitamente
(``DIA_D_AS_RUN_SCHEDULED=1``). Encenderlo no toca el motor ni `ActiveStrategy`: sólo
añade un job a la cola durable ``auto_ops_jobs``, que es read-only sobre PostgreSQL.

Reglas:

* **Doble gate**: el starter no arranca con el flag OFF y la función de encolado vuelve a
  comprobarlo. Un test que llame directo tampoco encola si el flag está apagado.
* **Dedupe durable**: una corrida ACTIVA o COMPLETADA del mismo día no se repite; los
  fallos se reintentan como máximo ``_MAX_ATTEMPTS_PER_DAY`` veces.
* **Sin cuenta**: se declara y no se encola nada (no se inventa una cuenta).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.auto_ops_jobs import EnqueueAutoOpsJob
from bolsa_domain.entities.auto_ops_job import (
    JOB_KIND_DIA_D_AS_RUN,
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
    "dia_d_as_run_scheduler_loop",
    "enqueue_daily_dia_d_as_run",
    "start_dia_d_as_run_scheduler",
]

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS_PER_DAY = 3


async def enqueue_daily_dia_d_as_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime | None = None,
) -> str | None:
    """Encola el as-run del día D si procede. Devuelve el id encolado o ``None``."""
    settings = get_settings()
    if not bool(getattr(settings, "dia_d_as_run_scheduled", False)):
        # Gate declarado: sin él, ni siquiera se abre sesión contra la BD.
        return None

    moment = now or datetime.now(UTC)
    lookback = max(1, int(getattr(settings, "dia_d_as_run_lookback_days", 1)))
    day = (moment.date() - timedelta(days=lookback)).isoformat()
    today = moment.date().isoformat()
    if day > today:  # pragma: no cover — lookback >= 1 lo hace imposible
        return None

    async with session_factory() as session:
        account_id = await SqlAlchemyAccountRepository(
            session
        ).resolve_default_account_for_owner()
        if not account_id:
            logger.info(
                "DIA_D_AS_RUN sin cuenta activa del owner: no se encola el job diario"
            )
            return None

        repo = SqlAlchemyAutoOpsJobRepository(session)
        existing = await repo.list_for_day(
            kind=JOB_KIND_DIA_D_AS_RUN, day=day, account_id=account_id
        )
        if existing:
            latest = existing[0]
            if latest.status in (
                JOB_STATUS_QUEUED,
                JOB_STATUS_RUNNING,
                JOB_STATUS_COMPLETED,
            ):
                logger.debug(
                    "DIA_D_AS_RUN job del %s ya en estado %s; no se duplica",
                    day,
                    latest.status,
                )
                return None
            if len(existing) >= _MAX_ATTEMPTS_PER_DAY:
                logger.warning(
                    "DIA_D_AS_RUN %s intento(s) fallidos el %s: no se reintenta hoy",
                    len(existing),
                    day,
                )
                return None

        job = await EnqueueAutoOpsJob(repo).execute(
            kind=JOB_KIND_DIA_D_AS_RUN,
            account_id=account_id,
            day=day,
            payload={
                "enqueuedBy": "scheduler",
                "accountId": account_id,
                "lookbackDays": lookback,
            },
        )
        await session.commit()
        logger.info(
            "DIA_D_AS_RUN encolado job %s (D=%s · cuenta %s)", job.id, day, account_id
        )
        return job.id


async def dia_d_as_run_scheduler_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(300.0, float(settings.dia_d_as_run_interval_seconds))
    logger.info(
        "Worker DIA_D_AS_RUN iniciado — comprueba/encola 1/día cada %ds", int(interval)
    )
    while True:
        try:
            await enqueue_daily_dia_d_as_run(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — el cron no muere por un fallo de BD
            logger.exception("DIA_D_AS_RUN: no se pudo encolar el job diario")
        await asyncio.sleep(interval)


def start_dia_d_as_run_scheduler(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    """Arranca el cron **sólo** si ``DIA_D_AS_RUN_SCHEDULED`` está encendido."""
    settings = get_settings()
    if not bool(getattr(settings, "dia_d_as_run_scheduled", False)):
        logger.info("DIA_D_AS_RUN scheduler OFF (DIA_D_AS_RUN_SCHEDULED=0)")
        return None
    return asyncio.create_task(dia_d_as_run_scheduler_loop(session_factory))
