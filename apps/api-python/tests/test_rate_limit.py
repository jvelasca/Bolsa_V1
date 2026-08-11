"""Rate limit middleware: prefijos deterministas + store en memoria (P1.8)."""

from __future__ import annotations

import pytest

from bolsa_api.middleware.rate_limit import MemoryStore, RateLimitMiddleware


def _middleware() -> RateLimitMiddleware:
    return RateLimitMiddleware(None, enabled=True, redis_url="")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        # Prefijos específicos: AI fundamentals más restrictivo que el resto de /api/ai/
        ("/api/ai/fundamentals/explain", 30),
        ("/api/ai/fundamentals/filings/summarize", 30),
        ("/api/ai/fundamentals/filings/ask", 30),
        ("/api/ai/status", 40),
        ("/api/ai/effectiveness", 40),
        # Instruments fundamentals (ruta con {id} → segmento)
        ("/api/instruments/341/fundamentals", 60),
        ("/api/instruments/fundamentals/query", 60),
        ("/api/instruments/fundamentals/screener", 60),
        # Sync
        ("/api/sync", 20),
        # Fuera de scope: no debe acotarse
        ("/api/portfolio/positions", None),
        ("/api/accounts", None),
        ("/api/health", None),
        # Sin subcadena frágil: "fund-backtest" no se acota
        ("/api/instruments/341/fund-backtest", None),
    ],
)
def test_limit_for_is_deterministic(path: str, expected: int | None) -> None:
    assert _middleware()._limit_for(path) == expected


@pytest.mark.asyncio
async def test_memory_store_blocks_after_limit() -> None:
    store = MemoryStore()
    key = "test:routed"
    # Debajo del límite → permitido (False = no supera). Con limit=5 se permiten 5.
    for _ in range(5):
        assert await store.check_and_tick(key, 5) is False
    # A partir del 6º → rechazado (True = supera)
    assert await store.check_and_tick(key, 5) is True
    # Clave distinta mantiene su contador independiente
    assert await store.check_and_tick("test:other", 5) is False
