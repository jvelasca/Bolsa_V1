"""Worker — Opportunity daily scan opt-in (V1.19).

Off-by-default: ``OPPORTUNITY_DAILY_SCAN_ENABLED=false``.
Encola scan contra universo **Estudio** (ADR-041 / V1.22 H1).
``OPPORTUNITY_DAILY_UNIVERSE_LIST_ID`` distinto de estudio se ignora.
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
    OPPORTUNITY_DISCOVERY_PAYLOAD_KEY,
    EnqueueOpportunityDailyScan,
    account_wants_daily_scan,
    clamp_daily_ops_list_id,
    resolve_universe_list_id,
)
from bolsa_infrastructure.config import get_settings

logger = logging.getLogger(__name__)

#: Motivo de journal/log cuando el tick de hoy ya estaba encolado (T-2, dedupe durable).
SCAN_DAILY_ALREADY_ENQUEUED = "scan_daily_already_enqueued"

_last_ran_day_key: str | None = None


def _utc_day_key() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


async def _resolve_targets(session: AsyncSession) -> list[dict[str, Any]]:
    """Cuentas a enriquecer con propose; scan siempre se encola al menos una vez."""
    settings = get_settings()
    env_account = (settings.opportunity_daily_account_id or "").strip() or None
    raw_list = (settings.opportunity_daily_universe_list_id or "").strip()
    list_id = clamp_daily_ops_list_id(raw_list or DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID)
    if raw_list and raw_list != list_id:
        logger.warning(
            "OPPORTUNITY_DAILY_UNIVERSE_LIST_ID=%s ignored; Daily Ops universe is %s",
            raw_list,
            list_id,
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


async def _targets_already_enqueued_today(session: AsyncSession) -> set[tuple[str, str | None]]:
    """Pares ``(listId, accountId)`` de discovery ya encolados hoy (dedupe durable).

    T-2 hace el primer tick **inmediato**, así que un reinicio no puede re-encolar el mismo
    universo el mismo día: el guard en memoria (``_last_ran_day_key``) muere con el proceso,
    la fila de ``scan_jobs`` no.
    """
    from bolsa_infrastructure.database.repositories.scan_job_repository import (
        SqlAlchemyScanJobRepository,
    )

    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    payloads = await SqlAlchemyScanJobRepository(session).list_payloads_since(
        since=day_start,
        payload_key=OPPORTUNITY_DISCOVERY_PAYLOAD_KEY,
    )
    done: set[tuple[str, str | None]] = set()
    for payload in payloads:
        universe = payload.get("universe")
        raw_list = payload.get("listId") or (
            universe.get("listId") if isinstance(universe, dict) else None
        )
        account = payload.get("opportunityAccountId")
        done.add(
            (
                clamp_daily_ops_list_id(str(raw_list or DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID)),
                str(account) if account else None,
            )
        )
    return done


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
            already = await _targets_already_enqueued_today(session)
            enqueue_uc = get_enqueue_scan_job_use_case(session)
            discovery = EnqueueOpportunityDailyScan(enqueue_uc)
            for target in targets:
                key = (str(target["listId"]), target.get("accountId"))
                if key in already:
                    logger.info(
                        "Opportunity daily scan ya encolado hoy — reason=%s list=%s account=%s",
                        SCAN_DAILY_ALREADY_ENQUEUED,
                        target["listId"],
                        target.get("accountId"),
                    )
                    continue
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
        "Worker OPPORTUNITY_DAILY_SCAN iniciado — intervalo %ds · list=%s · primer tick "
        "inmediato",
        interval,
        clamp_daily_ops_list_id(settings.opportunity_daily_universe_list_id),
    )
    # T-2: el primer intento es YA. Dormir el intervalo antes del primer trabajo dejaba al
    # proceso recién arrancado sin escanear hasta el día siguiente (24 h por defecto), que es
    # lo que el operador lee como «el scan no corre».
    while True:
        try:
            await _run_opportunity_daily_once(session_factory)
        except Exception:
            logger.exception("Error en worker Opportunity daily scan")
        await asyncio.sleep(interval)


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
