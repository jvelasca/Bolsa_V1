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
from collections.abc import Mapping, Sequence
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
from bolsa_infrastructure.database.repositories.scan_job_repository import (
    ScanJobRecord,
    SqlAlchemyScanJobRepository,
)

logger = logging.getLogger(__name__)

#: Motivo de journal/log cuando el tick de hoy ya estaba encolado (T-2, dedupe durable).
SCAN_DAILY_ALREADY_ENQUEUED = "scan_daily_already_enqueued"

#: D-3 (auditoría 2) — estados que SÍ representan «ya encolado hoy» para el dedupe durable.
#: Un job ``failed`` NO ejecutó el descubrimiento: contarlo como encolado dejaba el día
#: entero sin scan y sin aviso hasta el siguiente día UTC. La lista es de INCLUSIÓN (no de
#: exclusión) para que un estado terminal futuro (p. ej. ``cancelled``) tampoco lo bloquee.
SCAN_DAILY_DEDUPE_STATUSES: tuple[str, ...] = ("pending", "processing", "completed")

#: D-3 — motivo declarado cuando el discovery del día FALLÓ: el silencio era el defecto.
SCAN_DAILY_FAILED_TODAY = "scan_daily_failed_today"

_last_ran_day_key: str | None = None


def _utc_day_key() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _discovery_key(payload: Mapping[str, Any]) -> tuple[str, str | None]:
    """Par ``(listId, accountId)`` de un payload de discovery (normalizado).

    Es la clave del dedupe durable: el MISMO universo para la MISMA cuenta no se encola
    dos veces el mismo día. Puro y sin I/O, para poder testearlo sin PostgreSQL.
    """
    universe = payload.get("universe")
    raw_list = payload.get("listId") or (
        universe.get("listId") if isinstance(universe, Mapping) else None
    )
    account = payload.get("opportunityAccountId")
    return (
        clamp_daily_ops_list_id(
            str(raw_list or DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID)
        ),
        str(account) if account else None,
    )


def _dedupe_keys(payloads: Sequence[Mapping[str, Any]]) -> set[tuple[str, str | None]]:
    """Pares ``(listId, accountId)`` ya encolados hoy (puro, sin I/O)."""
    return {_discovery_key(payload) for payload in payloads}


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

    D-3 (auditoría 2): solo cuentan los estados de ``SCAN_DAILY_DEDUPE_STATUSES``. Antes el
    dedupe no filtraba por estado, así que un job que terminó ``failed`` contaba como «ya
    encolado hoy» y el día quedaba sin descubrimiento hasta el siguiente día UTC.
    """
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    payloads = await SqlAlchemyScanJobRepository(session).list_payloads_since(
        since=day_start,
        payload_key=OPPORTUNITY_DISCOVERY_PAYLOAD_KEY,
        statuses=SCAN_DAILY_DEDUPE_STATUSES,
    )
    return _dedupe_keys(payloads)


async def _failed_discoveries_today(session: AsyncSession) -> list[ScanJobRecord]:
    """D-3 — discovery del día que FALLARON (se declaran; ya no bloquean el reintento)."""
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return await SqlAlchemyScanJobRepository(session).list_since(
        since=day_start,
        payload_key=OPPORTUNITY_DISCOVERY_PAYLOAD_KEY,
        statuses=("failed",),
    )


async def _run_opportunity_daily_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> str | None:
    """Un intento de discovery del día (idempotente y con REINTENTO de fallidos).

    Capas de protección del día (de más barata a más durable):

    1. ``_last_ran_day_key`` — guard en MEMORIA: muere con el proceso.
    2. Dedupe DURABLE en ``scan_jobs`` — el MISMO ``(listId, cuenta)`` no se encola dos
       veces el día UTC, aunque el proceso reinicie (T-2).

    D-3 (auditoría 2): un discovery ``failed`` no ejecutó nada, así que NO cuenta como
    «ya encolado» (``SCAN_DAILY_DEDUPE_STATUSES``) y el día se reintenta. El reintento
    ocurre también DENTRO del mismo proceso: el guard en memoria solo corta cuando no hay
    ningún fallido pendiente de reintento. La condición de «pendiente» es que su
    ``(listId, cuenta)`` no esté ya cubierto por un job vivo o completado — así el aviso
    ``scan_daily_failed_today`` solo se emite cuando ese hueco sigue sin cubrir (el caso en
    que de verdad procede reintentar) y los reintentos quedan serializados uno a uno por el
    dedupe durable (no uno por tick).

    CONCURRENCIA (límite DECLARADO): ``scan_jobs`` no tiene una clave única de discovery,
    así que esta función asume UN scheduler por despliegue. Dos schedulers concurrentes
    pueden ver el dedupe vacío a la vez y encolar dos scans del mismo día; si el despliegue
    deja de garantizar un único proceso, hace falta un claim atómico (o una clave única
    por día/universo/cuenta) antes de confiar en este dedupe.
    """
    global _last_ran_day_key
    day = _utc_day_key()

    async with session_factory() as session:
        try:
            targets = await _resolve_targets(session)
            already = await _targets_already_enqueued_today(session)
            # D-3 — un fallido SOLO es reintentable si su hueco no está ya cubierto por un
            # job vivo o completado: si lo está, no hay nada que reintentar (y decirlo
            # sería mentir en cada reinicio).
            retryable = [
                failed
                for failed in await _failed_discoveries_today(session)
                if _discovery_key(failed.payload) not in already
            ]
            if _last_ran_day_key == day and not retryable:
                return None
            for failed in retryable:
                failed_list, failed_account = _discovery_key(failed.payload)
                logger.warning(
                    "Opportunity daily scan FALLÓ hoy y se REINTENTA — reason=%s job=%s "
                    "list=%s account=%s",
                    SCAN_DAILY_FAILED_TODAY,
                    failed.id,
                    failed_list,
                    failed_account,
                )
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
