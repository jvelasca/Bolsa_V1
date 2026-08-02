"""Simple in-memory rate limit for sensitive API routes (Q2.5)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# path prefix → max requests per window_seconds
SENSITIVE_PREFIXES: tuple[tuple[str, int], ...] = (
    ("/api/instruments/fundamentals", 60),
    ("/api/ai/fundamentals", 30),
    ("/api/ai/", 40),
    ("/api/sync", 20),
)

# Also match /api/instruments/{id}/fundamentals and /sync
_EXTRA_CONTAINS = (
    "/fundamentals",
    "/sync",
)

WINDOW_SECONDS = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, enabled: bool = True) -> None:
        super().__init__(app)
        self._enabled = enabled
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _limit_for(self, path: str) -> int | None:
        for prefix, limit in SENSITIVE_PREFIXES:
            if path.startswith(prefix):
                return limit
        if any(tok in path for tok in _EXTRA_CONTAINS) and path.startswith("/api/"):
            if "/sync" in path:
                return 20
            if "fundamentals" in path:
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

        client = request.client.host if request.client else "unknown"
        key = f"{client}:{path.split('?')[0]}"
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": f"Rate limit {limit}/{int(WINDOW_SECONDS)}s on sensitive route",
                },
                headers={"Retry-After": str(int(WINDOW_SECONDS))},
            )
        q.append(now)
        return await call_next(request)
