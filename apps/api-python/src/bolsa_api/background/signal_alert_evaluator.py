"""Evaluación periódica de alertas de estrategia (SC-6) — webhook/email sin cliente abierto."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import get_evaluate_signal_alerts_use_case
from bolsa_infrastructure.config import get_settings

logger = logging.getLogger(__name__)


async def _evaluate_signal_alerts_once(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        try:
            result = await get_evaluate_signal_alerts_use_case(session).execute()
            await session.commit()

            if not result.triggered:
                return

            for hit in result.triggered:
                logger.info(
                    "Alerta estrategia %s %s @ %.4f (subscription=%s)",
                    hit.subscription.symbol,
                    hit.signal.kind,
                    hit.signal.price,
                    hit.subscription.id,
                )

            for dispatch in result.dispatches:
                if dispatch.ok:
                    logger.info(
                        "Canal %s OK — subscription=%s",
                        dispatch.channel,
                        dispatch.subscription_id,
                    )
                else:
                    logger.warning(
                        "Canal %s falló — subscription=%s: %s",
                        dispatch.channel,
                        dispatch.subscription_id,
                        dispatch.error,
                    )
        except Exception:
            await session.rollback()
            raise


async def signal_alert_evaluator_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(5, int(settings.signal_alert_eval_interval_seconds))
    logger.info("Monitor alertas de estrategia iniciado — intervalo %ds", interval)

    while True:
        await asyncio.sleep(interval)
        try:
            await _evaluate_signal_alerts_once(session_factory)
        except Exception:
            logger.exception("Error evaluando alertas de estrategia programadas")


def start_signal_alert_evaluator(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None]:
    return asyncio.create_task(signal_alert_evaluator_loop(session_factory))
