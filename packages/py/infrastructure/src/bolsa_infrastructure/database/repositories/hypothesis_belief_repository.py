from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from bolsa_domain.entities.hypothesis_belief import BeliefHistoryEntry, HypothesisBelief
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import BeliefHistoryRow, HypothesisBeliefRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyHypothesisBeliefRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map_belief(self, row: HypothesisBeliefRow) -> HypothesisBelief:
        def _str_list(raw: Any) -> list[str]:
            if not isinstance(raw, list):
                return []
            return [str(x) for x in raw if isinstance(x, (str, int, float))]

        return HypothesisBelief(
            id=row.id,
            hypothesis_id=row.hypothesis_id,
            belief=float(row.belief),
            belief_ci_low=float(row.belief_ci_low),
            belief_ci_high=float(row.belief_ci_high),
            n_experiments=int(row.n_experiments),
            evidence_weight=float(row.evidence_weight),
            contexts_ok=_str_list(row.contexts_ok),
            contexts_fail=_str_list(row.contexts_fail),
            evidence_ids=_str_list(row.evidence_ids),
            trial_ids=_str_list(row.trial_ids),
            math_version=row.math_version,
            last_reviewed_at=row.last_reviewed_at.isoformat(),
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
        )

    def _map_history(self, row: BeliefHistoryRow) -> BeliefHistoryEntry:
        return BeliefHistoryEntry(
            id=row.id,
            hypothesis_id=row.hypothesis_id,
            belief_id=row.belief_id,
            belief=float(row.belief),
            belief_ci_low=float(row.belief_ci_low),
            belief_ci_high=float(row.belief_ci_high),
            n_experiments=int(row.n_experiments),
            evidence_weight=float(row.evidence_weight),
            math_version=row.math_version,
            created_at=row.created_at.isoformat(),
            trigger_evidence_id=row.trigger_evidence_id,
            delta=row.delta if isinstance(row.delta, dict) else None,
        )

    async def get_by_hypothesis_id(self, hypothesis_id: str) -> HypothesisBelief | None:
        stmt = select(HypothesisBeliefRow).where(
            HypothesisBeliefRow.hypothesis_id == hypothesis_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map_belief(row)

    async def get_by_id(self, belief_id: str) -> HypothesisBelief | None:
        stmt = select(HypothesisBeliefRow).where(HypothesisBeliefRow.id == belief_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map_belief(row)

    async def upsert_state(
        self,
        *,
        hypothesis_id: str,
        belief: float,
        belief_ci_low: float,
        belief_ci_high: float,
        n_experiments: int,
        evidence_weight: float,
        contexts_ok: list[str],
        contexts_fail: list[str],
        evidence_ids: list[str],
        trial_ids: list[str],
        math_version: str,
        belief_id: str | None = None,
    ) -> HypothesisBelief:
        now = datetime.now(UTC)
        existing = await self.get_by_hypothesis_id(hypothesis_id)
        if existing is None:
            row = HypothesisBeliefRow(
                id=belief_id or new_id(),
                hypothesis_id=hypothesis_id,
                belief=Decimal(str(belief)),
                belief_ci_low=Decimal(str(belief_ci_low)),
                belief_ci_high=Decimal(str(belief_ci_high)),
                n_experiments=n_experiments,
                evidence_weight=Decimal(str(evidence_weight)),
                contexts_ok=list(contexts_ok),
                contexts_fail=list(contexts_fail),
                evidence_ids=list(evidence_ids),
                trial_ids=list(trial_ids),
                math_version=math_version,
                last_reviewed_at=now,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
            await self._session.flush()
            return self._map_belief(row)

        stmt = select(HypothesisBeliefRow).where(
            HypothesisBeliefRow.hypothesis_id == hypothesis_id
        )
        row = (await self._session.execute(stmt)).scalar_one()
        row.belief = Decimal(str(belief))
        row.belief_ci_low = Decimal(str(belief_ci_low))
        row.belief_ci_high = Decimal(str(belief_ci_high))
        row.n_experiments = n_experiments
        row.evidence_weight = Decimal(str(evidence_weight))
        row.contexts_ok = list(contexts_ok)
        row.contexts_fail = list(contexts_fail)
        row.evidence_ids = list(evidence_ids)
        row.trial_ids = list(trial_ids)
        row.math_version = math_version
        row.last_reviewed_at = now
        row.updated_at = now
        await self._session.flush()
        return self._map_belief(row)

    async def append_history(
        self,
        *,
        hypothesis_id: str,
        belief_id: str,
        belief: float,
        belief_ci_low: float,
        belief_ci_high: float,
        n_experiments: int,
        evidence_weight: float,
        math_version: str,
        trigger_evidence_id: str | None = None,
        delta: dict[str, Any] | None = None,
    ) -> BeliefHistoryEntry:
        row = BeliefHistoryRow(
            id=new_id(),
            hypothesis_id=hypothesis_id,
            belief_id=belief_id,
            belief=Decimal(str(belief)),
            belief_ci_low=Decimal(str(belief_ci_low)),
            belief_ci_high=Decimal(str(belief_ci_high)),
            n_experiments=n_experiments,
            evidence_weight=Decimal(str(evidence_weight)),
            trigger_evidence_id=trigger_evidence_id,
            delta=delta,
            math_version=math_version,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return self._map_history(row)

    async def list_history(
        self,
        hypothesis_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[BeliefHistoryEntry], int]:
        filters = [BeliefHistoryRow.hypothesis_id == hypothesis_id]
        count_stmt = select(func.count()).select_from(BeliefHistoryRow).where(*filters)
        total = int((await self._session.execute(count_stmt)).scalar_one())
        list_stmt = (
            select(BeliefHistoryRow)
            .where(*filters)
            .order_by(desc(BeliefHistoryRow.created_at))
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(list_stmt)).scalars().all()
        return [self._map_history(r) for r in rows], total
