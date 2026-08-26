"""RV-1 / VS-1 / PA-1 — runtime Paper|Live venue (memoria + Redis + preferencia cuenta).

Precedence: runtime_memory ?? redis_global ?? account.settings_json.brokerVenue
?? Settings.BROKER_VENUE ?? paper.

Override global (mesa / ``POST /api/risk/broker-venue``) gana sobre preferencia
por cuenta. Default siempre ``paper``. ≠ thaw ``PAPER_D_EXECUTE``.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

BrokerVenue = Literal["paper", "live"]

VENUE_REDIS_KEY = "bolsa:risk:broker_venue"

_runtime_broker_venue: str | None = None


def get_runtime_broker_venue() -> str | None:
    return _runtime_broker_venue


def set_runtime_broker_venue(venue: str | None) -> None:
    """None limpia el override runtime."""
    global _runtime_broker_venue
    if venue is None:
        _runtime_broker_venue = None
    else:
        _runtime_broker_venue = normalize_broker_venue(venue)


def normalize_broker_venue(raw: str | None) -> BrokerVenue:
    """Solo paper|live; cualquier otro valor → paper."""
    if raw is None:
        return "paper"
    v = str(raw).strip().lower()
    if v == "live":
        return "live"
    return "paper"


def account_broker_venue_from_settings(settings: dict[str, Any] | None) -> str | None:
    """Lee ``settings_json.brokerVenue`` si está presente y es string; else None (unset)."""
    if not isinstance(settings, dict):
        return None
    raw = settings.get("brokerVenue")
    if raw is None or not isinstance(raw, str):
        return None
    return raw


async def _redis_client() -> Any | None:
    from bolsa_infrastructure.config import get_settings

    url = (get_settings().redis_url or "").strip()
    if not url:
        return None
    from redis.asyncio import Redis

    return Redis.from_url(url, socket_connect_timeout=0.4, socket_timeout=0.4)


async def read_redis_broker_venue() -> BrokerVenue | None:
    """None = Redis no disponible / sin clave."""
    client = await _redis_client()
    if client is None:
        return None
    try:
        raw = await client.get(VENUE_REDIS_KEY)
        await client.aclose()
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return normalize_broker_venue(str(raw))
    except Exception:
        logger.debug("read redis broker venue failed", exc_info=True)
        try:
            await client.aclose()
        except Exception:
            pass
        return None


async def write_redis_broker_venue(venue: BrokerVenue) -> bool:
    client = await _redis_client()
    if client is None:
        return False
    try:
        await client.set(VENUE_REDIS_KEY, normalize_broker_venue(venue))
        await client.aclose()
        return True
    except Exception:
        logger.debug("write redis broker venue failed", exc_info=True)
        try:
            await client.aclose()
        except Exception:
            pass
        return False


async def set_broker_venue(venue: BrokerVenue) -> dict[str, Any]:
    """Fija override runtime (memoria + Redis si hay)."""
    chosen = normalize_broker_venue(venue)
    set_runtime_broker_venue(chosen)
    redis_ok = await write_redis_broker_venue(chosen)
    return {
        "venue": chosen,
        "memory": True,
        "redis": redis_ok,
    }


def effective_broker_venue(account_venue: str | None = None) -> BrokerVenue:
    """Sync: runtime memory ?? account preference ?? Settings.broker_venue; default paper.

    Sin Redis (usar ``effective_broker_venue_async`` en DI / API / Confirm/Fill).
    """
    runtime = get_runtime_broker_venue()
    if runtime is not None:
        return normalize_broker_venue(runtime)
    if account_venue is not None:
        return normalize_broker_venue(account_venue)
    from bolsa_infrastructure.config import get_settings

    return normalize_broker_venue(get_settings().broker_venue)


async def effective_broker_venue_async(account_venue: str | None = None) -> BrokerVenue:
    """Coalesce: runtime_memory ?? redis ?? account_venue ?? Settings.BROKER_VENUE ?? paper."""
    runtime = get_runtime_broker_venue()
    if runtime is not None:
        return normalize_broker_venue(runtime)
    redis_val = await read_redis_broker_venue()
    if redis_val is not None:
        return redis_val
    if account_venue is not None:
        return normalize_broker_venue(account_venue)
    from bolsa_infrastructure.config import get_settings

    return normalize_broker_venue(get_settings().broker_venue)


async def broker_venue_status() -> dict[str, BrokerVenue | None]:
    """Estado global para GET/POST ``/api/risk/broker-venue`` (RV-1; sin cuenta)."""
    from bolsa_infrastructure.config import get_settings

    runtime_raw = get_runtime_broker_venue()
    env = normalize_broker_venue(get_settings().broker_venue)
    redis_val = await read_redis_broker_venue()
    effective = await effective_broker_venue_async()
    runtime_mem: BrokerVenue | None = (
        normalize_broker_venue(runtime_raw) if runtime_raw is not None else None
    )
    return {
        "brokerVenue": effective,
        "env": env,
        "runtimeMemory": runtime_mem,
        "redis": redis_val,
    }
