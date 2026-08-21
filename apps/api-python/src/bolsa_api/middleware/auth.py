"""Gate opcional APP_PASSWORD (cookie HttpOnly + Bearer SHA-256, sin JWT)."""

from collections.abc import Awaitable, Callable

from bolsa_infrastructure.config import get_settings
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from bolsa_api.auth.principal import resolve_app_principal
from bolsa_api.auth.session import SESSION_COOKIE_NAME, verify_session_cookie
from bolsa_api.auth.tokens import verify_access_token

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
    """Adjunta ``request.state.principal`` y, si hay password, exige cookie/Bearer."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        path = request.url.path
        # Siempre: altas y tests auth-off estampan el mismo owner que el modo password.
        request.state.principal = resolve_app_principal(settings)

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
