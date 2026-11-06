"""Latido del LEASE de un scan job ``processing`` (DS-1, auditoría 2.88.179).

``claim_next`` pasa la fila a ``processing`` y escribe ``updated_at`` UNA sola vez. El reaper
(``reconcile_scan_queue``) declara huérfano un ``processing`` cuyo ``updated_at`` superó
``SCAN_JOB_PROCESSING_STALE_SECONDS`` y lo reencola (o lo marca ``failed``). Sin latido, dos
consecuencias reales:

* un scan legítimo más largo que el umbral se reencolaba **mientras seguía vivo**, y podía
  acabar ejecutándose dos veces;
* el umbral no podía bajarse sin arriesgar falsos huérfanos, así que un job realmente colgado
  tardaba en recuperarse.

Este módulo renueva ``updated_at`` desde una tarea independiente. Dos reglas duras:

* **Sesión propia.** El latido NO reutiliza la sesión del job: esa sesión está dentro del
  turno del scan (posiblemente con transacciones abiertas) y un ``UPDATE`` concurrente en la
  misma sesión se encolaría detrás de ella. Cada tick abre y cierra su propia sesión.
* **Para cuando el job deja de estar ``processing``.** Si el scan terminó, falló o el reaper
  lo reencoló, ``renew_processing_lease`` devuelve ``None`` y el latido se detiene: un job ya
  reencolado no debe seguir refrescando su lease (le impediría al poller volver a reclamarlo).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.scan_job_repository import (
    SqlAlchemyScanJobRepository,
)

logger = logging.getLogger(__name__)

#: Suelo de cadencia: un latido más rápido que esto solo gasta conexiones.
MIN_LEASE_HEARTBEAT_SECONDS = 5.0

#: División del umbral de caducidad: tres latidos caben en la vida del lease, así que dos
#: ticks perdidos seguidos (GC, contención de BD) NO producen un falso huérfano.
_LEASE_DIVISOR = 3.0


def lease_heartbeat_interval_seconds(
    *,
    stale_after_seconds: float | None = None,
) -> float:
    """Cadencia del latido derivada del umbral de caducidad (sin variable de entorno nueva)."""
    stale = (
        float(stale_after_seconds)
        if stale_after_seconds is not None
        else float(get_settings().scan_job_processing_stale_seconds)
    )
    return max(MIN_LEASE_HEARTBEAT_SECONDS, stale / _LEASE_DIVISOR)


async def scan_job_lease_heartbeat(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: str,
    *,
    interval_seconds: float | None = None,
) -> None:
    """Renueva ``updated_at`` del job reclamado hasta que deja de estar ``processing``.

    El primer latido espera un intervalo: el claim acaba de escribir ``updated_at``, así que
    renovarlo de inmediato sería una consulta perdida.
    """
    interval = (
        float(interval_seconds)
        if interval_seconds is not None
        else lease_heartbeat_interval_seconds()
    )
    while True:
        await asyncio.sleep(interval)
        try:
            async with session_factory() as session:
                renewed = await SqlAlchemyScanJobRepository(
                    session
                ).renew_processing_lease(job_id)
                await session.commit()
        except Exception:  # noqa: BLE001 — observabilidad: el job sigue siendo el dueño del
            # trabajo. Si el latido falla de forma persistente el reaper lo recuperará; nunca
            # debe tumbar el scan.
            logger.warning(
                "Latido de lease fallido — job=%s (el reaper lo recuperará si caduca)",
                job_id,
                exc_info=True,
            )
            continue
        if renewed is None:
            logger.warning(
                "Latido de lease DETENIDO — job=%s ya no está `processing` (terminó, falló o "
                "fue reencolado por el reaper)",
                job_id,
            )
            return


def start_scan_job_lease_heartbeat(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: str,
    *,
    interval_seconds: float | None = None,
) -> asyncio.Task[None]:
    """Arranca el latido de un job reclamado (tarea de fondo, cancelable)."""
    return asyncio.create_task(
        scan_job_lease_heartbeat(
            session_factory, job_id, interval_seconds=interval_seconds
        )
    )


async def stop_scan_job_lease_heartbeat(task: asyncio.Task[None] | None) -> None:
    """Cancela el latido y espera a que termine (sin propagar la cancelación)."""
    if task is None or task.done():
        return
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


__all__ = [
    "MIN_LEASE_HEARTBEAT_SECONDS",
    "lease_heartbeat_interval_seconds",
    "scan_job_lease_heartbeat",
    "start_scan_job_lease_heartbeat",
    "stop_scan_job_lease_heartbeat",
]
