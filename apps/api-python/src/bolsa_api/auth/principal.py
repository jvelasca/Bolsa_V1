"""Principal single-tenant del request (R12-AUTH fase 1).

No hay JWT ni claims: tras el gate ``APP_PASSWORD`` el middleware adjunta
``request.state.principal`` con ``Settings.owner_principal()`` (default ``app``).
El mismo valor se estampa en altas nuevas de ``InvestmentAccount.user_id``.
"""

from __future__ import annotations

from bolsa_infrastructure.config import Settings, get_settings
from fastapi import Request

DEFAULT_APP_PRINCIPAL = "app"

__all__ = [
    "DEFAULT_APP_PRINCIPAL",
    "account_visible_to_principal",
    "get_request_principal",
    "resolve_app_principal",
]


def resolve_app_principal(settings: Settings) -> str:
    """Devuelve el principal single-tenant (``APP_OWNER_ID``, default ``app``)."""
    return settings.owner_principal() or DEFAULT_APP_PRINCIPAL


def get_request_principal(request: Request) -> str:
    """Lee ``request.state.principal`` o cae al owner de settings si falta."""
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, str) and principal.strip():
        return principal.strip()
    return resolve_app_principal(get_settings())


def account_visible_to_principal(user_id: str | None, principal: str) -> bool:
    """True si la cuenta es legacy (``user_id is None``) o del ``principal``."""
    return user_id is None or user_id == principal
