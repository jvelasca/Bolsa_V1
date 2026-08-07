"""Heartbeat Redis del worker Arq (OR-Obs)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

WORKER_ARQ_HEARTBEAT_KEY = "bolsa:worker:arq:heartbeat"
WORKER_HEARTBEAT_TTL_SEC = 180


async def touch_arq_heartbeat() -> None:
    """SET heartbeat con TTL. Best-effort — no tumba el worker."""
    try:
        from bolsa_infrastructure.config import get_settings

        settings = get_settings()
        url = (settings.redis_url or "").strip()
        if not url:
            return
        from redis.asyncio import Redis

        client = Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        try:
            await client.set(
                WORKER_ARQ_HEARTBEAT_KEY,
                datetime.now(tz=UTC).isoformat(),
                ex=WORKER_HEARTBEAT_TTL_SEC,
            )
        finally:
            await client.aclose()
    except Exception:
        logger.debug("arq heartbeat touch failed", exc_info=True)


async def read_arq_heartbeat() -> str | None:
    """Lee ISO timestamp del último heartbeat, o None."""
    try:
        from bolsa_infrastructure.config import get_settings

        settings = get_settings()
        url = (settings.redis_url or "").strip()
        if not url:
            return None
        from redis.asyncio import Redis

        client = Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        try:
            raw = await client.get(WORKER_ARQ_HEARTBEAT_KEY)
        finally:
            await client.aclose()
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return str(raw)
    except Exception:
        return None
