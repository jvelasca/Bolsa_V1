from datetime import UTC, datetime
from typing import Any

from bolsa_domain.entities.hypothesis import Hypothesis
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import HypothesisRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyHypothesisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: HypothesisRow) -> Hypothesis:
        falsifiers = row.falsifiers if isinstance(row.falsifiers, list) else []
        return Hypothesis(
            id=row.id,
            kind=row.kind,  # type: ignore[arg-type]
            statement=row.statement,
            falsifiers=[f for f in falsifiers if isinstance(f, dict)],
            status=row.status,  # type: ignore[arg-type]
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
            domain=row.domain,
            context=row.context if isinstance(row.context, dict) else None,
        )

    async def insert(
        self,
        *,
        statement: str,
        falsifiers: list[dict[str, Any]],
        kind: str = "hypothesis",
        domain: str | None = None,
        context: dict[str, Any] | None = None,
        status: str = "open",
        hypothesis_id: str | None = None,
    ) -> Hypothesis:
        now = datetime.now(UTC)
        row = HypothesisRow(
            id=hypothesis_id or new_id(),
            kind=kind,
            statement=statement,
            domain=domain,
            context=context,
            falsifiers=falsifiers,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def get_by_id(self, hypothesis_id: str) -> Hypothesis | None:
        stmt = select(HypothesisRow).where(HypothesisRow.id == hypothesis_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return None if row is None else self._map(row)

    async def list(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Hypothesis], int]:
        filters = []
        if status:
            filters.append(HypothesisRow.status == status)
        if kind:
            filters.append(HypothesisRow.kind == kind)

        count_stmt = select(func.count()).select_from(HypothesisRow)
        list_stmt = select(HypothesisRow)
        if filters:
            count_stmt = count_stmt.where(*filters)
            list_stmt = list_stmt.where(*filters)

        total = int((await self._session.execute(count_stmt)).scalar_one())
        list_stmt = (
            list_stmt.order_by(desc(HypothesisRow.created_at)).limit(limit).offset(offset)
        )
        rows = (await self._session.execute(list_stmt)).scalars().all()
        return [self._map(r) for r in rows], total

    async def update(
        self,
        hypothesis_id: str,
        *,
        statement: str | None = None,
        falsifiers: list[dict[str, Any]] | None = None,
        kind: str | None = None,
        domain: str | None = None,
        context: dict[str, Any] | None = None,
        status: str | None = None,
        clear_domain: bool = False,
        clear_context: bool = False,
    ) -> Hypothesis | None:
        stmt = select(HypothesisRow).where(HypothesisRow.id == hypothesis_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if statement is not None:
            row.statement = statement
        if falsifiers is not None:
            row.falsifiers = falsifiers
        if kind is not None:
            row.kind = kind
        if status is not None:
            row.status = status
        if clear_domain:
            row.domain = None
        elif domain is not None:
            row.domain = domain
        if clear_context:
            row.context = None
        elif context is not None:
            row.context = context
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return self._map(row)
