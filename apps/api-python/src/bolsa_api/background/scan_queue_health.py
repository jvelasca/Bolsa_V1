"""Salud de ``scan_jobs``: qué autoridad la drena y si hay atasco (T-1 / DS-1).

R12-SCHED deja **una** autoridad por concern: con ``SCAN_QUEUE_BACKEND=arq`` la cola la drena
``arq_worker``; con cualquier otro backend la drena el proceso dedicado
``queue_poll_worker`` (``start_scan_worker`` + ``start_optimization_worker``). El
``scheduler_worker`` **no** la drena a propósito — lo fija
``test_scheduler_no_embebe_scan_ni_optimize``.

El hueco que cierra este módulo: si el despliegue no levanta el proceso dedicado, los scans se
encolan y nadie los ejecuta, y el arranque del scheduler no lo decía. Ahora **declara** la
autoridad y, si hay jobs ``pending`` envejecidos, publica ``scan_queue_stalled`` con la acción
concreta en vez de callar.

**DS-1 (auditoría 2.88.179).** El chequeo era UNA vez al arrancar y solo miraba ``pending``.
Un job ``processing`` cuyo proceso murió tras reclamarlo quedaba invisible, y como
``processing`` cuenta en el dedupe del scan diario, bloqueaba el reintento de ese día. Ahora
hay un **vigía periódico** que, además de medir, recupera los ``processing`` huérfanos
(reencola inline, declara ``failed`` con ``arq``) y lo publica en cada ciclo.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.models.tables import ScanJobRow
from bolsa_infrastructure.database.repositories.scan_job_repository import (
    SqlAlchemyScanJobRepository,
)

logger = logging.getLogger(__name__)

#: Motivos falsables del informe (no son motivos del motor AUTO: no tocan la atribución).
SCAN_QUEUE_HEALTHY = "scan_queue_healthy"
SCAN_QUEUE_STALLED = "scan_queue_stalled"
SCAN_QUEUE_PROCESSING_STALE = "scan_queue_processing_stale"
SCAN_QUEUE_UNKNOWN = "scan_queue_unknown"

#: Un ``pending`` más viejo que esto sin que nadie lo reclame es un atasco, no latencia.
DEFAULT_STALE_AFTER_SECONDS = 300.0

#: DS-1 — un ``processing`` cuyo lease (``updated_at``) es más viejo que esto es huérfano.
#: Es el MISMO default que ``SCAN_JOB_PROCESSING_STALE_SECONDS``.
DEFAULT_STALE_PROCESSING_AFTER_SECONDS = 3600.0

#: Suelo de cadencia del vigía: un loop más rápido que esto solo gasta BD.
_MIN_HEALTH_INTERVAL_SECONDS = 60.0

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
    #: DS-1 — jobs ``processing`` vivos y antigüedad del más viejo (edad de su lease).
    processing: int = 0
    oldest_processing_seconds: float | None = None
    stale_processing: int = 0
    stale_processing_after_seconds: float = DEFAULT_STALE_PROCESSING_AFTER_SECONDS

    @property
    def stalled(self) -> bool:
        if self.stale_processing > 0:
            return True
        if self.oldest_pending_seconds is None:
            return False
        return self.oldest_pending_seconds >= self.stale_after_seconds

    @property
    def reason(self) -> str:
        if self.stale_processing > 0:
            return SCAN_QUEUE_PROCESSING_STALE
        return SCAN_QUEUE_STALLED if self.stalled else SCAN_QUEUE_HEALTHY


def _age_seconds(value: datetime | None, reference: datetime) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return (reference - value).total_seconds()


async def inspect_scan_queue(
    session: AsyncSession,
    *,
    backend: str,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    stale_processing_after_seconds: float = DEFAULT_STALE_PROCESSING_AFTER_SECONDS,
    now: datetime | None = None,
) -> ScanQueueHealth:
    """Mide ``pending`` y ``processing`` (sólo lectura).

    El ``pending`` se mide por ``created_at`` (cuánto lleva esperando); el ``processing`` por
    ``updated_at`` (cuánto lleva sin latido desde que se reclamó). Un ``processing`` más viejo
    que ``stale_processing_after_seconds`` cuenta como huérfano y es atasco.
    """
    reference = now or datetime.now(UTC)
    rows = (
        await session.execute(
            select(
                ScanJobRow.status,
                ScanJobRow.created_at,
                ScanJobRow.updated_at,
            ).where(ScanJobRow.status.in_(("pending", "processing")))
        )
    ).all()
    pending = 0
    processing = 0
    oldest_pending: float | None = None
    oldest_processing: float | None = None
    stale_processing = 0
    for status, created_at, updated_at in rows:
        if status == "pending":
            pending += 1
            age = _age_seconds(created_at, reference)
            if age is not None and (oldest_pending is None or age > oldest_pending):
                oldest_pending = age
            continue
        processing += 1
        age = _age_seconds(updated_at, reference)
        if age is None:
            continue
        if oldest_processing is None or age > oldest_processing:
            oldest_processing = age
        if age >= stale_processing_after_seconds:
            stale_processing += 1
    return ScanQueueHealth(
        backend=backend,
        authority=scan_queue_authority(backend),
        pending=pending,
        oldest_pending_seconds=oldest_pending,
        stale_after_seconds=float(stale_after_seconds),
        processing=processing,
        oldest_processing_seconds=oldest_processing,
        stale_processing=stale_processing,
        stale_processing_after_seconds=float(stale_processing_after_seconds),
    )


def _log_health(health: ScanQueueHealth) -> None:
    if health.stale_processing > 0:
        logger.error(
            "Cola de scan ATASCADA — reason=%s authority=%s backend=%s processing=%d "
            "staleProcessing=%d oldestProcessing=%s staleProcessingAfter=%.0fs. Un job "
            "`processing` sin latido bloquea el dedupe del scan diario: el vigía lo "
            "reencola si la autoridad es `queue_poll_worker` o lo declara `failed` con "
            "`arq_worker`; si se repite, revisa el proceso que reclama "
            "(`bolsa-queue-poll-worker`).",
            health.reason,
            health.authority,
            health.backend,
            health.processing,
            health.stale_processing,
            "n/a"
            if health.oldest_processing_seconds is None
            else f"{health.oldest_processing_seconds:.0f}s",
            health.stale_processing_after_seconds,
        )
        return
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
        "Cola de scan — reason=%s authority=%s backend=%s pending=%d oldestPending=%s "
        "processing=%d oldestProcessing=%s",
        health.reason,
        health.authority,
        health.backend,
        health.pending,
        "n/a" if health.oldest_pending_seconds is None else f"{health.oldest_pending_seconds:.0f}s",
        health.processing,
        "n/a"
        if health.oldest_processing_seconds is None
        else f"{health.oldest_processing_seconds:.0f}s",
    )


async def report_scan_queue_health(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
) -> ScanQueueHealth | None:
    """Declara la autoridad de la cola UNA vez; ``None`` si no se pudo leer.

    Fail-soft a propósito: un problema de lectura de la cola no debe tumbar el scheduler (el
    resto de crons son independientes), pero sí quedar declarado con ``scan_queue_unknown``.
    El seguimiento continuo (y la recuperación de ``processing`` huérfanos) es
    ``scan_queue_health_worker_loop``.
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


