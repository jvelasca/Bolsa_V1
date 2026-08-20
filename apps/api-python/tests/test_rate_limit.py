"""Rate limit middleware: prefijos deterministas + store en memoria (P1.8)."""

from __future__ import annotations

import pytest
from starlette.requests import Request

from bolsa_api.middleware.rate_limit import (
    MemoryStore,
    RateLimitMiddleware,
    get_client_ip,
)


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
        # Auth (R-8B.1): login y status tienen límites propios
        ("/api/auth/login", 20),
        ("/api/auth/status", 60),
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


def _request(host: str = "198.51.100.7", xff: str | None = None) -> Request:
    headers = {"X-Forwarded-For": xff} if xff else {}
    # Starlette 1.6 no normaliza las claves en `Headers`: deben ir ya en minúsculas.
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/ai/status",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (host, 12345),
            "server": ("127.0.0.1", 8000),
            "scheme": "http",
            "query_string": b"",
        }
    )


def test_get_client_ip_ignores_xff_without_trusted_proxy() -> None:
    """Sin trusted proxy (dev/local), `X-Forwarded-For` NO se confía (anti-spoofing)."""
    # Peer real 198.51.100.7 intenta suplantar a otro cliente vía XFF.
    req = _request(host="198.51.100.7", xff="172.16.0.99, 172.16.0.1")
    assert get_client_ip(req, trusted_proxies="") == "198.51.100.7"
    # Tampoco si TRUSTED_PROXIES está configurado pero el peer no está listado.
    assert get_client_ip(req, trusted_proxies="203.0.113.1") == "198.51.100.7"


def test_get_client_ip_uses_first_xff_when_peer_is_trusted() -> None:
    """Proxy de confianza → se usa la PRIMERA IP de X-Forwarded-For (cliente original)."""
    req = _request(host="203.0.113.1", xff="70.41.3.18, 203.0.113.1")
    assert get_client_ip(req, trusted_proxies="203.0.113.1") == "70.41.3.18"


def test_get_client_ip_trusted_proxies_accepts_comma_separated_list() -> None:
    """TRUSTED_PROXIES se normaliza coma-separado; varios proxies son soportados."""
    req = _request(host="10.0.0.5", xff="198.51.100.20, 10.0.0.1, 10.0.0.5")
    trusted = "203.0.113.1,10.0.0.5"
    assert get_client_ip(req, trusted_proxies=trusted) == "198.51.100.20"


def test_get_client_ip_trusted_peer_without_xff_falls_back_to_client_host() -> None:
    """Peer de confianza sin header → cae a client.host (acceso directo)."""
    req = _request(host="203.0.113.1", xff=None)
    assert get_client_ip(req, trusted_proxies="203.0.113.1") == "203.0.113.1"


def test_get_client_ip_trims_whitespace_in_xff() -> None:
    """El primer elemento de XFF puede llevar espacios tras la coma inicial."""
    req = _request(host="203.0.113.1", xff=" 70.41.3.18 , 203.0.113.1")
    assert get_client_ip(req, trusted_proxies="203.0.113.1") == "70.41.3.18"

