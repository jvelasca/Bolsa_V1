"""V2.21 / A8 (M2) — ExecutionEventReaperWorker (autónomo, cableado en scheduler).

Cierra el gap del audit §4: el "reaper" de ``APPLYING`` stale existía como función
(``reap_stale_applying`` en ``execution_event.py``) pero no se ejecutaba en ningún
ciclo normal. Este worker lo convierte en un crons continuo y autónomo (patrón
``asyncio`` de `scheduler_worker`), SIN depender de HTTP.

Seguridad (M1/A8): solo se activa tras el fencing estructural ``lease_generation``.
Proceso por tick (en su propia sesión, commit por fase):

1. ``reap_stale_applying``: reclama filas ``APPLYING`` cuyo ``updated_at`` venció
   (lease del dueño muerto). El reclaim ROBA el fence (bump de generación), de modo
   que un dueño viejo ya NO puede finalizar (M1 lo prueba con PG real).
2. Sin ``resolve_candidate``/``apply_finance`` (este worker NO fabrica aritmética
   financiera — H4) baja las huérfanas a ``RETRY`` reaplicable o deja intacto un
   ``APPLIED`` ya resuelto. No abre NINGUNA vía real ni fabrica ledger.

Habilitado por defecto (tras M1 es seguro). Deshabilitable con
``EXECUTION_EVENT_REAPER_ENABLED=0``. Un heartbeat legítimo (``renew_apply_lease``)
evita que un apply largo de un dueño vivo sea acusado de stale.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta

from bolsa_application.execution_event import reap_stale_applying
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

TICK_SECONDS = 5
_ENV_ENABLED = "EXECUTION_EVENT_REAPER_ENABLED"
_DEFAULT_BATCH = 50
# Aplica la misma ventana de lease que el dominio (updated_at viejo = dueño muerto).
LEASE_GRACE_SECONDS = 30


def _worker_enabled() -> bool:
    raw = (os.getenv(_ENV_ENABLED) or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _owner_identity() -> str:
    try:
        return f"exec-reaper-{os.getpid()}"
    except AttributeError:  # pragma: no cover
        return f"exec-reaper-{id(object())}"


async def _reap_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    limit: int = _DEFAULT_BATCH,
) -> dict[str, int]:
    """Un barrido: reclaim de APPLYING stale → liberación a RETRY (o intacto si ya
    APPLIED). No fabrica dinero ni toca la vía LIVE."""
    from bolsa_application.execution_event import PostgresExecutionEventStore

    counts: dict[str, int] = {
        "reclaimed": 0,
        "applied": 0,
        "already_applied": 0,
        "retry": 0,
        "failed": 0,
        "errors": 0,
    }
    async with session_factory() as session:
        try:
            store = PostgresExecutionEventStore(session)
            stale_before = datetime.now(UTC) - timedelta(seconds=LEASE_GRACE_SECONDS)
            result = await reap_stale_applying(
                store,
                owner=_owner_identity(),
                stale_before=stale_before,
                limit=limit,
                # Sin resolver/apply: este reaper solo LIBERA huérfanas a RETRY.
                # La (re)materialización real vuelve por el camino durable de la
                # reconciliación de cada venue (resolve_candidate → apply), jamás aquí.
                resolve_candidate=None,
                apply_finance=None,
            )
            counts.update(result)
        except Exception:
            await session.rollback()
            raise
    return counts


async def execution_event_reaper_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float = TICK_SECONDS,
    limit: int = _DEFAULT_BATCH,
) -> None:
    wid = _owner_identity()
    logger.info("ExecutionEventReaperWorker iniciado (tick=%ss worker=%s)", tick_seconds, wid)
    while True:
        await asyncio.sleep(tick_seconds)
        if not _worker_enabled():
            continue
        try:
            counts = await _reap_once(session_factory, limit=limit)
            if counts.get("reclaimed"):
                logger.info("execution_event reaper reclaimed=%s", counts)
        except Exception:  # noqa: BLE001 — un tick no tumba el worker.
            logger.exception("execution_event reaper tick failed")


def start_execution_event_reaper_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float = TICK_SECONDS,
    limit: int = _DEFAULT_BATCH,
) -> asyncio.Task[None] | None:
    if not _worker_enabled():
        logger.info(
            "ExecutionEventReaperWorker desactivado (%s=false)",
            _ENV_ENABLED,
        )
        return None
    return asyncio.create_task(
        execution_event_reaper_worker_loop(
            session_factory,
            tick_seconds=tick_seconds,
            limit=limit,
        )
    )
