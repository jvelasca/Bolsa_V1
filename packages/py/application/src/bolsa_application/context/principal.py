"""Principal del request activo (ContextVar) para estampar altas fuera de la capa API."""

from __future__ import annotations

from contextvars import ContextVar, Token

_current_principal: ContextVar[str | None] = ContextVar("current_principal", default=None)

__all__ = [
    "get_current_principal",
    "reset_current_principal",
    "set_current_principal",
]


def get_current_principal() -> str | None:
    return _current_principal.get()


def set_current_principal(principal: str | None) -> Token[str | None]:
    return _current_principal.set(principal)


def reset_current_principal(token: Token[str | None]) -> None:
    _current_principal.reset(token)
