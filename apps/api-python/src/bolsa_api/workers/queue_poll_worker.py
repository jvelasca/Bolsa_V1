"""Proceso dedicado al poll de colas scan/optimize (no-ARQ) — R12-SCHED / R-8C.2.

Una autoridad por concern: el ``scheduler_worker`` solo corre crons periódicos.
Este proceso es la autoridad de poll inline cuando ``SCAN_QUEUE_BACKEND`` no es
``arq``. Con ``arq``, la autoridad es ``arq_worker`` y este proceso hace no-op
(exit 0) para no doble-ejecutar.

Ejecución:
    python -m bolsa_api.workers.queue_poll_worker
    # o: bolsa-queue-poll-worker
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from bolsa_api.background.optimization_worker import start_optimization_worker
from bolsa_api.background.scan_worker import start_scan_worker
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.migrations import database_bootstrap
from bolsa_infrastructure.database.session import create_engine, create_session_factory

logger = logging.getLogger(__name__)


def _queue_loop_starters() -> list[Any]:
    """Starters de poll inline; vacío si ARQ es la autoridad de colas."""
    settings = get_settings()
    if settings.scan_queue_backend.lower() == "arq":
        return []
    return [start_scan_worker, start_optimization_worker]


async def _run_queue_poll(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    # Mismo bootstrap que scheduler: solo-start seguro; advisory lock serializa.
    await database_bootstrap(engine=engine, session_factory=session_factory)

    starters = _queue_loop_starters()
    tasks: list[asyncio.Task[None]] = []
    for starter in starters:
        task = starter(session_factory)
        if task is not None:
            tasks.append(task)

    if not tasks:
        logger.warning(
            "Ningún queue poll activo — SCAN_QUEUE_BACKEND=%s (esperado no-arq)",
            get_settings().scan_queue_backend,
        )

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # pragma: no cover — Windows
            pass

    await stop.wait()
    logger.info("Señal de parada recibida — cancelando queue poll workers…")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await engine.dispose()


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()

    if settings.scan_queue_backend.lower() == "arq":
        logger.info(
            "SCAN_QUEUE_BACKEND=arq — queue_poll_worker no-op; "
            "las colas las gestiona arq_worker (R12-SCHED / R-8C.2)"
        )
        return

    engine: AsyncEngine = create_engine(settings)
    session_factory = create_session_factory(engine)

    # En Windows, asyncio.run() usa ProactorEventLoop por defecto, incompatible
    # con psycopg async. Forzar SelectorEventLoop (mismo motivo que scheduler).
    loop: asyncio.AbstractEventLoop
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
    else:
        loop = asyncio.new_event_loop()

    logger.info(
        "Queue poll worker iniciado (backend=%s; scan + optimize)",
        settings.scan_queue_backend,
    )
    try:
        with asyncio.Runner(loop_factory=lambda: loop) as runner:
            runner.run(_run_queue_poll(session_factory, engine))
    finally:
        logger.info("Queue poll worker detenido")


if __name__ == "__main__":
    run()
