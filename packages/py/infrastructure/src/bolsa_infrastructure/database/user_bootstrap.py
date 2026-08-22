"""Seed one-shot del admin bootstrap (ADR-027 C.1 / F5).

Crea un único user con ``id = APP_OWNER_ID`` (default ``app``) si la tabla
``users`` está vacía. Contraseña:

- ``APP_BOOTSTRAP_PASSWORD`` si está definida, o
- ``APP_PASSWORD`` (derivación única documentada para transición C.1→C.2).

Login: ``APP_BOOTSTRAP_LOGIN`` (default ``app``). Sin registro público.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.auth.passwords import hash_password
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.user_repository import SqlAlchemyUserRepository


async def ensure_bootstrap_user(session: AsyncSession) -> None:
    settings = get_settings()
    repo = SqlAlchemyUserRepository(session)
    if await repo.count_users() > 0:
        return

    plain_password = settings.bootstrap_password()
    if not plain_password:
        return

    await repo.create_bootstrap_user(
        user_id=settings.owner_principal(),
        login=settings.bootstrap_login(),
        password_hash=hash_password(plain_password),
        role="admin",
    )
