"""Gate APP_PASSWORD + JWT (cookie HttpOnly + Bearer, ADR-027 C.2)."""

from collections.abc import Awaitable, Callable

from bolsa_application.context.principal import reset_current_principal, set_current_principal
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from bolsa_api.auth.jwt import (
    decode_access_token,
    extract_bearer_or_cookie_token,
    session_version_matches,
)
from bolsa_api.auth.principal import resolve_app_principal
from bolsa_api.auth.session import SESSION_COOKIE_NAME, verify_session_cookie
from bolsa_api.auth.tokens import verify_access_token

PUBLIC_PREFIXES = (
    "/api/health",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/refresh",
    "/api/auth/status",
    "/api/docs",
    "/api/openapi.json",
    "/api/redoc",
)


async def _principal_from_jwt(request: Request) -> tuple[str | None, str | None]:
    settings = get_settings()
    token = extract_bearer_or_cookie_token(
        dict(request.headers),
        request.cookies.get(SESSION_COOKIE_NAME),
    )
    claims = decode_access_token(settings, token)
    if claims is None:
        return None, None
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        return None, None

    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        return None, None

    async with factory() as session:
        repo = SqlAlchemyUserRepository(session)
        user = await repo.get_by_id(sub.strip())
        if user is None or user.disabled_at is not None:
            return None, None
        if not session_version_matches(claims, user.session_version):
            return None, None

    role = claims.get("role")
    role_str = role if isinstance(role, str) else None
    return sub.strip(), role_str


class AuthMiddleware(BaseHTTPMiddleware):
    """Adjunta ``request.state.principal`` y exige JWT o gate legacy si hay password."""

    async def _dispatch_with_principal_context(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        token = set_current_principal(request.state.principal)
        try:
            return await call_next(request)
        finally:
            reset_current_principal(token)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        path = request.url.path
        request.state.principal = resolve_app_principal(settings)
        request.state.auth_role = None

        if not settings.app_password:
            return await self._dispatch_with_principal_context(request, call_next)

        if any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await self._dispatch_with_principal_context(request, call_next)

        if request.method == "OPTIONS":
            return await self._dispatch_with_principal_context(request, call_next)

        jwt_principal, jwt_role = await _principal_from_jwt(request)
        if jwt_principal is not None:
            request.state.principal = jwt_principal
            request.state.auth_role = jwt_role
            return await self._dispatch_with_principal_context(request, call_next)

        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()
        if verify_access_token(settings, token):
            return await self._dispatch_with_principal_context(request, call_next)

        cookie_value = request.cookies.get(SESSION_COOKIE_NAME)
        if verify_session_cookie(settings, cookie_value or ""):
            return await self._dispatch_with_principal_context(request, call_next)

        return JSONResponse(status_code=401, content={"error": "Unauthorized"})
