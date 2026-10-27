"""Salud de ``scan_jobs``: qué autoridad la drena y si hay atasco (T-1).

R12-SCHED deja **una** autoridad por concern: con ``SCAN_QUEUE_BACKEND=arq`` la cola la drena
``arq_worker``; con cualquier otro backend la drena el proceso dedicado
``queue_poll_worker`` (``start_scan_worker`` + ``start_optimization_worker``). El
``scheduler_worker`` **no** la drena a propósito — lo fija
``test_scheduler_no_embebe_scan_ni_optimize``.

El hueco que cierra este módulo: si el despliegue no levanta el proceso dedicado, los scans se
encolan y nadie los ejecuta, y el arranque del scheduler no lo decía. Ahora **declara** la
autoridad y, si hay jobs ``pending`` envejecidos, publica ``scan_queue_stalled`` con la acción
concreta en vez de callar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models.tables import ScanJobRow

logger = logging.getLogger(__name__)

#: Motivos falsables del informe (no son motivos del motor AUTO: no tocan la atribución).
SCAN_QUEUE_HEALTHY = "scan_queue_healthy"
SCAN_QUEUE_STALLED = "scan_queue_stalled"
SCAN_QUEUE_UNKNOWN = "scan_queue_unknown"

#: Un ``pending`` más viejo que esto sin que nadie lo reclame es un atasco, no latencia.
DEFAULT_STALE_AFTER_SECONDS = 300.0

_AUTHORITY_ARQ = "arq_worker"
_AUTHORITY_INLINE = "queue_poll_worker"


def scan_queue_authority(backend: str) -> str:
    """Quién drena ``scan_jobs`` con este ``SCAN_QUEUE_BACKEND``."""
    return _AUTHORITY_ARQ if backend.strip().lower() == "arq" else _AUTHORITY_INLINE


@dataclass(frozen=True, slots=True)
class ScanQueueHealth:
    backend: str
    authority: str
    pending: int
    oldest_pending_seconds: float | None
    stale_after_seconds: float

    @property
    def stalled(self) -> bool:
        if self.oldest_pending_seconds is None:
            return False
        return self.oldest_pending_seconds >= self.stale_after_seconds

    @property
    def reason(self) -> str:
        return SCAN_QUEUE_STALLED if self.stalled else SCAN_QUEUE_HEALTHY


async def inspect_scan_queue(
    session: AsyncSession,
    *,
    backend: str,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    now: datetime | None = None,
) -> ScanQueueHealth:
    """Cuenta ``pending`` y antigüedad del más viejo (sólo lectura)."""
    reference = now or datetime.now(UTC)
    rows = (
        await session.execute(select(ScanJobRow.created_at).where(ScanJobRow.status == "pending"))
    ).scalars().all()
    oldest: float | None = None
    for created_at in rows:
        if created_at is None:
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age = (reference - created_at).total_seconds()
        if oldest is None or age > oldest:
            oldest = age
    return ScanQueueHealth(
        backend=backend,
        authority=scan_queue_authority(backend),
        pending=len(rows),
        oldest_pending_seconds=oldest,
        stale_after_seconds=float(stale_after_seconds),
    )


def _log_health(health: ScanQueueHealth) -> None:
    if health.stalled:
        logger.error(
            "Cola de scan ATASCADA — reason=%s authority=%s backend=%s pending=%d "
            "oldestPending=%.0fs staleAfter=%.0fs. Nadie está drenando scan_jobs: arranca el "
            "proceso dedicado `bolsa-queue-poll-worker` (o usa SCAN_QUEUE_BACKEND=arq con "
            "arq_worker vivo).",
            health.reason,
            health.authority,
            health.backend,
            health.pending,
            health.oldest_pending_seconds or 0.0,
            health.stale_after_seconds,
        )
        return
    logger.info(
        "Cola de scan — reason=%s authority=%s backend=%s pending=%d oldestPending=%s",
        health.reason,
        health.authority,
        health.backend,
        health.pending,
        "n/a" if health.oldest_pending_seconds is None else f"{health.oldest_pending_seconds:.0f}s",
    )


async def report_scan_queue_health(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
) -> ScanQueueHealth | None:
    """Declara la autoridad de la cola al arrancar; ``None`` si no se pudo leer.

    Fail-soft a propósito: un problema de lectura de la cola no debe tumbar el scheduler (el
    resto de crons son independientes), pero sí quedar declarado con ``scan_queue_unknown``.
    """
    backend = get_settings().scan_queue_backend
    try:
        async with session_factory() as session:
            health = await inspect_scan_queue(
                session, backend=backend, stale_after_seconds=stale_after_seconds
            )
    except Exception:  # noqa: BLE001 — observabilidad, nunca un aborto del arranque.
        logger.warning(
            "No se pudo leer la cola de scan — reason=%s authority=%s backend=%s",
            SCAN_QUEUE_UNKNOWN,
            scan_queue_authority(backend),
            backend,
            exc_info=True,
        )
        return None
    _log_health(health)
    return health


__all__ = [
    "DEFAULT_STALE_AFTER_SECONDS",
    "SCAN_QUEUE_HEALTHY",
    "SCAN_QUEUE_STALLED",
    "SCAN_QUEUE_UNKNOWN",
    "ScanQueueHealth",
    "inspect_scan_queue",
    "report_scan_queue_health",
    "scan_queue_authority",
]
