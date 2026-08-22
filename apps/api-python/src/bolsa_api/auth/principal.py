"""Principal single-tenant del request (R12-AUTH fase 1).

No hay JWT ni claims: tras el gate ``APP_PASSWORD`` el middleware adjunta
``request.state.principal`` con ``Settings.owner_principal()`` (default ``app``).
El mismo valor se estampa en altas nuevas de ``InvestmentAccount.user_id``.
"""

from __future__ import annotations

from bolsa_infrastructure.config import Settings, get_settings

DEFAULT_APP_PRINCIPAL = "app"

__all__ = [
    "DEFAULT_APP_PRINCIPAL",
    "account_visible_to_principal",
    "resolve_app_principal",
]


def resolve_app_principal(settings: Settings) -> str:
    """Devuelve el principal single-tenant (``APP_OWNER_ID``, default ``app``)."""
    return settings.owner_principal() or DEFAULT_APP_PRINCIPAL


def account_visible_to_principal(user_id: str | None, principal: str) -> bool:
    """True si la cuenta es del ``principal`` (F7a: legacy NULL solo bootstrap)."""
    if user_id == principal:
        return True
    if user_id is None:
        return principal == resolve_app_principal(get_settings())
    return False
