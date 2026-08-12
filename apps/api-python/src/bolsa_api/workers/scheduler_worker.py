"""Proceso separado de workers programados — fuera del `lifespan` de FastAPI (D3).

P0.4: los workers/schedulers/crons vivían embebidos en ``main.lifespan``; con
``uvicorn --workers N`` se duplicaban (una copia por worker del servicio HTTP).
D3 los mueve a **un proceso dedicado** que ejecuta los mismos loops (basados en
los ``start_*`` de ``bolsa_api.background``, que ya gestionan su gate de
configuración), de modo que haya exactamente una instancia de cada cron.

Ejecución:
    python -m bolsa_api.workers.scheduler_worker

Este proceso NO es un worker Arq: los loops son periódicos (``while True`` +
``sleep``) y el gate por-feature es el mismo que usaba FastAPI. Los jobs
scan/optimize siguen siendo gestionados por el worker Arq cuando
``SCAN_QUEUE_BACKEND=arq`` (ver ``arq_worker.py``); en el resto de backends los
loops inline de scan/optimize viven aquí, igual que antes vivían en FastAPI.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.account_migration import run_account_data_migration
from bolsa_infrastructure.database.session import create_engine, create_session_factory
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from bolsa_api.background.auto_sync_worker import start_auto_sync_worker
from bolsa_api.background.core_r_cron_worker import start_core_r_cron_worker
from bolsa_api.background.daily_alert_evaluator import start_daily_alert_evaluator
from bolsa_api.background.estudio_eod_opinion_worker import start_estudio_eod_opinion_worker
from bolsa_api.background.fa_weekly_worker import start_fa_weekly_worker
from bolsa_api.background.index_subscribe_worker import start_index_subscribe_worker
from bolsa_api.background.optimization_worker import start_optimization_worker
from bolsa_api.background.scan_worker import start_scan_worker
from bolsa_api.background.signal_alert_evaluator import start_signal_alert_evaluator
from bolsa_api.background.tracker_schedule_worker import start_tracker_schedule_worker

logger = logging.getLogger(__name__)


def _event_loop_starters() -> list[Any]:
    # Workers periódicos que gestionan su propio gate de configuración.
    return [
        start_daily_alert_evaluator,
        start_signal_alert_evaluator,
        start_tracker_schedule_worker,
        start_fa_weekly_worker,
        start_core_r_cron_worker,
        start_estudio_eod_opinion_worker,
        start_auto_sync_worker,
        start_index_subscribe_worker,
    ]


def _queue_loop_starters() -> list[Any]:
    # Scan/optimize inline: solo si el backend NO es arq (arq lo gestiona aparte).
    settings = get_settings()
    if settings.scan_queue_backend.lower() == "arq":
        return []
    return [start_scan_worker, start_optimization_worker]


async def _run_scheduler(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    # F3a (P1.2): migración de datos de cuentas idempotente UNA vez al arranque
    # del proceso, fuera del path de petición (antes: por-request en el repositorio).
    async with session_factory() as migration_session:
        await run_account_data_migration(migration_session)

    starters = [*_event_loop_starters(), *_queue_loop_starters()]
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

    logger.info("Scheduler worker iniciado")
    try:
        with asyncio.Runner(loop_factory=lambda: loop) as runner:
            runner.run(_run_scheduler(session_factory, engine))
    finally:
        logger.info("Scheduler worker detenido")


if __name__ == "__main__":
    run()
