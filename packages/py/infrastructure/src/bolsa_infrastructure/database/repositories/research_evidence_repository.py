from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.research_evidence import ResearchEvidence
from bolsa_infrastructure.database.models import ResearchEvidenceRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyResearchEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: ResearchEvidenceRow) -> ResearchEvidence:
        return ResearchEvidence(
            id=row.id,
            instrument_id=row.instrument_id,
            level=row.level,  # type: ignore[arg-type]
            source=row.source,  # type: ignore[arg-type]
            evidence_weight=float(row.evidence_weight),
            summary=row.summary if isinstance(row.summary, dict) else {},
            created_at=row.created_at.isoformat(),
            trial_id=row.trial_id,
            hypothesis_id=row.hypothesis_id,
            edge_report_id=row.edge_report_id,
            math_version=row.math_version,
        )

    async def insert_evidence(
        self,
        *,
        instrument_id: str,
        level: str,
        source: str,
        evidence_weight: float,
        summary: dict[str, Any],
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        edge_report_id: str | None = None,
        math_version: str | None = None,
        evidence_id: str | None = None,
    ) -> ResearchEvidence:
        resolved_id = evidence_id or new_id()
        row = ResearchEvidenceRow(
            id=resolved_id,
            instrument_id=instrument_id,
            trial_id=trial_id,
            hypothesis_id=hypothesis_id,
            edge_report_id=edge_report_id,
            level=level,
            source=source,
            evidence_weight=Decimal(str(evidence_weight)),
            summary=summary,
            math_version=math_version,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def get_by_id(self, evidence_id: str) -> ResearchEvidence | None:
        stmt = select(ResearchEvidenceRow).where(ResearchEvidenceRow.id == evidence_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return None if row is None else self._map(row)

    async def list_evidence(
        self,
        *,
        instrument_id: str | None = None,
        trial_id: str | None = None,
        hypothesis_id: str | None = None,
        level: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchEvidence], int]:
        filters = []
        if instrument_id:
            filters.append(ResearchEvidenceRow.instrument_id == instrument_id)
        if trial_id:
            filters.append(ResearchEvidenceRow.trial_id == trial_id)
        if hypothesis_id:
            filters.append(ResearchEvidenceRow.hypothesis_id == hypothesis_id)
        if level:
            filters.append(ResearchEvidenceRow.level == level)

        count_stmt = select(func.count()).select_from(ResearchEvidenceRow)
        list_stmt = select(ResearchEvidenceRow)
        if filters:
            count_stmt = count_stmt.where(*filters)
            list_stmt = list_stmt.where(*filters)

        total = int((await self._session.execute(count_stmt)).scalar_one())
        list_stmt = (
            list_stmt.order_by(desc(ResearchEvidenceRow.created_at))
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(list_stmt)).scalars().all()
        return [self._map(r) for r in rows], total
