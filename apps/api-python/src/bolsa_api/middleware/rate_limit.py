"""Rate limit para rutas sensibles (P1.8).

Comportamiento:
- **Distribuido entre workers** cuando ``REDIS_URL`` está configurada: se usa un
  contador de ventana fija en Redis (``INCR`` + ``EXPIRE``), compartido entre todos
  los procesos uvicorn. Sin Redis se degrada a un contador **en memoria por proceso**
  (fallback), documentado como límite no compartido.
- **Prefijos deterministas y ordenados**: las rutas más específicas se declaran antes
  que las genéricas (se gana por primera coincidencia). Sin coincidencias textuales
  frágiles sobre subcadenas arbitrarias.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Protocol

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Prefijos (path) sensibles → máx. requests por ventana. Orden: de más específico a más
# genérico, porque _limit_for devuelve la primera coincidencia por startswith.
SENSITIVE_PREFIXES: tuple[tuple[str, int], ...] = (
    # AI fundamentals (explain / filings) es más restrictivo que el resto de /api/ai/
    ("/api/ai/fundamentals", 30),
    ("/api/ai/", 40),
    ("/api/instruments/fundamentals/query", 60),
    ("/api/instruments/fundamentals/screener", 60),
    ("/api/sync", 20),
    # Auth (R-8B.1): login es objetivo de fuerza bruta → límite bajo; status es una
    # lectura barata del FE (AuthGate) → más permisivo.
    ("/api/auth/login", 20),
    ("/api/auth/status", 60),
)

# Extra: /api/instruments/{id}/fundamentals (id en el path). Se resuelve por segmento,
# no por subcadena, para no acotar rutas no relacionadas.
_FUNDAMENTALS_SEGMENT = "fundamentals"

WINDOW_SECONDS = 60.0

# F-SEG-3: separador aritmético aceptado por Starlette/Uvicorn para la cabecera
# `X-Forwarded-For` (p. ej. `203.0.113.1, 70.41.3.18`).
_FORWARDED_SEPARATOR = ","


class RateLimitStore(Protocol):
    """Almacén de contadores por clave y ventana."""

    async def check_and_tick(self, key: str, limit: int) -> bool:
        """Devuelve True si la request supera el límite (debe rechazarse con 429)."""
        ...

    async def _reset(self) -> None:  # para tests / idle
        ...


class MemoryStore:
    """Ventana deslizante en memoria por proceso (fallback sin Redis)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def check_and_tick(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False

    async def _reset(self) -> None:  # pragma: no cover - solo tests
        self._hits.clear()


class RedisStore:
    """Contador de ventana fija en Redis (distribuido entre workers) — P1.8.

    Se usa ``INCR`` + ``PEXPIRE`` por clave ``key:window``. Cada llamada incrementa y
    devuelve el conteo; si supera ``limit`` se rechaza. El TTL asegura que la ventana se
    auto-expira sin limpieza externa.

    Si Redis no está disponible se degrada a un contador en memoria (fallback), de modo
    que en local (sin Redis, aunque ``REDIS_URL`` tenga un valor por defecto) se siguen
    aplicando límites. Un mini circuit-breaker evita sonclear Redis caído en cada
    request: tras una falla, se reintenta a lo sumo una vez cada ``RETRY_AFTER_SEC``.
    """

    _LUA_INCREMENT = """
    local c = redis.call('INCR', KEYS[1])
    if c == 1 then
        redis.call('PEXPIRE', KEYS[1], ARGV[1])
    end
    return c
    """
    RETRY_AFTER_SEC = 15.0

    def __init__(self, client: object, *, prefix: str = "rl") -> None:
        self._client = client  # redis.asyncio.Redis
        self._prefix = prefix
        self._memory = MemoryStore()
        self._redis_down_since: float | None = None
    @classmethod
    def _bucketed_key(cls, prefix: str, key: str) -> str:
        window = int(time.time() // WINDOW_SECONDS)
        return f"{prefix}:{window}:{key}"

    def _should_probe_redis(self) -> bool:
        if self._redis_down_since is None:
            return True
        since = self._redis_down_since
        return since is not None and (time.monotonic() - since) >= self.RETRY_AFTER_SEC

    async def check_and_tick(self, key: str, limit: int) -> bool:
        if self._redis_down_since is not None and not self._should_probe_redis():
            return await self._memory.check_and_tick(key, limit)

        full = self._bucketed_key(self._prefix, key)
        try:
            count = await self._client.eval(  # type: ignore[attr-defined]
                self._LUA_INCREMENT, 1, full, int(WINDOW_SECONDS * 1000)
            )
        except Exception:  # noqa: BLE001 — Redis cae → probar de nuevo en RETRY_AFTER
            self._redis_down_since = time.monotonic()
            return await self._memory.check_and_tick(key, limit)
        self._redis_down_since = None
        return int(count) > limit

    async def _reset(self) -> None:  # pragma: no cover - solo tests
        self._redis_down_since = None
        await self._memory._reset()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        enabled: bool = True,
        redis_url: str | None = None,
        trusted_proxies: str = "",
    ) -> None:
        super().__init__(app)
        self._enabled = enabled
        self._trusted_proxies = trusted_proxies
        self._store: RateLimitStore
        redis = redis_url or ""
        if redis.strip():
            # Con REDIS_URL configurado (default presente) se usa RedisStore, que
            # degrada a memoria si Redis no responde.
            self._store = RedisStore(_new_redis_client(redis))
        else:
            self._store = MemoryStore()

    def _limit_for(self, path: str) -> int | None:
        for prefix, limit in SENSITIVE_PREFIXES:
            if path.startswith(prefix):
                return limit
        # /api/instruments/{id}/fundamentals → segmento `fundamentals`
        if _path_has_segment(path, _FUNDAMENTALS_SEGMENT) and path.startswith(
            "/api/instruments/"
        ):
            return 60
        return None

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._enabled or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        limit = self._limit_for(path)
        if limit is None:
            return await call_next(request)

        client = get_client_ip(request, self._trusted_proxies)
        key = f"{client}:{path.split('?')[0]}"

        if await self._store.check_and_tick(key, limit):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit {limit}/{int(WINDOW_SECONDS)}s on sensitive route",
                },
                headers={"Retry-After": str(int(WINDOW_SECONDS))},
            )
        return await call_next(request)

    async def _reset_store(self) -> None:  # pragma: no cover - solo tests
        await self._store._reset()


