"""Evaluación programada de alertas daily_close tras el cierre del IBEX."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import get_evaluate_alerts_use_case

logger = logging.getLogger(__name__)

MADRID = ZoneInfo("Europe/Madrid")
CHECK_INTERVAL_SECONDS = 15 * 60
POST_CLOSE_HOUR = 17
POST_CLOSE_MINUTE = 35

_last_daily_eval_date: date | None = None


def _is_post_ibex_close_window(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    if now.hour > POST_CLOSE_HOUR:
        return True
    if now.hour == POST_CLOSE_HOUR and now.minute >= POST_CLOSE_MINUTE:
        return True
    return False


async def _evaluate_daily_close_alerts(session_factory: async_sessionmaker[AsyncSession]) -> int:
    global _last_daily_eval_date

    async with session_factory() as session:
        try:
            result = await get_evaluate_alerts_use_case(session).execute(
                price_source_filter="daily_close",
            )
            await session.commit()
            triggered = len(result.triggered)
            if triggered:
                symbols = ", ".join(item.symbol for item in result.triggered)
                logger.info("Alertas daily_close disparadas: %s", symbols)
            return triggered
        except Exception:
            await session.rollback()
            raise


async def daily_alert_evaluator_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    global _last_daily_eval_date

    logger.info("Monitor post-cierre de alertas daily_close iniciado")
    while True:
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        now = datetime.now(MADRID)
        if not _is_post_ibex_close_window(now):
            continue
        if _last_daily_eval_date == now.date():
            continue
        try:
            await _evaluate_daily_close_alerts(session_factory)
            _last_daily_eval_date = now.date()
        except Exception:
            logger.exception("Error evaluando alertas daily_close programadas")


def start_daily_alert_evaluator(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None]:
    return asyncio.create_task(daily_alert_evaluator_loop(session_factory))
