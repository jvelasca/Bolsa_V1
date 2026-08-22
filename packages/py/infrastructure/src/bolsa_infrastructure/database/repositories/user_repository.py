"""Repositorio mínimo de usuarios (R12-AUTH F5)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import UserRow


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> UserRow | None:
        stmt = select(UserRow).where(UserRow.id == user_id.strip())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_login(self, login: str) -> UserRow | None:
        stmt = select(UserRow).where(UserRow.login == login.strip())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_session_version(self, user_id: str) -> int:
        user = await self.get_by_id(user_id)
        if user is None:
            return 0
        new_sv = user.session_version + 1
        stmt = (
            update(UserRow)
            .where(UserRow.id == user_id.strip())
            .values(session_version=new_sv)
        )
        await self._session.execute(stmt)
        await self._session.commit()
        return new_sv

    async def update_password_hash(self, user_id: str, password_hash: str) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            return
        stmt = (
            update(UserRow)
            .where(UserRow.id == user_id.strip())
            .values(
                password_hash=password_hash,
                session_version=user.session_version + 1,
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

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
