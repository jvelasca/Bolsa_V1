"""Runtime kill switch + idempotencia AUTO (Redis best-effort + memoria proceso).

OR-P7 / A3: el flag env ``RISK_KILL_SWITCH`` sigue siendo fuente dura;
este módulo permite activar/desactivar sin reiniciar (UI / API).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_RUNTIME_KILL: bool = False
_IDEMPOTENCY_MEMORY: set[str] = set()

KILL_SWITCH_REDIS_KEY = "bolsa:risk:kill_switch"
IDEMPOTENCY_REDIS_PREFIX = "bolsa:auto-exec:idem:"
IDEMPOTENCY_TTL_SEC = 60 * 60 * 48  # 48h

CUSTODY_REDIS_PREFIX = "bolsa:custody:"
CUSTODY_TTL_SEC = 60 * 60 * 48  # 48h: ventana de bloqueo igual que auto-exec


def get_runtime_kill_switch_memory() -> bool:
    return _RUNTIME_KILL


def set_runtime_kill_switch_memory(enabled: bool) -> None:
    global _RUNTIME_KILL
    _RUNTIME_KILL = bool(enabled)


def clear_idempotency_memory_for_tests() -> None:
    _IDEMPOTENCY_MEMORY.clear()


async def _redis_client() -> Any | None:
    from bolsa_infrastructure.config import get_settings

    url = (get_settings().redis_url or "").strip()
    if not url:
        return None
    from redis.asyncio import Redis

    return Redis.from_url(url, socket_connect_timeout=0.4, socket_timeout=0.4)


async def read_redis_kill_switch() -> bool | None:
    """None = Redis no disponible / sin clave."""
    client = await _redis_client()
    if client is None:
        return None
    try:
        raw = await client.get(KILL_SWITCH_REDIS_KEY)
        await client.aclose()
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    except Exception:
        logger.debug("read redis kill switch failed", exc_info=True)
        try:
            await client.aclose()
        except Exception:
            pass
        return None


async def write_redis_kill_switch(enabled: bool) -> bool:
    client = await _redis_client()
    if client is None:
        return False
    try:
        await client.set(KILL_SWITCH_REDIS_KEY, "1" if enabled else "0")
        await client.aclose()
        return True
    except Exception:
        logger.debug("write redis kill switch failed", exc_info=True)
        try:
            await client.aclose()
        except Exception:
            pass
        return False


async def set_kill_switch(enabled: bool) -> dict[str, Any]:
    """Activa/desactiva kill switch runtime (memoria + Redis si hay)."""
    set_runtime_kill_switch_memory(enabled)
    redis_ok = await write_redis_kill_switch(enabled)
    return {
        "enabled": enabled,
        "memory": True,
        "redis": redis_ok,
    }


async def effective_kill_switch() -> bool:
    """OR de env Settings + memoria proceso + Redis."""
    from bolsa_infrastructure.config import get_settings

    if bool(get_settings().risk_kill_switch):
        return True
    if get_runtime_kill_switch_memory():
        return True
    redis_val = await read_redis_kill_switch()
    return bool(redis_val)


async def kill_switch_status() -> dict[str, Any]:
    from bolsa_infrastructure.config import get_settings

    env_on = bool(get_settings().risk_kill_switch)
    mem_on = get_runtime_kill_switch_memory()
    redis_on = await read_redis_kill_switch()
    effective = env_on or mem_on or bool(redis_on)
    return {
        "effective": effective,
        "env": env_on,
        "runtimeMemory": mem_on,
        "redis": redis_on,
    }


async def claim_auto_execute_idempotency(key: str) -> bool:
    """True si la clave es nueva (claim OK). False si ya existía (skip)."""
    if key in _IDEMPOTENCY_MEMORY:
        return False
    client = await _redis_client()
    if client is not None:
        try:
            # SET NX + TTL
            ok = await client.set(
                f"{IDEMPOTENCY_REDIS_PREFIX}{key}",
                "1",
                nx=True,
                ex=IDEMPOTENCY_TTL_SEC,
            )
            await client.aclose()
            if ok:
                _IDEMPOTENCY_MEMORY.add(key)
                return True
            return False
        except Exception:
            logger.debug("idempotency redis claim failed", exc_info=True)
            try:
                await client.aclose()
            except Exception:
                pass
    _IDEMPOTENCY_MEMORY.add(key)
    return True


async def release_auto_execute_idempotency(key: str) -> None:
    """Libera un claim AUTO no confirmado (p. ej. fill fallido) para permitir reintento.

    Best-effort: borra memoria del proceso y Redis si hay. Un retry con la misma clave
    volverá a pasar ``claim_auto_execute_idempotency``.
    """
    _IDEMPOTENCY_MEMORY.discard(key)
    client = await _redis_client()
    if client is None:
        return
    try:
        await client.delete(f"{IDEMPOTENCY_REDIS_PREFIX}{key}")
        await client.aclose()
    except Exception:
        logger.debug("idempotency redis release failed", exc_info=True)
        try:
            await client.aclose()
        except Exception:
            pass


_CUSTODY_MEMORY: set[str] = set()


def clear_custody_memory_for_tests() -> None:
    _CUSTODY_MEMORY.clear()


def make_custody_idempotency_key(account_id: str, period: str) -> str:
    """Clave estable por cuenta y periodo (año) para el cargo de custodia."""
    return f"custody|{account_id}|{period}"


async def claim_custody_charge(account_id: str, period: str) -> bool:
    """True si el cargo de custodia (cuenta, periodo) no se ha aplicado aún.

    Guard SET NX sobre ``bolsa:custody:*`` — único medio atomico entre workers/requests
    para impedir el doble cargo de custodia en lecturas concurrentes (GET summary/tax).
    """
    key = make_custody_idempotency_key(account_id, period)
    if key in _CUSTODY_MEMORY:
        return False
    client = await _redis_client()
    if client is not None:
        try:
            ok = await client.set(
                f"{CUSTODY_REDIS_PREFIX}{key}",
                "1",
                nx=True,
                ex=CUSTODY_TTL_SEC,
            )
            await client.aclose()
            if ok:
                _CUSTODY_MEMORY.add(key)
                return True
            return False
        except Exception:
            logger.debug("custody redis claim failed", exc_info=True)
            try:
                await client.aclose()
            except Exception:
                pass
    _CUSTODY_MEMORY.add(key)
    return True


async def release_custody_charge(account_id: str, period: str) -> None:
    """Libera un claim de custodia cuando NO se aplicó cargo (salida temprana)."""
    key = make_custody_idempotency_key(account_id, period)
    _CUSTODY_MEMORY.discard(key)
    client = await _redis_client()
    if client is None:
        return
    try:
        await client.delete(f"{CUSTODY_REDIS_PREFIX}{key}")
        await client.aclose()
    except Exception:
        logger.debug("custody redis release failed", exc_info=True)
        try:
            await client.aclose()
        except Exception:
            pass
