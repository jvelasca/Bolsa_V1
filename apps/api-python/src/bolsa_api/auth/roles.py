"""Enforcement de roles JWT (R12-AUTH F10 / ADR-027)."""

from __future__ import annotations

from fastapi import HTTPException, Request

__all__ = ["require_role"]


def require_role(request: Request, role: str) -> None:
    """Exige que el JWT autenticado incluya ``role`` (403 si no coincide)."""
    auth_role = getattr(request.state, "auth_role", None)
    if auth_role != role:
        raise HTTPException(status_code=403, detail="Forbidden")
