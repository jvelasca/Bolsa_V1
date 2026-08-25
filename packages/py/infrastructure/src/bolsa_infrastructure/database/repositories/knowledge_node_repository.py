from __future__ import annotations

import builtins
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.knowledge_node import KnowledgeNode
from bolsa_infrastructure.database.models import KnowledgeNodeRow
from bolsa_infrastructure.ids import new_id

_ACTIVE_STAGES = ("CANDIDATE", "EMERGING", "ACCEPTED", "CANONICAL")


class SqlAlchemyKnowledgeNodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: KnowledgeNodeRow) -> KnowledgeNode:
        evidence_ids = row.evidence_ids if isinstance(row.evidence_ids, list) else []
        return KnowledgeNode(
            id=row.id,
            hypothesis_id=row.hypothesis_id,
            stage=row.stage,  # type: ignore[arg-type]
            statement=row.statement,
            knowledge_confidence=float(row.knowledge_confidence),
            validity_context=(
                row.validity_context if isinstance(row.validity_context, dict) else {}
            ),
            evidence_ids=[str(x) for x in evidence_ids if isinstance(x, (str, int))],
            belief_snapshot=(
                row.belief_snapshot if isinstance(row.belief_snapshot, dict) else {}
            ),
            consolidation_report=(
                row.consolidation_report
                if isinstance(row.consolidation_report, dict)
                else {}
            ),
            math_version=row.math_version,
            consolidated_at=row.consolidated_at.isoformat(),
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
            notes=row.notes,
        )

    async def insert(
        self,
        *,
        hypothesis_id: str,
        stage: str,
        statement: str,
        knowledge_confidence: float,
        validity_context: dict[str, Any],
        evidence_ids: list[str],
        belief_snapshot: dict[str, Any],
        consolidation_report: dict[str, Any],
        math_version: str,
        notes: str | None = None,
        node_id: str | None = None,
    ) -> KnowledgeNode:
        now = datetime.now(UTC)
        row = KnowledgeNodeRow(
            id=node_id or new_id(),
            hypothesis_id=hypothesis_id,
            stage=stage,
            statement=statement,
            knowledge_confidence=Decimal(str(knowledge_confidence)),
            validity_context=validity_context,
            evidence_ids=list(evidence_ids),
            belief_snapshot=belief_snapshot,
            consolidation_report=consolidation_report,
            math_version=math_version,
            notes=notes,
            consolidated_at=now,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def get_by_id(self, node_id: str) -> KnowledgeNode | None:
        stmt = select(KnowledgeNodeRow).where(KnowledgeNodeRow.id == node_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)

    async def list(
        self,
        *,
        hypothesis_id: str | None = None,
        stage: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[KnowledgeNode], int]:
        filters = []
        if hypothesis_id:
            filters.append(KnowledgeNodeRow.hypothesis_id == hypothesis_id)
        if stage:
            filters.append(KnowledgeNodeRow.stage == stage)
        count_stmt = select(func.count()).select_from(KnowledgeNodeRow)
        list_stmt = select(KnowledgeNodeRow)
        if filters:
            count_stmt = count_stmt.where(*filters)
            list_stmt = list_stmt.where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())
        list_stmt = (
            list_stmt.order_by(desc(KnowledgeNodeRow.created_at))
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(list_stmt)).scalars().all()
        return [self._map(r) for r in rows], total

    async def list_active_for_hypothesis(
        self, hypothesis_id: str
    ) -> builtins.list[KnowledgeNode]:
        stmt = select(KnowledgeNodeRow).where(
            KnowledgeNodeRow.hypothesis_id == hypothesis_id,
            KnowledgeNodeRow.stage.in_(_ACTIVE_STAGES),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._map(r) for r in rows]

    async def update_stage(self, node_id: str, stage: str) -> KnowledgeNode | None:
        stmt = select(KnowledgeNodeRow).where(KnowledgeNodeRow.id == node_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        row.stage = stage
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return self._map(row)
