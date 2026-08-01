from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import InstrumentRow, OptimizationRunRow
from bolsa_infrastructure.ids import new_id

OptimizationRunStatus = Literal["pending", "processing", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class OptimizationRunRecord:
    id: str
    instrument_id: str
    symbol: str
    status: OptimizationRunStatus
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    engine: str | None
    best_score: float | None
    trial_count: int | None
    bar_count: int | None
    created_at: str
    updated_at: str
    completed_at: str | None


class SqlAlchemyOptimizationRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_pending(self, payload: dict[str, Any]) -> OptimizationRunRecord:
        instrument_id = str(payload.get("instrumentId") or "")
        if not instrument_id:
            raise ValueError("payload.instrumentId es obligatorio")

        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        result = await self._session.execute(stmt)
        instrument = result.scalar_one_or_none()
        if instrument is None:
            raise ValueError("Instrumento no encontrado")

        now = datetime.now(UTC)
        row = OptimizationRunRow(
            id=new_id(),
            instrument_id=instrument_id,
            symbol=instrument.symbol,
            status="pending",
            payload=payload,
            result=None,
            error=None,
            engine=str(payload.get("engine") or "auto"),
            best_score=None,
            trial_count=None,
            bar_count=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)

    async def create_completed(
        self,
        payload: dict[str, Any],
        result: dict[str, Any],
    ) -> OptimizationRunRecord:
        instrument_id = str(payload.get("instrumentId") or result.get("instrumentId") or "")
        if not instrument_id:
            raise ValueError("instrumentId es obligatorio")

        stmt = select(InstrumentRow).where(InstrumentRow.id == instrument_id)
        db_result = await self._session.execute(stmt)
        instrument = db_result.scalar_one_or_none()
        if instrument is None:
            raise ValueError("Instrumento no encontrado")

        trials = result.get("trials") or []
        best_score = None
        if trials:
            best_score = float(trials[0].get("score", 0))

        now = datetime.now(UTC)
        row = OptimizationRunRow(
            id=new_id(),
            instrument_id=instrument_id,
            symbol=instrument.symbol,
            status="completed",
            payload=payload,
            result=result,
            error=None,
            engine=str(result.get("engine")),
            best_score=Decimal(str(best_score)) if best_score is not None else None,
            trial_count=len(trials),
            bar_count=int(result.get("barCount") or 0),
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_record(row)

    async def get_by_id(self, run_id: str) -> OptimizationRunRecord | None:
        stmt = select(OptimizationRunRow).where(OptimizationRunRow.id == run_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_record(row)

    async def list_recent(self, *, limit: int = 20) -> list[OptimizationRunRecord]:
        stmt = (
            select(OptimizationRunRow)
            .order_by(OptimizationRunRow.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_record(row) for row in result.scalars().all()]

    async def claim_next(self) -> OptimizationRunRecord | None:
        stmt = (
            select(OptimizationRunRow)
            .where(OptimizationRunRow.status == "pending")
            .order_by(OptimizationRunRow.created_at.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return await self._claim_row(row.id)

    async def claim_by_id(self, run_id: str) -> OptimizationRunRecord | None:
        return await self._claim_row(run_id)

    async def _claim_row(self, run_id: str) -> OptimizationRunRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(OptimizationRunRow)
            .where(OptimizationRunRow.id == run_id, OptimizationRunRow.status == "pending")
            .values(status="processing", updated_at=now)
            .returning(OptimizationRunRow)
        )
        updated = await self._session.execute(stmt)
        claimed = updated.scalar_one_or_none()
        if claimed is None:
            return None
        return self._to_record(claimed)

    async def mark_completed(
        self,
        run_id: str,
        *,
        result: dict[str, Any],
    ) -> OptimizationRunRecord | None:
        trials = result.get("trials") or []
        best_score = float(trials[0].get("score", 0)) if trials else None
        now = datetime.now(UTC)
        stmt = (
            update(OptimizationRunRow)
            .where(OptimizationRunRow.id == run_id, OptimizationRunRow.status == "processing")
            .values(
                status="completed",
                result=result,
                error=None,
                engine=str(result.get("engine")),
                best_score=Decimal(str(best_score)) if best_score is not None else None,
                trial_count=len(trials),
                bar_count=int(result.get("barCount") or 0),
                updated_at=now,
                completed_at=now,
            )
            .returning(OptimizationRunRow)
        )
        updated = await self._session.execute(stmt)
        row = updated.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def mark_failed(self, run_id: str, *, error: str) -> OptimizationRunRecord | None:
        now = datetime.now(UTC)
        stmt = (
            update(OptimizationRunRow)
            .where(OptimizationRunRow.id == run_id, OptimizationRunRow.status == "processing")
            .values(status="failed", error=error, updated_at=now, completed_at=now)
            .returning(OptimizationRunRow)
        )
        updated = await self._session.execute(stmt)
        row = updated.scalar_one_or_none()
        return self._to_record(row) if row else None

    async def update_progress(
        self,
        run_id: str,
        *,
        trial_count: int,
        best_score: float | None = None,
    ) -> None:
        """Mid-run progress visible to GET /optimize/runs/{id} pollers."""
        now = datetime.now(UTC)
        values: dict[str, Any] = {
            "trial_count": int(trial_count),
            "updated_at": now,
        }
        if best_score is not None:
            values["best_score"] = Decimal(str(best_score))
        stmt = (
            update(OptimizationRunRow)
            .where(OptimizationRunRow.id == run_id, OptimizationRunRow.status == "processing")
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.commit()

    def _to_record(self, row: OptimizationRunRow) -> OptimizationRunRecord:
        return OptimizationRunRecord(
            id=row.id,
            instrument_id=row.instrument_id,
            symbol=row.symbol,
            status=row.status,  # type: ignore[arg-type]
            payload=dict(row.payload),
            result=dict(row.result) if row.result is not None else None,
            error=row.error,
            engine=row.engine,
            best_score=float(row.best_score) if row.best_score is not None else None,
            trial_count=row.trial_count,
            bar_count=row.bar_count,
            created_at=row.created_at.isoformat(),
            updated_at=row.updated_at.isoformat(),
            completed_at=row.completed_at.isoformat() if row.completed_at else None,
        )
