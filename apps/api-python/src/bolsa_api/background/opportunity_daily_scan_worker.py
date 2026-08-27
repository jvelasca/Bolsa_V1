"""Worker — Opportunity daily scan opt-in (V1.19).

Off-by-default: ``OPPORTUNITY_DAILY_SCAN_ENABLED=false``.
Encola scan contra universo configurado (default ibex35).
Propose acotado solo si hay ``OPPORTUNITY_DAILY_ACCOUNT_ID`` o cuenta con
``settings_json.opportunityDailyScanEnabled``.
Nunca execute / AUTO / Router.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import get_enqueue_scan_job_use_case
from bolsa_application.opportunity_daily_discovery import (
    DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
    EnqueueOpportunityDailyScan,
    account_wants_daily_scan,
    resolve_universe_list_id,
)
from bolsa_infrastructure.config import get_settings

logger = logging.getLogger(__name__)

_last_ran_day_key: str | None = None


def _utc_day_key() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


async def _resolve_targets(session: AsyncSession) -> list[dict[str, Any]]:
    """Cuentas a enriquecer con propose; scan siempre se encola al menos una vez."""
    settings = get_settings()
    env_account = (settings.opportunity_daily_account_id or "").strip() or None
    list_id = (
        (settings.opportunity_daily_universe_list_id or "").strip()
        or DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID
    )
    propose_cap = int(settings.opportunity_daily_propose_cap)

    targets: list[dict[str, Any]] = []
    if env_account:
        targets.append(
            {
                "accountId": env_account,
                "listId": list_id,
                "proposeCap": propose_cap,
            }
        )
        return targets

    # Preferencias por cuenta (opt-in en settings_json)
    try:
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )

        repo = SqlAlchemyAccountRepository(session)
        accounts = await repo.list_accounts()
        for acc in accounts:
            acc_id = getattr(acc, "id", None) or getattr(acc, "account_id", None)
            if not acc_id:
                continue
            status = getattr(acc, "status", None)
            if status and str(status).lower() not in {"active", "open"}:
                continue
            raw_settings = None
            getter = getattr(repo, "get_settings_json", None)
            if callable(getter):
                raw_settings = await getter(str(acc_id))
            if not account_wants_daily_scan(raw_settings):
                continue
            targets.append(
                {
                    "accountId": str(acc_id),
                    "listId": resolve_universe_list_id(raw_settings, default=list_id),
                    "proposeCap": propose_cap,
                }
            )
    except Exception:
        logger.exception("Opportunity daily: no se pudieron listar cuentas opt-in")

    if not targets:
        # Scan-only (funnel) sin propose — una cola global
        targets.append(
            {
                "accountId": None,
                "listId": list_id,
                "proposeCap": propose_cap,
            }
        )
    return targets


async def _run_opportunity_daily_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> str | None:
    global _last_ran_day_key
    day = _utc_day_key()
    if _last_ran_day_key == day:
        return None

    async with session_factory() as session:
        try:
            targets = await _resolve_targets(session)
            enqueue_uc = get_enqueue_scan_job_use_case(session)
            discovery = EnqueueOpportunityDailyScan(enqueue_uc)
            for target in targets:
                job = await discovery.execute(
                    list_id=str(target["listId"]),
                    account_id=target.get("accountId"),
                    propose_cap=int(target["proposeCap"]),
                )
                logger.info(
                    "Opportunity daily scan enqueued job=%s list=%s account=%s",
                    getattr(job, "id", None),
                    target["listId"],
                    target.get("accountId"),
                )
            await session.commit()
            _last_ran_day_key = day
            return day
        except Exception:
            await session.rollback()
            raise


async def opportunity_daily_scan_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = get_settings()
    interval = max(300, int(settings.opportunity_daily_scan_interval_seconds))
    logger.info(
        "Worker OPPORTUNITY_DAILY_SCAN iniciado — intervalo %ds · list=%s",
        interval,
        settings.opportunity_daily_universe_list_id,
    )
    while True:
        await asyncio.sleep(interval)
        try:
            await _run_opportunity_daily_once(session_factory)
        except Exception:
            logger.exception("Error en worker Opportunity daily scan")


def start_opportunity_daily_scan_worker(
    session_factory: async_sessionmaker[AsyncSession],
) -> asyncio.Task[None] | None:
    settings = get_settings()
    if not settings.opportunity_daily_scan_enabled:
        logger.info(
            "Worker OPPORTUNITY_DAILY_SCAN desactivado "
            "(OPPORTUNITY_DAILY_SCAN_ENABLED=false)"
        )
        return None
    return asyncio.create_task(opportunity_daily_scan_worker_loop(session_factory))
