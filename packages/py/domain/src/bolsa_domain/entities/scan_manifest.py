from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DataSnapshotRecord:
    id: str
    instrument_id: str
    timeframe: str
    data_version: str
    bar_count: int
    from_ts: str
    to_ts: str
    source: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ScanManifestRecord:
    id: str
    scan_job_id: str | None
    tracker_definition_id: str | None
    strategy_definition_id: str | None
    manifest: dict[str, Any]
    created_at: str
