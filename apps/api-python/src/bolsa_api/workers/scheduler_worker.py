"""Proceso separado de workers programados — fuera del `lifespan` de FastAPI (D3).

P0.4: los workers/schedulers/crons vivían embebidos en ``main.lifespan``; con
``uvicorn --workers N`` se duplicaban (una copia por worker del servicio HTTP).
D3 los mueve a **un proceso dedicado** que ejecuta los mismos loops (basados en
los ``start_*`` de ``bolsa_api.background``, que ya gestionan su gate de
configuración), de modo que haya exactamente una instancia de cada cron.

Ejecución:
    python -m bolsa_api.workers.scheduler_worker

R12-SCHED / R-8C.2: este proceso es **solo crons periódicos**. Nunca arranca
scan/optimize. Autoridad de colas:

- ``SCAN_QUEUE_BACKEND=arq`` → ``arq_worker``
- postgres / redis / otros backends no-ARQ → ``queue_poll_worker``
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from bolsa_api.background.auto_sync_worker import start_auto_sync_worker
from bolsa_api.background.core_r_cron_worker import start_core_r_cron_worker
from bolsa_api.background.custody_job_worker import start_custody_job_worker
from bolsa_api.background.daily_alert_evaluator import start_daily_alert_evaluator
from bolsa_api.background.estudio_eod_opinion_worker import start_estudio_eod_opinion_worker
from bolsa_api.background.fa_weekly_worker import start_fa_weekly_worker
from bolsa_api.background.index_subscribe_worker import start_index_subscribe_worker
from bolsa_api.background.opportunity_daily_scan_worker import (
    start_opportunity_daily_scan_worker,
)
from bolsa_api.background.signal_alert_evaluator import start_signal_alert_evaluator
from bolsa_api.background.tracker_schedule_worker import start_tracker_schedule_worker
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.migrations import database_bootstrap
from bolsa_infrastructure.database.session import create_engine, create_session_factory

logger = logging.getLogger(__name__)


def _event_loop_starters() -> list[Any]:
    # Workers periódicos que gestionan su propio gate de configuración.
    return [
        start_daily_alert_evaluator,
        start_signal_alert_evaluator,
        start_tracker_schedule_worker,
        start_fa_weekly_worker,
        start_core_r_cron_worker,
        start_custody_job_worker,
        start_estudio_eod_opinion_worker,
        start_opportunity_daily_scan_worker,
        start_auto_sync_worker,
        start_index_subscribe_worker,
    ]


async def _run_scheduler(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    # F3b + F3a (P1.2) + R-8A/P0-A: migraciones Alembic + migración de datos de
    # cuentas UNA vez al arranque, serializadas con el resto de procesos (workers
    # FastAPI con --workers N) mediante advisory lock, fuera del path de petición.
    await database_bootstrap(engine=engine, session_factory=session_factory)

    starters = _event_loop_starters()
    tasks: list[asyncio.Task[None]] = []
    for starter in starters:
        task = starter(session_factory)
        if task is not None:
            tasks.append(task)

    if not tasks:
        logger.warning(
            "Ningún worker programado activo en este proceso — revisa los flags "
            "(TRACKER_SCHEDULE_ENABLED, FA_WEEKLY_CRON_ENABLED, CORE_R_CRON_ENABLED, …)"
        )

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover — Windows
            pass

    await stop.wait()
    logger.info("Señal de parada recibida — cancelando workers…")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await engine.dispose()


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    engine: AsyncEngine = create_engine(settings)
    session_factory = create_session_factory(engine)

    # En Windows, asyncio.run() usa ProactorEventLoop por defecto, incompatible
    # con psycopg async. Forzar SelectorEventLoop (mismo motivo que win_loop.py,
    # que uvicorn usa en run_dev.py). Ver https://sqlalche.me/e/20/rvf5
    loop: asyncio.AbstractEventLoop
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
    else:
        loop = asyncio.new_event_loop()

    logger.info("Scheduler worker iniciado (crons only; R12-SCHED)")
    try:
        with asyncio.Runner(loop_factory=lambda: loop) as runner:
            runner.run(_run_scheduler(session_factory, engine))
    finally:
        logger.info("Scheduler worker detenido")


if __name__ == "__main__":
    run()
