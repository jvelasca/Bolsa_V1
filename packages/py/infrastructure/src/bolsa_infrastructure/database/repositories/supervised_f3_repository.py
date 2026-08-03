"""SEMI Confirm F3 — cola supervisada por cuenta (blob JSON)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import SupervisedF3AccountStateRow


@dataclass(frozen=True, slots=True)
class SupervisedF3AccountStateRecord:
    account_id: str
    queue: list[dict[str, Any]]
    active_id: str | None
    updated_at: datetime


class SqlAlchemySupervisedF3Repository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: SupervisedF3AccountStateRow) -> SupervisedF3AccountStateRecord:
        queue = row.queue_json if isinstance(row.queue_json, list) else []
        return SupervisedF3AccountStateRecord(
            account_id=row.account_id,
            queue=[x for x in queue if isinstance(x, dict)],
            active_id=row.active_id if isinstance(row.active_id, str) else None,
            updated_at=row.updated_at,
        )

    async def get(self, account_id: str) -> SupervisedF3AccountStateRecord | None:
        stmt = select(SupervisedF3AccountStateRow).where(
            SupervisedF3AccountStateRow.account_id == account_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def upsert(
        self,
        account_id: str,
        *,
        queue: list[dict[str, Any]],
        active_id: str | None,
    ) -> SupervisedF3AccountStateRecord:
        stmt = select(SupervisedF3AccountStateRow).where(
            SupervisedF3AccountStateRow.account_id == account_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        now = datetime.now(tz=UTC)
        if row is None:
            row = SupervisedF3AccountStateRow(
                account_id=account_id,
                queue_json=list(queue),
                active_id=active_id,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.queue_json = list(queue)
            row.active_id = active_id
            row.updated_at = now
        await self._session.flush()
        return self._map(row)
