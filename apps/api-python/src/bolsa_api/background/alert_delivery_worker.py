"""Worker periódico del OUTBOX de alertas de señal (v2.88.137).

AUDITORIA3 (hallazgo 5, ``Parcialmente corregido``): la entrega de una alerta de señal ya no se
pierde —vive en ``alert_deliveries`` con estados, backoff y dead letter— pero hasta ahora sólo la
drenaba el endpoint ``POST /signal-alerts/deliveries/process``, pensado para un cron EXTERNO. Si
ese cron no se despliega ni se supervisa, una entrega fallida no se reintenta tras la barra
inicial. Este worker CIERRA ese hueco: ejecuta ``ProcessAlertDeliveries.execute()`` cada pocos
segundos desde el proceso dedicado de crons (``bolsa_api.workers.scheduler_worker``), con métrica
de ``RETRYABLE_FAILED`` y **alerta explícita** sobre ``DEAD_LETTER`` (WARNING por cada fila que
agota su presupuesto). El endpoint queda como disparador manual adicional; ya no es el único.

Reglas duras:

* **On-by-default** (``ALERT_DELIVERY_WORKER_ENABLED``; se apaga con ``0/false/no/off``), como el
  outbox de lifecycle: un reintento garantizado no puede depender de una variable ausente.
* **No toca la decisión.** Sólo reintenta entregas ya encoladas por la evaluación de alertas;
  nunca crea señales, no altera umbrales ni ejecuta órdenes.
* **Idempotente y sin ámbito de cuenta**: reclama CUALQUIER entrega vencida (el dueño viaja en la
  fila); el claim con lease (``FOR UPDATE SKIP LOCKED``) garantiza un único worker por fila.
* **Fail-safe por tick**: un error del tick se registra y NO mata el bucle.

@see packages/py/application/src/bolsa_application/signal_alerts.py (ProcessAlertDeliveries)
@see apps/api-python/src/bolsa_api/background/lifecycle_outbox_worker.py (patrón)
"""

from __future__ import annotations

import asyncio
import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import get_process_alert_deliveries_use_case
from bolsa_infrastructure.config import get_settings

logger = logging.getLogger(__name__)

TICK_SECONDS = 15.0
DELIVERY_BATCH_LIMIT = 50
_ENV_ENABLED = "ALERT_DELIVERY_WORKER_ENABLED"


def _worker_enabled() -> bool:
    raw = (os.getenv(_ENV_ENABLED) or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


async def _process_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    limit: int = DELIVERY_BATCH_LIMIT,
) -> dict[str, int]:
    """Drena una tanda de entregas vencidas y devuelve el recuento por desenlace.

    Claves: ``claimed`` (filas reclamadas), ``delivered`` (entrega OK),
    ``retryable_failed`` (fallo con reintento programado) y ``dead_letter`` (presupuesto agotado).
    """
    async with session_factory() as session:
        try:
            dispatches = await get_process_alert_deliveries_use_case(session).execute(limit=limit)
        except Exception:
            await session.rollback()
            raise

    summary = {
        "claimed": len(dispatches),
        "delivered": 0,
        "retryable_failed": 0,
        "dead_letter": 0,
    }
    for dispatch in dispatches:
        if dispatch.ok:
            summary["delivered"] += 1
        elif dispatch.will_retry:
            summary["retryable_failed"] += 1
        else:
            summary["dead_letter"] += 1
            # ALERTA: una entrega que agotó su presupuesto NUNCA se pierde en silencio.
            logger.warning(
                "Alerta OUTBOX DEAD_LETTER subscription=%s channel=%s delivery=%s attempt=%s: %s",
                dispatch.subscription_id,
                dispatch.channel,
                dispatch.delivery_id,
                dispatch.attempt,
                dispatch.error,
            )
    return summary


async def alert_delivery_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float | None = None,
    limit: int = DELIVERY_BATCH_LIMIT,
) -> None:
    settings = get_settings()
    interval = (
        float(tick_seconds)
        if tick_seconds is not None
        else max(5.0, float(settings.alert_delivery_worker_interval_seconds))
    )
    logger.info("AlertDeliveryWorker iniciado (tick=%ss)", interval)
    while True:
        await asyncio.sleep(interval)
        if not _worker_enabled():
            continue
        try:
            summary = await _process_once(session_factory, limit=limit)
            if summary["claimed"]:
                # Métrica por tick: permite observar RETRYABLE_FAILED y DEAD_LETTER en logs.
                logger.info("alert_delivery worker tick: %s", summary)
        except Exception:
            logger.exception("alert_delivery worker tick failed")


def start_alert_delivery_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float | None = None,
    limit: int = DELIVERY_BATCH_LIMIT,
) -> asyncio.Task[None] | None:
    if not _worker_enabled():
        logger.info("AlertDeliveryWorker desactivado (%s=false)", _ENV_ENABLED)
        return None
    return asyncio.create_task(
        alert_delivery_worker_loop(session_factory, tick_seconds=tick_seconds, limit=limit)
    )


__all__ = [
    "DELIVERY_BATCH_LIMIT",
    "TICK_SECONDS",
    "alert_delivery_worker_loop",
    "start_alert_delivery_worker",
]
