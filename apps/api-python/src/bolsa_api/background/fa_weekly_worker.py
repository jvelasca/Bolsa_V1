"""Worker — pipeline semanal FA → whitelist → Paper D (off-by-default)."""

from __future__ import annotations

import asyncio
import logging

from bolsa_analytics.signals.fundamental_screener import week_key_utc
from bolsa_application.fa_weekly_pipeline import (
    build_cron_payload_from_settings,
    is_fa_weekly_window,
)
from bolsa_infrastructure.config import get_settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import get_run_fa_weekly_pipeline_use_case

logger = logging.getLogger(__name__)

_last_ran_week_key: str | None = None


async def _run_fa_weekly_once(session_factory: async_sessionmaker[AsyncSession]) -> str | None:
    global _last_ran_week_key
    settings = get_settings()
    payload = build_cron_payload_from_settings(settings)
    if payload is None:
        logger.warning(
            "FA weekly cron: FA_WEEKLY_UNIVERSE_LIST_ID no definido — skip"
        )
        return None

    week = week_key_utc()
    if _last_ran_week_key == week:
        return None

    async with session_factory() as session:
        try:
            result = await get_run_fa_weekly_pipeline_use_case(session).execute(payload)
            await session.commit()
            _last_ran_week_key = week
            logger.info(
                "FA weekly pipeline %s: status=%s hits=%s elegibles=%s execute=%s",
                week,
                result.get("status"),
                (result.get("screener") or {}).get("hitCount"),
                (result.get("propose") or {}).get("eligibleCount"),
                (result.get("propose") or {}).get("executeStatus"),
            )
            return week
        except Exception:
            await session.rollback()
            raise


async def fa_weekly_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(60, int(settings.fa_weekly_cron_interval_seconds))
    weekday = int(settings.fa_weekly_weekday)
    hour = int(settings.fa_weekly_hour)
    logger.info(
        "Worker FA weekly iniciado — intervalo %ds · weekday=%s hour>=%s Madrid",
        interval,
        weekday,
        hour,
    )

    while True:
        await asyncio.sleep(interval)
        settings = get_settings()
        if not is_fa_weekly_window(
            weekday=int(settings.fa_weekly_weekday),
            hour=int(settings.fa_weekly_hour),
        ):
            continue
        try:
            await _run_fa_weekly_once(session_factory)
        except Exception:
            logger.exception("Error en worker FA weekly")


def start_fa_weekly_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    settings = get_settings()
    if not settings.fa_weekly_cron_enabled:
        logger.info("FA weekly worker desactivado (FA_WEEKLY_CRON_ENABLED=false)")
        return None
    return asyncio.create_task(fa_weekly_worker_loop(session_factory))
