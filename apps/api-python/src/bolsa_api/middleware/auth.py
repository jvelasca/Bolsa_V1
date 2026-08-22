"""Gate APP_PASSWORD + JWT (cookie HttpOnly + Bearer, ADR-027 C.2)."""

from collections.abc import Awaitable, Callable

from bolsa_infrastructure.config import get_settings
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from bolsa_api.auth.jwt import decode_access_token, extract_bearer_or_cookie_token
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


def _principal_from_jwt(request: Request) -> str | None:
    settings = get_settings()
    token = extract_bearer_or_cookie_token(
        dict(request.headers),
        request.cookies.get(SESSION_COOKIE_NAME),
    )
    claims = decode_access_token(settings, token)
    if claims is None:
        return None
    sub = claims.get("sub")
    return sub.strip() if isinstance(sub, str) and sub.strip() else None


class AuthMiddleware(BaseHTTPMiddleware):
    """Adjunta ``request.state.principal`` y exige JWT o gate legacy si hay password."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        path = request.url.path
        request.state.principal = resolve_app_principal(settings)

        if not settings.app_password:
            return await call_next(request)

        if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        jwt_principal = _principal_from_jwt(request)
        if jwt_principal is not None:
            request.state.principal = jwt_principal
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()
        if verify_access_token(settings, token):
            return await call_next(request)

        cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
        if verify_session_cookie(settings, cookie_value or ""):
            return await call_next(request)

        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
