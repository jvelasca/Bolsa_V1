"""Lee ``request.state.principal`` del request autenticado (R12-AUTH F5)."""

from __future__ import annotations

from fastapi import HTTPException, Request

from bolsa_api.auth.principal import resolve_app_principal
from bolsa_infrastructure.config import get_settings

__all__ = ["get_request_principal", "require_jwt_principal"]


def get_request_principal(request: Request) -> str:
    """Lee ``request.state.principal`` o cae al owner de settings si falta."""
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, str) and principal.strip():
        return principal.strip()
    return resolve_app_principal(get_settings())


async def require_jwt_principal(request: Request) -> str:
    """401 unless a valid JWT principal is present. Lifecycle must not fall back."""
    from bolsa_api.middleware.auth import _principal_from_jwt

    principal, role = await _principal_from_jwt(request)
    if principal is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "JWT required"},
        )
    request.state.principal = principal
    if role:
        request.state.auth_role = role
    return principal
