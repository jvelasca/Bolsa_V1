"""Worker de actualización automática de OHLCV con cola y rate limiting.

El worker respeta la configuración de proveedores (migración ``059``):

* con el proveedor ``ohlcv`` deshabilitado o sin configuración mínima **no** escanea ni
  procesa la cola; el motivo se declara una vez por transición (no en cada tick);
* el throttle del cliente Yahoo se aplica desde ``min_interval_seconds`` en cada tick,
  de modo que un cambio en Configuración surte efecto sin reiniciar el proceso.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_api.api.dependencies import (
    get_enqueue_stale_use_case,
    get_market_provider_config_resolver,
    get_process_sync_queue_use_case,
    get_sync_scheduler_repository,
)
from bolsa_application.sync_scheduler import is_post_market_window
from bolsa_domain.entities.market_provider import (
    CAPABILITY_OHLCV,
    PROVIDER_YAHOO,
    MarketProviderConfig,
)

logger = logging.getLogger(__name__)

TICK_SECONDS = 15
_last_scan_at: datetime | None = None
#: Último estado declarado del proveedor (para no repetir el aviso en cada tick).
_last_provider_note: str | None = None


async def _ohlcv_provider(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[MarketProviderConfig | None, str | None]:
    async with session_factory() as session:
        resolution = await get_market_provider_config_resolver(session).resolve_capability(
            CAPABILITY_OHLCV
        )
    return resolution.provider, resolution.reason


def _apply_yahoo_throttle(configs: list[MarketProviderConfig]) -> None:
    yahoo = next((cfg for cfg in configs if cfg.id == PROVIDER_YAHOO), None)
    if yahoo is None:
        return
    from bolsa_market.yahoo_client import get_yahoo_finance_client

    get_yahoo_finance_client().min_interval_sec = float(yahoo.min_interval_seconds)


async def _refresh_provider_settings(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[bool, str | None]:
    """Devuelve ``(usable, reason)`` y aplica el throttle del proveedor ``ohlcv``."""
    async with session_factory() as session:
        configs = await get_market_provider_config_resolver(session).list_configs()
    _apply_yahoo_throttle(configs)
    usable = [cfg for cfg in configs if cfg.usable and cfg.supports(CAPABILITY_OHLCV)]
    if usable:
        return True, None
    declared = [cfg.id for cfg in configs if cfg.supports(CAPABILITY_OHLCV)]
    return False, f"provider_disabled:{declared[0]}" if declared else "no_provider_declared"


def _note_provider_state(reason: str | None) -> None:
    """Declara el cambio de estado del proveedor una sola vez."""
    global _last_provider_note
    if reason == _last_provider_note:
        return
    if reason is None:
        if _last_provider_note is not None:
            logger.info("Auto-sync: proveedor OHLCV de nuevo disponible")
    else:
        logger.warning(
            "Auto-sync detenido por configuración: %s (deshabilita o corrige el "
            "proveedor en Configuración → Sync / proveedores)",
            reason,
        )
    _last_provider_note = reason


async def _run_scan(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        try:
            result = await get_enqueue_stale_use_case(session).execute()
            await session.commit()
            if result.skipped_reason:
                _note_provider_state(result.skipped_reason)
                return 0
            if result.enqueued:
                logger.info(
                    "Auto-sync: %s instrumentos encolados (escaneados %s)",
                    result.enqueued,
                    result.scanned,
                )
            return result.enqueued
        except Exception:
            await session.rollback()
            raise


async def _run_queue_item(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    async with session_factory() as session:
        try:
            repo = get_sync_scheduler_repository(session)
            settings = await repo.get_settings()
            if not settings.auto_sync_enabled:
                return False
            result = await get_process_sync_queue_use_case(session).execute()
            await session.commit()
            if result.skipped_reason:
                _note_provider_state(result.skipped_reason)
                return False
            if result.processed and result.instrument_id:
                # Los fallos ya quedan registrados en DB (queue.last_error +
                # data_sync_logs). Para un símbolo permanentemente no-resoluble
                # (p. ej. 404) el WARNING por cada intento es ruido: se usa INFO
                # y el detalle del error se conserva en el mensaje.
                logger.log(
                    logging.INFO,
                    "Auto-sync cola: %s → %s%s",
                    result.instrument_id,
                    result.status,
                    f" ({result.error})" if result.error else "",
                )
            return result.processed
        except Exception:
            await session.rollback()
            raise


async def auto_sync_worker_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    global _last_scan_at

    logger.info("Worker auto-sync OHLCV iniciado")
    while True:
        await asyncio.sleep(TICK_SECONDS)
        try:
            usable, reason = await _refresh_provider_settings(session_factory)
            _note_provider_state(reason)
            if not usable:
                continue

            async with session_factory() as session:
                settings = await get_sync_scheduler_repository(session).get_settings()
            if not settings.auto_sync_enabled:
                continue
            if settings.post_market_only and not is_post_market_window():
                continue

            now = datetime.now(UTC)
            scan_due = (
                _last_scan_at is None
                or (now - _last_scan_at).total_seconds() >= settings.scan_interval_minutes * 60
            )
            if scan_due:
                await _run_scan(session_factory)
                _last_scan_at = now

            processed = await _run_queue_item(session_factory)
            if processed:
                async with session_factory() as session:
                    settings = await get_sync_scheduler_repository(session).get_settings()
                    delay = settings.min_delay_seconds
                await asyncio.sleep(delay)
        except Exception:
            logger.exception("Error en worker auto-sync")


def start_auto_sync_worker(session_factory: async_sessionmaker[AsyncSession]) -> asyncio.Task[None]:
    return asyncio.create_task(auto_sync_worker_loop(session_factory))
