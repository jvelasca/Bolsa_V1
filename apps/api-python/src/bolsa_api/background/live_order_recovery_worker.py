"""V2.12 — LiveOrderRecoveryWorker (XL-3 UNKNOWN → query_broker, NO re-POST).

On-by-default (env ``LIVE_RECOVERY_WORKER_ENABLED``) en ``scheduler_worker``, no
en la lifespan de FastAPI (evita duplicación bajo ``uvicorn --workers N``). Cada
tick lee filas duraderas ``live_orders`` en estado ``UNKNOWN`` y las resuelve con
el puerto ``LiveOrderQueryPort`` (``query_broker``). Resolver **nunca** re-POSTea:
UNKNOWN solo sale vía query del broker o queda UNKNOWN si el venue no contesta.

Fail-closed:
* Sin cliente de query cableado para la cuenta/venue → tratar como
  ``unavailable``: la fila queda UNKNOWN y se refresca ``updated_at`` (para no
  hilar fino) + se anota el intento. Nada se cierra en falso.
* Un outcome ``unavailable`` del cliente real → igualmente UNKNOWN (sin estado
  terminal fabricado).
* Los outcomes ``partial``/``filled``/``working``/``rejected``/``cancelled`` que
  iluminan una transición legal desde UNKNOWN se persisten como estado de la
  máquina. **NO** se sintetiza ``execute_trade``/ledger aquí (veto XL-3; el
  slice XL-2 síncrono sigue vivo y el apply financiero sigue PARKED).

≠ thaw · ≠ PAPER_D_EXECUTE · ≠ autoriza re-POST.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from bolsa_application.live_order_query import LiveOrderQueryPort
from bolsa_application.live_order_store import PostgresLiveOrderStore
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

TICK_SECONDS = 5
_ENV_ENABLED = "LIVE_RECOVERY_WORKER_ENABLED"
_DEFAULT_BATCH = 50

# Provider shape: (venue, account_id, venue_order_id) → query port | None.
QueryProvider = Callable[
    [str, str, str],
    Awaitable[LiveOrderQueryPort | None],
]


def _worker_enabled() -> bool:
    raw = (os.getenv(_ENV_ENABLED) or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


async def _no_query_provider(
    venue: str,
    account_id: str,
    venue_order_id: str,
) -> LiveOrderQueryPort | None:
    """Sin cliente real de query cableado → unavailable (fail-closed).

    El contrato XTB ``GET /orders/{venueOrderId}`` no existe todavía (audit
    Hallazgo 3), así que el poller de verdad no fabrica cierre: devuelve None y
    la fila permanece UNKNOWN.
    """
    _ = venue, account_id, venue_order_id
    return None


async def resolve_one_unknown(
    order: Any,
    query: LiveOrderQueryPort | None,
    *,
    store: Any,
    account_id: str,
) -> str:
    """Resuelve una fila UNKNOWN → devuelve 'resolved'|'unavailable'|'error'.

    Fail-closed:
    * sin cliente de query o sin venue_order_id → sigue UNKNOWN (updated_at bump).
    * outcome no mapeable / intraducible desde UNKNOWN → sigue UNKNOWN.
    * outcome legal → persiste la transición. NUNCA sintetiza execute_trade.
    """
    from bolsa_analytics.cognitive.live_order import (
        can_transition_live_order,
        transition_live_order,
    )

    if query is None or not order.venue_order_id:
        return await _refresh_unknown(store, order, account_id=account_id)
    result = await query.query_broker_order(venue_order_id=order.venue_order_id)
    target = result.to_live_status()
    if target is None or not can_transition_live_order(order.status, target):
        return await _refresh_unknown(store, order, account_id=account_id)
    filled_qty = order.filled_quantity
    if target in {"PARTIAL", "FILLED"} and result.filled_quantity is not None:
        filled_qty = float(result.filled_quantity)
    advanced = transition_live_order(
        order,
        target,
        filled_quantity=filled_qty,
    )
    await store.put(advanced, account_id=account_id)
    logger.info(
        "live_order %s UNKNOWN→%s (resolved vía query, no re-POST)",
        order.order_id,
        target,
    )
    return "resolved"


async def _refresh_unknown(store: Any, order: Any, *, account_id: str) -> str:
    """Queda UNKNOWN; refresca updated_at para no hilar el ciclo de poll."""
    await store.put(order, account_id=account_id)
    return "unavailable"


async def _drain_unknowns(
    store: Any,
    *,
    query_provider: QueryProvider | None,
    limit: int,
) -> dict[str, Any]:
    """Drena filas UNKNOWN del store dado (testable sin PG)."""
    provider = query_provider or _no_query_provider
    rows = await store.list_unknown(limit=limit)
    resolved: int = 0
    unavailable: int = 0
    errors: int = 0
    for order in rows:
        try:
            query = await provider(order.venue, order.account_id, order.venue_order_id)
            status = await resolve_one_unknown(
                order,
                query,
                store=store,
                account_id=order.account_id or "",
            )
            if status == "resolved":
                resolved += 1
            else:
                unavailable += 1
        except Exception:  # noqa: BLE001 — una fila no tumba el tick
            errors += 1
            logger.exception("live_order recovery failed order_id=%s", order.order_id)

    return {
        "drained": len(rows),
        "resolved": resolved,
        "unavailable": unavailable,
        "errors": errors,
    }


async def _drain_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    query_provider: QueryProvider | None = None,
    limit: int = _DEFAULT_BATCH,
) -> dict[str, Any]:
    async with session_factory() as session:
        store = PostgresLiveOrderStore(session)
        # Re-put va por otra sesión por fila para límites de bloqueo cortos.
        result = await _drain_unknowns(
            store,
            query_provider=query_provider,
            limit=limit,
        )
    return result


async def live_order_recovery_worker_loop(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float = TICK_SECONDS,
    query_provider: QueryProvider | None = None,
    limit: int = _DEFAULT_BATCH,
) -> None:
    logger.info("LiveOrderRecoveryWorker iniciado (tick=%ss)", tick_seconds)
    while True:
        await asyncio.sleep(tick_seconds)
        if not _worker_enabled():
            continue
        try:
            drain = await _drain_once(
                session_factory,
                query_provider=query_provider,
                limit=limit,
            )
            if drain["drained"]:
                logger.info("live_order recovery drain: %s", drain)
        except Exception:  # noqa: BLE001
            logger.exception("live_order recovery tick failed")


def start_live_order_recovery_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    tick_seconds: float = TICK_SECONDS,
    query_provider: QueryProvider | None = None,
    limit: int = _DEFAULT_BATCH,
) -> asyncio.Task[None] | None:
    if not _worker_enabled():
        logger.info(
            "LiveOrderRecoveryWorker desactivado (%s=false)",
            _ENV_ENABLED,
        )
        return None
    return asyncio.create_task(
        live_order_recovery_worker_loop(
            session_factory,
            tick_seconds=tick_seconds,
            query_provider=query_provider,
            limit=limit,
        )
    )
