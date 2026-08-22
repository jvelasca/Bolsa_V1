"""Principal del request (R12-AUTH).

El middleware inicializa ``request.state.principal`` con
``Settings.owner_principal()`` (default ``app``). Con auth ON y JWT válido
lo sustituye por el ``sub`` del token. El mismo valor de propietario se
estampa en altas nuevas de ``InvestmentAccount.user_id`` cuando aplica.
"""

from __future__ import annotations

from bolsa_infrastructure.config import Settings

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
    """True si ``user_id == principal`` (F7c: legacy NULL nunca visible)."""
    return user_id == principal