def _path_has_segment(path: str, segment: str) -> bool:
    return segment in path.split("/")


def _split_trusted_proxies(raw: str) -> set[str]:
    """Normaliza `TRUSTED_PROXIES` (coma-separados) a un set de hosts/IPs."""
    return {p.strip() for p in raw.split(",") if p.strip()}


def _request_client_host(request: Request) -> str:
    """IP real del peer inmediato (web server / proxy de borde)."""
    return request.client.host if request.client else "unknown"


def get_client_ip(request: Request, trusted_proxies: str = "") -> str:
    """IP del cliente para rate-limit respetando `X-Forwarded-For` con confianza.

    F-SEG-3 (anti-spoofing): el header `X-Forwarded-For` lo puede falsificar
    cualquier cliente, así que sólo se confía en él cuando el *peer inmediato*
    (``request.client.host``) es un proxy/host de confianza configurado en
    ``TRUSTED_PROXIES``.

    - Si el peer inmediato NO está en ``trusted_proxies`` (p. ej. dev/local sin
      proxy, o un host no listado) → se devuelve ``client.host`` y se ignora el
      header (un cliente externo no puede resetear su propio contador).
    - Si el peer inmediato SÍ es de confianza → se usa la **primera** dirección de
      ``X-Forwarded-For``, que es la que el cliente original dejó al entrar en la
      cadena de proxies (cada proxy hace append de su par inmediato). Un peer de
      confianza sobrescribe el header de cualquier cliente antes de reenviarlo.
    - Si no hay header o está vacío desde un peer de confianza → se cae a
      ``client.host`` (equivalente a un acceso directo en prod sin reverse proxy).
    """
    peer = _request_client_host(request)
    if trusted_proxies and peer in _split_trusted_proxies(trusted_proxies):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            first = forwarded.split(_FORWARDED_SEPARATOR, 1)[0].strip()
            if first:
                return first
    return peer


def _new_redis_client(redis_url: str) -> object:
    """Cliente Redis async lazy (compartido por el store de rate-limit)."""
    from redis.asyncio import Redis

    return Redis.from_url(redis_url)
