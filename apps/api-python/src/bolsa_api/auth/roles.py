"""Enforcement de roles JWT (R12-AUTH F10 / ADR-027)."""

from __future__ import annotations

from fastapi import HTTPException, Request

from bolsa_infrastructure.config import get_settings

__all__ = ["require_admin_when_auth_enabled", "require_role"]


def require_role(request: Request, role: str) -> None:
    """Exige que el JWT autenticado incluya ``role`` (403 si no coincide)."""
    auth_role = getattr(request.state, "auth_role", None)
    if auth_role != role:
        raise HTTPException(status_code=403, detail="Forbidden")


def require_admin_when_auth_enabled(request: Request) -> None:
    """Exige rol ``admin`` **solo** cuando la autenticación está activa.

    Con ``APP_PASSWORD`` vacío la app es local y no hay JWT que inspeccionar: exigir un
    rol ahí bloquearía el desarrollo sin proteger nada (no hay usuario que suplantar).
    Con auth activa, en cambio, una acción que escribe en disco y ejecuta un proceso es de
    administración: sin claim ``role=admin`` se responde 403 (fail-closed, también para un
    token válido sin rol declarado).
    """
    if not get_settings().app_password:
        return
    require_role(request, "admin")
