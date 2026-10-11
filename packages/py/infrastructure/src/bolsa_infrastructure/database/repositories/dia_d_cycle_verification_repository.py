"""Repositorio SQLAlchemy — verificación DÍA-D enlazada a un ciclo AUTO (P2)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.dia_d_cycle_verification import DiaDCycleVerification
from bolsa_infrastructure.database.models import DiaDCycleVerificationRow
from bolsa_infrastructure.ids import new_id


class SqlAlchemyDiaDCycleVerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: DiaDCycleVerificationRow) -> DiaDCycleVerification:
        return DiaDCycleVerification(
            id=row.id,
            cycle_id=row.cycle_id,
            account_id=row.account_id,
            instrument_id=row.instrument_id,
            symbol=row.symbol,
            dia_d=row.dia_d,
            end_date=row.end_date,
            mode=row.mode,
            created_at=row.created_at.isoformat(),
            strategy_preset_key=row.strategy_preset_key,
            strategy_version=row.strategy_version,
            strategy_definition_id=row.strategy_definition_id,
            band=row.band,
            result=row.result if isinstance(row.result, dict) else None,
            research_evidence_id=row.research_evidence_id,
        )

    async def _find(
        self, *, cycle_id: str, dia_d: str, end_date: str, mode: str
    ) -> DiaDCycleVerificationRow | None:
        stmt = select(DiaDCycleVerificationRow).where(
            DiaDCycleVerificationRow.cycle_id == cycle_id,
            DiaDCycleVerificationRow.dia_d == dia_d,
            DiaDCycleVerificationRow.end_date == end_date,
            DiaDCycleVerificationRow.mode == mode,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert(
        self,
        *,
        cycle_id: str,
        instrument_id: str,
        symbol: str,
        dia_d: str,
        end_date: str,
        mode: str,
        account_id: str | None = None,
        strategy_preset_key: str | None = None,
        strategy_version: str | None = None,
        strategy_definition_id: str | None = None,
        band: str | None = None,
        result: dict[str, Any] | None = None,
        research_evidence_id: str | None = None,
        verification_id: str | None = None,
    ) -> DiaDCycleVerification:
        """Idempotente por ``(cycle_id, dia_d, end_date, mode)``: re-verificar actualiza.

        Un campo ``None`` NO se rellena con relleno: se persiste el hueco declarado.
        """
        existing = await self._find(
            cycle_id=cycle_id, dia_d=dia_d, end_date=end_date, mode=mode
        )
        if existing is not None:
            existing.account_id = account_id
            existing.instrument_id = instrument_id
            existing.symbol = symbol
            existing.strategy_preset_key = strategy_preset_key
            existing.strategy_version = strategy_version
            existing.strategy_definition_id = strategy_definition_id
            existing.band = band
            existing.result = result or {}
            existing.research_evidence_id = research_evidence_id
            await self._session.flush()
            return self._map(existing)

        row = DiaDCycleVerificationRow(
            id=verification_id or new_id(),
            cycle_id=cycle_id,
            account_id=account_id,
            instrument_id=instrument_id,
            symbol=symbol,
            strategy_preset_key=strategy_preset_key,
            strategy_version=strategy_version,
            strategy_definition_id=strategy_definition_id,
            dia_d=dia_d,
            end_date=end_date,
            mode=mode,
            band=band,
            result=result or {},
            research_evidence_id=research_evidence_id,
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def list_verifications(
        self,
        *,
        account_id: str | None = None,
        cycle_id: str | None = None,
        limit: int = 200,
    ) -> list[DiaDCycleVerification]:
        """Verificaciones del principal; con ``cycle_id`` acota a un ciclo.

        ``account_id`` es el aislamiento por cuenta (fail-closed en el llamante).
        """
        filters = []
        if account_id is not None:
            filters.append(DiaDCycleVerificationRow.account_id == account_id)
        if cycle_id is not None:
            filters.append(DiaDCycleVerificationRow.cycle_id == cycle_id)
        stmt = select(DiaDCycleVerificationRow)
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(desc(DiaDCycleVerificationRow.created_at)).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._map(r) for r in rows]

    async def get_by_id(self, verification_id: str) -> DiaDCycleVerification | None:
        stmt = select(DiaDCycleVerificationRow).where(
            DiaDCycleVerificationRow.id == verification_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else self._map(row)
