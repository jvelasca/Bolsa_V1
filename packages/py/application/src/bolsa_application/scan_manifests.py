from typing import Any

from bolsa_analytics.research.scan_manifest import build_scan_manifest
from bolsa_domain.repositories.scan_manifest_repository import (
    DataSnapshotRepository,
    ScanManifestRepository,
)


class PersistScanManifest:
    def __init__(
        self,
        snapshot_repo: DataSnapshotRepository,
        manifest_repo: ScanManifestRepository,
    ) -> None:
        self._snapshots = snapshot_repo
        self._manifests = manifest_repo

    async def execute(
        self,
        *,
        scan_id: str,
        result: dict[str, Any],
        payload: dict[str, Any],
        scan_job_id: str | None = None,
        cache_stats: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        instrument_snapshots = list(result.get("instrumentSnapshots") or [])
        if not instrument_snapshots:
            return None

        strategy_definition_id = result.get("strategyDefinitionId") or payload.get("strategyDefinitionId")
        if not strategy_definition_id:
            preset = payload.get("presetKey")
            if preset:
                strategy_definition_id = f"preset:{preset}"
            else:
                return None

        strategy_version = int(payload.get("strategyVersion") or 1)
        if payload.get("definition") and isinstance(payload["definition"], dict):
            strategy_version = int(payload["definition"].get("version") or strategy_version)

        await self._snapshots.upsert_many(instrument_snapshots)

        universe = payload.get("universe") or {}
        if payload.get("jobKind") == "parent":
            scan_request = payload.get("scanRequest") or {}
            universe = scan_request.get("universe") or universe
            strategy_version = int(
                scan_request.get("strategyVersion")
                or (scan_request.get("definition") or {}).get("version")
                or strategy_version,
            )

        manifest = build_scan_manifest(
            scan_id=scan_id,
            strategy_definition_id=str(strategy_definition_id),
            strategy_version=strategy_version,
            timeframe=str(result.get("timeframe") or payload.get("timeframe") or "1d"),
            universe=universe,
            scanned_count=int(result.get("scannedCount") or 0),
            hit_count=int(result.get("hitCount") or 0),
            instrument_snapshots=instrument_snapshots,
            tracker_definition_id=payload.get("trackerDefinitionId"),
            cache_stats=cache_stats,
            scan_mode=result.get("scanMode"),
            scorer_version=result.get("scorerVersion"),
            scorer_id=result.get("scorerId"),
            gate_rule_hash=result.get("gateRuleHash"),
            fundamentals_version=result.get("fundamentalsVersion"),
        )

        record = await self._manifests.create_manifest(
            scan_id=scan_id,
            manifest=manifest,
            strategy_definition_id=strategy_definition_id
            if not str(strategy_definition_id).startswith("preset:")
            else None,
            scan_job_id=scan_job_id,
            tracker_definition_id=payload.get("trackerDefinitionId"),
        )
        return record.manifest


class GetScanManifest:
    def __init__(self, manifest_repo: ScanManifestRepository) -> None:
        self._manifests = manifest_repo

    async def execute(self, scan_id: str) -> dict[str, Any] | None:
        record = await self._manifests.get_by_scan_id(scan_id)
        if record is None:
            return None
        return record.manifest
