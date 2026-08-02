from datetime import UTC, datetime
from typing import Any

from bolsa_domain.entities.scan_manifest import DataSnapshotRecord, ScanManifestRecord
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import DataSnapshotRow, ScanManifestRow


class SqlAlchemyDataSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: DataSnapshotRow) -> DataSnapshotRecord:
        return DataSnapshotRecord(
            id=row.id,
            instrument_id=row.instrument_id,
            timeframe=row.timeframe,
            data_version=row.data_version,
            bar_count=row.bar_count,
            from_ts=row.from_ts,
            to_ts=row.to_ts,
            source=row.source,
            created_at=row.created_at.isoformat(),
        )

    async def upsert_snapshot(
        self,
        *,
        snapshot_id: str,
        instrument_id: str,
        timeframe: str,
        data_version: str,
        bar_count: int,
        from_ts: str,
        to_ts: str,
        source: str = "postgres",
    ) -> DataSnapshotRecord:
        now = datetime.now(UTC)
        stmt = (
            insert(DataSnapshotRow)
            .values(
                id=snapshot_id,
                instrument_id=instrument_id,
                timeframe=timeframe,
                data_version=data_version,
                bar_count=bar_count,
                from_ts=from_ts,
                to_ts=to_ts,
                source=source,
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(DataSnapshotRow)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            existing = await self._session.get(DataSnapshotRow, snapshot_id)
            if existing is None:
                raise RuntimeError(f"Failed to upsert data snapshot {snapshot_id}")
            return self._map(existing)
        return self._map(row)

    async def upsert_many(self, snapshots: list[dict[str, Any]]) -> None:
        for meta in snapshots:
            await self.upsert_snapshot(
                snapshot_id=str(meta["id"]),
                instrument_id=str(meta["instrumentId"]),
                timeframe=str(meta["timeframe"]),
                data_version=str(meta["dataVersion"]),
                bar_count=int(meta["barCount"]),
                from_ts=str(meta["from"]),
                to_ts=str(meta["to"]),
                source=str(meta.get("source") or "postgres"),
            )


class SqlAlchemyScanManifestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _map(self, row: ScanManifestRow) -> ScanManifestRecord:
        return ScanManifestRecord(
            id=row.id,
            scan_job_id=row.scan_job_id,
            tracker_definition_id=row.tracker_definition_id,
            strategy_definition_id=row.strategy_definition_id,
            manifest=dict(row.manifest),
            created_at=row.created_at.isoformat(),
        )

    async def get_by_scan_id(self, scan_id: str) -> ScanManifestRecord | None:
        row = await self._session.get(ScanManifestRow, scan_id)
        if row is None:
            return None
        return self._map(row)

    async def create_manifest(
        self,
        *,
        scan_id: str,
        manifest: dict[str, Any],
        strategy_definition_id: str | None = None,
        scan_job_id: str | None = None,
        tracker_definition_id: str | None = None,
    ) -> ScanManifestRecord:
        existing = await self._session.get(ScanManifestRow, scan_id)
        if existing is not None:
            return self._map(existing)

        now = datetime.now(UTC)
        row = ScanManifestRow(
            id=scan_id,
            scan_job_id=scan_job_id,
            tracker_definition_id=tracker_definition_id,
            strategy_definition_id=strategy_definition_id,
            manifest=manifest,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return self._map(row)

    async def list_by_tracker(self, tracker_definition_id: str, *, limit: int = 20) -> list[ScanManifestRecord]:
        stmt = (
            select(ScanManifestRow)
            .where(ScanManifestRow.tracker_definition_id == tracker_definition_id)
            .order_by(ScanManifestRow.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._map(row) for row in result.scalars().all()]
