"""Planificador de la verificación periódica de estrategia (ADR-050) — OFF por defecto.

Qué hace
--------
No mide: garantiza que **cada época cerrada tenga su artefacto as-run**. El método de
medición sigue siendo el CLI ``v2_102``; este cron solo decide CUÁNDO toca medir y con qué
universo declarado.

Reglas
------
* **Doble gate**: ``STRATEGY_VERIFICATION_ENABLED`` apagado ⇒ ni el starter ni la función de
  encolado abren sesión contra la base de datos.
* **Épocas no solapadas**: la siguiente época empieza en el ``to_day`` de la última época
  registrada (o en ``hoy - everyDays`` la primera vez). Mientras no haya transcurrido
  ``everyDays`` desde ese cierre, no se encola nada.
* **Universo declarado en D**: se resuelve del libro durable de D. Sin posiciones se declara
  el hueco; el artefacto quedará ``NOT_EVALUATED`` en ``initial_state`` y no se presenta como
  certificable.
* **Dedupe durable**: la cola ``auto_ops_jobs`` ya deduplica por ``(kind, cuenta, día)``.

La ventana móvil (``rolling``) es solo historial: este planificador no la usa para decidir y
sus runs se marcan ``kind="rolling"`` si llegan a persistirse.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.background.dia_d_as_run_scheduler import resolve_declared_universe
from bolsa_application.auto_ops_jobs import EnqueueAutoOpsJob
from bolsa_domain.entities.auto_ops_job import JOB_KIND_DIA_D_AS_RUN
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
    SqlAlchemyAutoOpsJobRepository,
)
from bolsa_infrastructure.database.repositories.strategy_verification_repository import (
    SqlAlchemyStrategyVerificationRepository,
)

__all__ = [
    "enqueue_due_verification_epochs",
    "start_strategy_verification_scheduler",
    "strategy_verification_scheduler_loop",
]

logger = logging.getLogger(__name__)

_KIND_EPOCH = "epoch"


def _next_epoch_window(*, last_to: date | None, today: date, every_days: int) -> tuple[date, date] | None:
    """Ventana ``(day, to_day]`` pendiente, o ``None`` si aún no toca medir.

    Con ``last_to`` conocido, la época siguiente es ``(last_to, last_to + every]`` y solo se
    encola cuando ya cerró. Sin runs previos se mide la última ventana completa.
    """
    if last_to is None:
        return today - timedelta(days=every_days), today
    if (today - last_to).days < every_days:
        return None
    day = last_to
    to_day = last_to + timedelta(days=every_days)
    if to_day > today:
        return None
    return day, to_day


async def enqueue_due_verification_epochs(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime | None = None,
) -> list[str]:
    """Encola los as-run de las épocas vencidas. Devuelve los ids de job creados."""
    settings = get_settings()
    if not bool(getattr(settings, "strategy_verification_enabled", False)):
        return []

    moment = now or datetime.now(UTC)
    today = moment.date()
    every = max(1, int(getattr(settings, "strategy_verification_every_days", 30)))

    async with session_factory() as session:
        account_id = await SqlAlchemyAccountRepository(
            session
        ).resolve_default_account_for_owner()
        if not account_id:
            logger.info(
                "STRATEGY_VERIFICATION sin cuenta activa del owner: no se encola época"
            )
            return []

        verification_repo = SqlAlchemyStrategyVerificationRepository(session)
        runs = await verification_repo.list_runs(
            account_id=account_id, kind=_KIND_EPOCH, limit=1
        )
        last_to = date.fromisoformat(runs[-1].to_day) if runs else None
        window = _next_epoch_window(last_to=last_to, today=today, every_days=every)
        if window is None:
            logger.debug(
                "STRATEGY_VERIFICATION: la época siguiente aún no ha cerrado (última=%s)",
                last_to,
            )
            return []
        day, to_day = window

        universe = await resolve_declared_universe(
            session, account_id=account_id, day=day.isoformat()
        )
        job = await EnqueueAutoOpsJob(
            SqlAlchemyAutoOpsJobRepository(session)
        ).execute(
            kind=JOB_KIND_DIA_D_AS_RUN,
            account_id=account_id,
            day=day.isoformat(),
            payload={
                "enqueuedBy": "strategy-verification-scheduler",
                "accountId": account_id,
                "to": to_day.isoformat(),
                "universeInstruments": list(universe),
                "verifyBars": True,
                "verificationProfileId": "default",
                "verificationKind": _KIND_EPOCH,
            },
        )
        await session.commit()
        if not universe:
            logger.warning(
                "STRATEGY_VERIFICATION época %s→%s sin universo declarado en D: el "
                "artefacto no podrá certificar el estado inicial",
                day,
                to_day,
            )
        logger.info(
            "STRATEGY_VERIFICATION época %s→%s encolada (job %s · cuenta %s)",
            day,
            to_day,
            job.id,
            account_id,
        )
        return [job.id]


async def strategy_verification_scheduler_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(300.0, float(settings.strategy_verification_interval_seconds))
    logger.info(
        "Worker STRATEGY_VERIFICATION iniciado — comprueba épocas cada %ds", int(interval)
    )
    while True:
        try:
            await enqueue_due_verification_epochs(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — el cron no muere por un fallo de BD
            logger.exception("STRATEGY_VERIFICATION: no se pudo encolar la época")
        await asyncio.sleep(interval)


def start_strategy_verification_scheduler(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    """Arranca el cron **sólo** si ``STRATEGY_VERIFICATION_ENABLED`` está encendido."""
    settings = get_settings()
    if not bool(getattr(settings, "strategy_verification_enabled", False)):
        logger.info("STRATEGY_VERIFICATION scheduler OFF (STRATEGY_VERIFICATION_ENABLED=0)")
        return None
    return asyncio.create_task(strategy_verification_scheduler_loop(session_factory))
