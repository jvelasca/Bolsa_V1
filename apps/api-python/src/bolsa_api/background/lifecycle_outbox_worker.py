"""V1.91–V1.93 — continuous LifecycleOutboxWorker (pending → processing → applied|dead).

On-by-default: runs in ``scheduler_worker`` (not FastAPI lifespan). Polls every
few seconds, claims with SKIP LOCKED, drains via AppendLifecycleEvent.
Disable with ``LIFECYCLE_OUTBOX_WORKER_ENABLED=0``.

V1.92: ``tick_seconds`` injectable for PG certification without sleeping 3s×N.

V1.93: TX split — claim+commit (processing durable), then per-row
append+mark+commit so a crash between phases is recoverable via stale reclaim.

V1.97: ``on_after_append_index`` injects mid ``append_many`` (T2 pair atomicity).
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

TICK_SECONDS = 3
_ENV_ENABLED = "LIFECYCLE_OUTBOX_WORKER_ENABLED"

AfterClaimHook = Callable[[list[Any]], Awaitable[None]]
BeforeApplyCommitHook = Callable[[str], Awaitable[None]]
# Re-export shape: (index, event) — same as AppendManyHook.
AfterAppendIndexHook = Callable[[int, Any], Awaitable[None] | None]


def _worker_enabled() -> bool:
    raw = (os.getenv(_ENV_ENABLED) or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


async def _drain_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    on_after_claim: AfterClaimHook | None = None,
    on_before_apply_commit: BeforeApplyCommitHook | None = None,
    on_after_append_index: AfterAppendIndexHook | None = None,
) -> dict[str, Any]:
    """Claim in TX1, apply each row in its own TX2 (V1.93 failure window)."""
    from bolsa_application.lifecycle_event_store import (
        AppendLifecycleEvent,
        PostgresLifecycleEventStore,
    )
    from bolsa_application.lifecycle_outbox import (
        PostgresLifecycleOutboxStore,
        apply_lifecycle_outbox_row,
    )

    async with session_factory() as session:
        try:
            store = PostgresLifecycleOutboxStore(session)
            claimed = await store.claim_batch(limit=50)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    if on_after_claim is not None:
        await on_after_claim(claimed)

    applied = 0
    errors = 0
    for row in claimed:
        async with session_factory() as session:
            try:
                store = PostgresLifecycleOutboxStore(session)
                append = AppendLifecycleEvent(
                    PostgresLifecycleEventStore(
                        session,
                        on_after_append_index=on_after_append_index,
                    )
                )
                # Re-load record from this session's claim snapshot fields.
                result = await apply_lifecycle_outbox_row(store, append, row)
                if on_before_apply_commit is not None:
                    await on_before_apply_commit(row.id)
                await session.commit()
                applied += result["applied"]
                errors += result["errors"]
            except Exception:
                await session.rollback()
                logger.exception(
                    "lifecycle_outbox worker apply failed id=%s (left processing)",
                    row.id,
                )
                errors += 1

    return {
        "drained": len(claimed),
        "applied": applied,
        "errors": errors,
    }


async def lifecycle_outbox_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float = TICK_SECONDS,
    on_after_claim: AfterClaimHook | None = None,
    on_before_apply_commit: BeforeApplyCommitHook | None = None,
    on_after_append_index: AfterAppendIndexHook | None = None,
) -> None:
    logger.info("LifecycleOutboxWorker iniciado (tick=%ss)", tick_seconds)
    while True:
        await asyncio.sleep(tick_seconds)
        if not _worker_enabled():
            continue
        try:
            drain = await _drain_once(
                session_factory,
                on_after_claim=on_after_claim,
                on_before_apply_commit=on_before_apply_commit,
                on_after_append_index=on_after_append_index,
            )
            if drain.get("drained"):
                logger.info("lifecycle_outbox worker drain: %s", drain)
        except Exception:
            logger.exception("lifecycle_outbox worker tick failed")


def start_lifecycle_outbox_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float = TICK_SECONDS,
    on_after_claim: AfterClaimHook | None = None,
    on_before_apply_commit: BeforeApplyCommitHook | None = None,
    on_after_append_index: AfterAppendIndexHook | None = None,
) -> asyncio.Task[None] | None:
    if not _worker_enabled():
        logger.info(
            "LifecycleOutboxWorker desactivado (%s=false)",
            _ENV_ENABLED,
        )
        return None
    return asyncio.create_task(
        lifecycle_outbox_worker_loop(
            session_factory,
            tick_seconds=tick_seconds,
            on_after_claim=on_after_claim,
            on_before_apply_commit=on_before_apply_commit,
            on_after_append_index=on_after_append_index,
        )
    )
