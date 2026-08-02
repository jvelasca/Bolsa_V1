from collections.abc import Awaitable, Callable

from bolsa_infrastructure.config import get_settings
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from bolsa_api.auth.tokens import verify_access_token

PUBLIC_PREFIXES = (
    "/api/health",
    "/api/auth/login",
    "/api/auth/status",
    "/api/docs",
    "/api/openapi.json",
    "/api/redoc",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        path = request.url.path

        if not settings.app_password:
            return await call_next(request)

        if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()
        if not verify_access_token(settings, token):
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})

        return await call_next(request)