async def reconcile_scan_queue(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stale_processing_after_seconds: float = DEFAULT_STALE_PROCESSING_AFTER_SECONDS,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    requeue: bool | None = None,
    max_reaps: int = 3,
    now: datetime | None = None,
) -> ScanQueueHealth | None:
    """Recupera los ``processing`` huérfanos y devuelve la salud resultante.

    ``requeue=None`` lo deriva de la AUTORIDAD: con ``queue_poll_worker`` se reencola (es el
    poller quien lo reclamaría), con ``arq_worker`` se declara ``failed`` (devolver la fila a
    ``pending`` no republica nada en Redis). ``None`` como retorno significa «no se pudo leer»:
    se declara ``scan_queue_unknown`` y NO se tumba el proceso.
    """
    backend = get_settings().scan_queue_backend
    reference = now or datetime.now(UTC)
    should_requeue = (
        scan_queue_authority(backend) == _AUTHORITY_INLINE if requeue is None else requeue
    )
    try:
        async with session_factory() as session:
            repository = SqlAlchemyScanJobRepository(session)
            reaped = await repository.reap_stale_processing(
                stale_before=reference
                - timedelta(seconds=max(0.0, float(stale_processing_after_seconds))),
                requeue=should_requeue,
                max_reaps=max_reaps,
                now=reference,
            )
            await session.commit()
            for job in reaped:
                if job.status == "pending":
                    logger.warning(
                        "Scan job HUÉRFANO reencolado — job=%s reaps=%s staleProcessingAfter="
                        "%.0fs (el proceso que lo reclamó no lo terminó)",
                        job.id,
                        job.payload.get("_reapCount"),
                        stale_processing_after_seconds,
                    )
                else:
                    logger.error(
                        "Scan job HUÉRFANO declarado failed — job=%s reaps=%s error=%s",
                        job.id,
                        job.payload.get("_reapCount"),
                        job.error,
                    )
            health = await inspect_scan_queue(
                session,
                backend=backend,
                stale_after_seconds=stale_after_seconds,
                stale_processing_after_seconds=stale_processing_after_seconds,
                now=reference,
            )
    except Exception:  # noqa: BLE001 — observabilidad, nunca un aborto del proceso.
        logger.warning(
            "No se pudo reconciliar la cola de scan — reason=%s authority=%s backend=%s",
            SCAN_QUEUE_UNKNOWN,
            scan_queue_authority(backend),
            backend,
            exc_info=True,
        )
        return None
    return health


