"""Lee ``request.state.principal`` del request autenticado (R12-AUTH F5)."""

from __future__ import annotations

from bolsa_infrastructure.config import get_settings
from fastapi import Request

from bolsa_api.auth.principal import resolve_app_principal

__all__ = ["get_request_principal"]


def get_request_principal(request: Request) -> str:
    """Lee ``request.state.principal`` o cae al owner de settings si falta."""
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, str) and principal.strip():
        return principal.strip()
    return resolve_app_principal(get_settings())
