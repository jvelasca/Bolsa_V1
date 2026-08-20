from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from bolsa_api.auth.session import SESSION_COOKIE_NAME, verify_session_cookie
from bolsa_api.auth.tokens import verify_access_token
from bolsa_infrastructure.config import get_settings

PUBLIC_PREFIXES = (
    "/api/health",
    "/api/auth/login",
    "/api/auth/logout",
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
            # R-8B.2: aceptar también la cookie HttpOnly firmada como alternativa
            # al header Bearer (el FE migra a cookie; Bearer queda de fallback).
            cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
            if not verify_session_cookie(settings, cookie_value or ""):
                return JSONResponse(status_code=401, content={"error": "Unauthorized"})

        return await call_next(request)