async def scan_queue_health_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    interval_seconds: float | None = None,
) -> None:
    """Vigía periódico de la cola: mide, recupera huérfanos y declara el cambio de estado.

    `DS-1`: antes se miraba **una sola vez**, al arrancar. Un ``processing`` colgado durante
    la vida del proceso no se detectaba nunca.
    """
    settings = get_settings()
    stale_seconds = float(settings.scan_job_processing_stale_seconds)
    max_reaps = int(settings.scan_job_processing_max_reaps)
    interval = max(
        _MIN_HEALTH_INTERVAL_SECONDS,
        float(
            interval_seconds
            if interval_seconds is not None
            else settings.scan_queue_health_interval_seconds
        ),
    )
    logger.info(
        "Worker SALUD DE COLA DE SCAN iniciado — intervalo %.0fs · backend=%s · "
        "staleProcessingAfter=%.0fs · primer tick inmediato",
        interval,
        settings.scan_queue_backend,
        stale_seconds,
    )
    last_reason: str | None = None
    while True:
        try:
            health = await reconcile_scan_queue(
                session_factory,
                stale_processing_after_seconds=stale_seconds,
                max_reaps=max_reaps,
            )
            # El INFO de «sana» no se repite cada ciclo; un atasco sí se declara siempre.
            if health is not None and (health.stalled or health.reason != last_reason):
                _log_health(health)
                last_reason = health.reason
        except Exception:  # noqa: BLE001 — el vigía no puede tumbarse a sí mismo.
            logger.exception("Error en el vigía de la cola de scan")
        await asyncio.sleep(interval)


def start_scan_queue_health_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    """Arranca el vigía periódico (siempre activo: es observabilidad, no una cola)."""
    return asyncio.create_task(scan_queue_health_worker_loop(session_factory))


__all__ = [
    "DEFAULT_STALE_AFTER_SECONDS",
    "DEFAULT_STALE_PROCESSING_AFTER_SECONDS",
    "SCAN_QUEUE_HEALTHY",
    "SCAN_QUEUE_PROCESSING_STALE",
    "SCAN_QUEUE_STALLED",
    "SCAN_QUEUE_UNKNOWN",
    "ScanQueueHealth",
    "inspect_scan_queue",
    "reconcile_scan_queue",
    "report_scan_queue_health",
    "scan_queue_authority",
    "scan_queue_health_worker_loop",
    "start_scan_queue_health_worker",
]
