"""Repositorio mínimo de usuarios (R12-AUTH F5)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import UserRow


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_login(self, login: str) -> UserRow | None:
        stmt = select(UserRow).where(UserRow.login == login.strip())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_users(self) -> int:
        stmt = select(func.count()).select_from(UserRow)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def create_bootstrap_user(
        self,
        *,
        user_id: str,
        login: str,
        password_hash: str,
        role: str | None = "admin",
    ) -> UserRow:
        now = datetime.now(UTC)
        row = UserRow(
            id=user_id,
            login=login.strip(),
            password_hash=password_hash,
            role=role,
            created_at=now,
            disabled_at=None,
        )
        self._session.add(row)
        await self._session.commit()
        return row
