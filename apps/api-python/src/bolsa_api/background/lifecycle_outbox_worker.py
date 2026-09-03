"""V1.91 — continuous LifecycleOutboxWorker (pending → processing → applied|dead).

On-by-default: runs in ``scheduler_worker`` (not FastAPI lifespan). Polls every
few seconds, claims with SKIP LOCKED, drains via AppendLifecycleEvent.
Disable with ``LIFECYCLE_OUTBOX_WORKER_ENABLED=0``.
"""

from __future__ import annotations

import asyncio
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

TICK_SECONDS = 3
_ENV_ENABLED = "LIFECYCLE_OUTBOX_WORKER_ENABLED"


def _worker_enabled() -> bool:
    raw = (os.getenv(_ENV_ENABLED) or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


async def _drain_once(session_factory: async_sessionmaker[AsyncSession]) -> dict:
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        PostgresLifecycleEventStore,
    )
    from bolsa_application.lifecycle_outbox import (
        PostgresLifecycleOutboxStore,
        drain_lifecycle_outbox,
    )

    async with session_factory() as session:
        try:
            drain = await drain_lifecycle_outbox(
                PostgresLifecycleOutboxStore(session),
                AppendLifecycleEvent(PostgresLifecycleEventStore(session)),
            )
            await session.commit()
            return drain
        except Exception:
            await session.rollback()
            raise


async def lifecycle_outbox_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    logger.info("LifecycleOutboxWorker iniciado (tick=%ss)", TICK_SECONDS)
    while True:
        await asyncio.sleep(TICK_SECONDS)
        if not _worker_enabled():
            continue
        try:
            drain = await _drain_once(session_factory)
            if drain.get("drained"):
                logger.info("lifecycle_outbox worker drain: %s", drain)
        except Exception:
            logger.exception("lifecycle_outbox worker tick failed")


def start_lifecycle_outbox_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    if not _worker_enabled():
        logger.info(
            "LifecycleOutboxWorker desactivado (%s=false)",
            _ENV_ENABLED,
        )
        return None
    return asyncio.create_task(lifecycle_outbox_worker_loop(session_factory))
