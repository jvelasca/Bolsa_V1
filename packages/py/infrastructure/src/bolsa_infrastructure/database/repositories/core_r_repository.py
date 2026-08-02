"""CORE-R account state repository (Q3.4) — blob JSON por cuenta."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import CoreRAccountStateRow


@dataclass(frozen=True, slots=True)
class CoreRAccountStateRecord:
    account_id: str
    queue: list[dict[str, Any]]
    reports: dict[str, Any]
    scheduler: dict[str, Any]
    updated_at: datetime


class SqlAlchemyCoreRRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: CoreRAccountStateRow) -> CoreRAccountStateRecord:
        queue = row.queue_json if isinstance(row.queue_json, list) else []
        reports = row.reports_json if isinstance(row.reports_json, dict) else {}
        scheduler = row.scheduler_json if isinstance(row.scheduler_json, dict) else {}
        return CoreRAccountStateRecord(
            account_id=row.account_id,
            queue=[x for x in queue if isinstance(x, dict)],
            reports=reports,
            scheduler=scheduler,
            updated_at=row.updated_at,
        )

    async def get(self, account_id: str) -> CoreRAccountStateRecord | None:
        stmt = select(CoreRAccountStateRow).where(CoreRAccountStateRow.account_id == account_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def upsert(
        self,
        account_id: str,
        *,
        queue: list[dict[str, Any]],
        reports: dict[str, Any],
        scheduler: dict[str, Any],
    ) -> CoreRAccountStateRecord:
        stmt = select(CoreRAccountStateRow).where(CoreRAccountStateRow.account_id == account_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        now = datetime.now(tz=UTC)
        if row is None:
            row = CoreRAccountStateRow(
                account_id=account_id,
                queue_json=list(queue),
                reports_json=dict(reports),
                scheduler_json=dict(scheduler),
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.queue_json = list(queue)
            row.reports_json = dict(reports)
            row.scheduler_json = dict(scheduler)
            row.updated_at = now
        await self._session.flush()
        return self._map(row)
