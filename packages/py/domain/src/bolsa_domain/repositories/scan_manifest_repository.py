from typing import Any, Protocol

from bolsa_domain.entities.scan_manifest import DataSnapshotRecord, ScanManifestRecord


class DataSnapshotRepository(Protocol):
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
    ) -> DataSnapshotRecord: ...

    async def upsert_many(self, snapshots: list[dict[str, Any]]) -> None: ...


class ScanManifestRepository(Protocol):
    async def get_by_scan_id(self, scan_id: str) -> ScanManifestRecord | None: ...

    async def create_manifest(
        self,
        *,
        scan_id: str,
        manifest: dict[str, Any],
        strategy_definition_id: str | None = None,
        scan_job_id: str | None = None,
        tracker_definition_id: str | None = None,
    ) -> ScanManifestRecord: ...
