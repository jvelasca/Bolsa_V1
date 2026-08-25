from typing import Any
from unittest.mock import MagicMock

import pytest

from bolsa_application.context.principal import (
    get_current_principal,
    reset_current_principal,
    set_current_principal,
)
from bolsa_application.events.platform_event_bus import PlatformEventBus
from bolsa_application.scan_chunking import JOB_KIND_CHUNK
from bolsa_application.scan_jobs import EnqueueScanJob, ProcessScanJob
from bolsa_application.scans import ScanRunResult
from bolsa_domain.entities.platform_event import PlatformEventRecord
from bolsa_domain.platform_kernel import MAX_SCAN_INSTRUMENTS_CHUNK
from bolsa_infrastructure.database.repositories.scan_job_repository import ScanJobRecord


class InMemoryPlatformEventRepository:
    def __init__(self) -> None:
        self.events: list[PlatformEventRecord] = []

    async def append(
        self,
        *,
        event_type: str,
        payload: dict,
        correlation_id: str | None = None,
        user_id: str | None = None,
    ) -> PlatformEventRecord:
        record = PlatformEventRecord(
            id=f"evt-{len(self.events) + 1}",
            type=event_type,
            payload=payload,
            correlation_id=correlation_id,
            user_id=user_id,
            created_at="2026-08-22T12:00:00+00:00",
        )
        self.events.append(record)
        return record

    async def list_events(self, **kwargs: Any) -> list[PlatformEventRecord]:
        return list(self.events)


class FakeScanJobRepo:
    def __init__(self) -> None:
        self.created: list[ScanJobRecord] = []
        self.jobs: dict[str, ScanJobRecord] = {}
        self._n = 0

    def _record(
        self,
        payload: dict[str, Any],
        *,
        job_id: str | None = None,
        status: str = "pending",
        tracker_definition_id: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ScanJobRecord:
        self._n += 1
        rec = ScanJobRecord(
            id=job_id or f"job-{self._n}",
            status=status,  # type: ignore[arg-type]
            payload=payload,
            result=result,
            error=error,
            cache_hits=None,
            cache_misses=None,
            tracker_definition_id=tracker_definition_id,
            created_at="2026-08-22T12:00:00+00:00",
            updated_at="2026-08-22T12:00:00+00:00",
            completed_at=None,
        )
        self.jobs[rec.id] = rec
        return rec

    async def create(
        self,
        payload: dict[str, Any],
        *,
        status: str = "pending",
        tracker_definition_id: str | None = None,
    ) -> ScanJobRecord:
        rec = self._record(
            payload,
            status=status,
            tracker_definition_id=tracker_definition_id,
        )
        self.created.append(rec)
        return rec

    async def update_payload(self, job_id: str, payload: dict[str, Any]) -> ScanJobRecord | None:
        old = self.jobs[job_id]
        rec = self._record(
            payload,
            job_id=old.id,
            status=old.status,
            tracker_definition_id=old.tracker_definition_id,
        )
        return rec

    async def claim_by_id(self, job_id: str) -> ScanJobRecord | None:
        return self.jobs.get(job_id)

    async def mark_completed(
        self,
        job_id: str,
        *,
        result: dict[str, Any],
        cache_hits: int,
        cache_misses: int,
    ) -> None:
        old = self.jobs[job_id]
        self.jobs[job_id] = ScanJobRecord(
            id=old.id,
            status="completed",
            payload=old.payload,
            result=result,
            error=None,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            tracker_definition_id=old.tracker_definition_id,
            created_at=old.created_at,
            updated_at=old.updated_at,
            completed_at=old.updated_at,
        )

    async def mark_failed(self, job_id: str, *, error: str) -> None:
        old = self.jobs[job_id]
        self.jobs[job_id] = ScanJobRecord(
            id=old.id,
            status="failed",
            payload=old.payload,
            result=old.result,
            error=error,
            cache_hits=old.cache_hits,
            cache_misses=old.cache_misses,
            tracker_definition_id=old.tracker_definition_id,
            created_at=old.created_at,
            updated_at=old.updated_at,
            completed_at=old.completed_at,
        )


class DummyFeatureCache:
    hits = 0
    misses = 0


class FakeRunScan:
    def __init__(self, event_bus: PlatformEventBus | None = None, *, fail: bool = False) -> None:
        self.event_bus = event_bus
        self.fail = fail
        self.principal_seen: str | None = None

    async def execute(self, **kwargs: Any) -> ScanRunResult:
        self.principal_seen = get_current_principal()
        if self.fail:
            raise RuntimeError("scan failed")
        result = ScanRunResult(
            scan_id="scan-1",
            scanned_count=0,
            hit_count=0,
            hits=[],
            skipped=[],
            strategy_definition_id=None,
            list_id=None,
            timeframe="1d",
            instrument_snapshots=[],
            strategy_version=1,
        )
        if self.event_bus is not None:
            await self.event_bus.publish(
                "scan.completed",
                {"hitCount": 0},
                correlation_id=result.scan_id,
            )
        return result


def _enqueue() -> tuple[EnqueueScanJob, FakeScanJobRepo]:
    repo = FakeScanJobRepo()
    return EnqueueScanJob(job_repo=repo, list_repository=MagicMock()), repo


@pytest.mark.asyncio
async def test_enqueue_stamps_owner_user_id_from_principal() -> None:
    use_case, repo = _enqueue()
    token = set_current_principal("user-a")
    try:
        job = await use_case.execute(
            {"universe": {"instrumentIds": ["inst-1"]}, "timeframe": "1d"},
        )
    finally:
        reset_current_principal(token)

    assert job.payload["ownerUserId"] == "user-a"
    assert repo.created[0].payload["ownerUserId"] == "user-a"


@pytest.mark.asyncio
async def test_enqueue_does_not_overwrite_caller_owner_user_id() -> None:
    use_case, _repo = _enqueue()
    token = set_current_principal("user-a")
    try:
        job = await use_case.execute(
            {
                "universe": {"instrumentIds": ["inst-1"]},
                "timeframe": "1d",
                "ownerUserId": "user-caller",
            },
        )
    finally:
        reset_current_principal(token)

    assert job.payload["ownerUserId"] == "user-caller"


@pytest.mark.asyncio
async def test_enqueue_without_principal_leaves_owner_absent() -> None:
    use_case, _repo = _enqueue()
    assert get_current_principal() is None
    job = await use_case.execute(
        {"universe": {"instrumentIds": ["inst-1"]}, "timeframe": "1d"},
    )
    assert "ownerUserId" not in job.payload


@pytest.mark.asyncio
async def test_enqueue_copies_owner_user_id_to_child_chunks() -> None:
    use_case, repo = _enqueue()
    ids = [f"inst-{i}" for i in range(MAX_SCAN_INSTRUMENTS_CHUNK + 1)]
    token = set_current_principal("user-a")
    try:
        await use_case.execute({"universe": {"instrumentIds": ids}, "timeframe": "1d"})
    finally:
        reset_current_principal(token)

    children = [job for job in repo.created if job.payload.get("jobKind") == JOB_KIND_CHUNK]
    assert len(children) == 2
    assert all(child.payload["ownerUserId"] == "user-a" for child in children)
    parent = next(job for job in repo.created if job.payload.get("jobKind") == "parent")
    assert parent.payload["scanRequest"]["ownerUserId"] == "user-a"


@pytest.mark.asyncio
async def test_process_scan_job_stamps_scan_completed_user_id_from_payload() -> None:
    repo = FakeScanJobRepo()
    job = await repo.create(
        {
            "universe": {"instrumentIds": ["inst-1"]},
            "timeframe": "1d",
            "ownerUserId": "user-a",
        },
    )
    events = InMemoryPlatformEventRepository()
    run_scan = FakeRunScan(event_bus=PlatformEventBus(events))
    processor = ProcessScanJob(job_repo=repo, run_scan=run_scan, feature_cache=DummyFeatureCache())

    assert get_current_principal() is None
    result = await processor.execute(job.id)

    assert result.status == "completed"
    assert run_scan.principal_seen == "user-a"
    assert events.events[0].user_id == "user-a"
    assert events.events[0].type == "scan.completed"
    assert get_current_principal() is None


@pytest.mark.asyncio
async def test_process_scan_job_resets_principal_on_failure() -> None:
    repo = FakeScanJobRepo()
    job = await repo.create(
        {
            "universe": {"instrumentIds": ["inst-1"]},
            "timeframe": "1d",
            "ownerUserId": "user-a",
        },
    )
    run_scan = FakeRunScan(fail=True)
    processor = ProcessScanJob(job_repo=repo, run_scan=run_scan, feature_cache=DummyFeatureCache())

    result = await processor.execute(job.id)

    assert result.status == "failed"
    assert run_scan.principal_seen == "user-a"
    assert get_current_principal() is None


@pytest.mark.asyncio
async def test_process_scan_job_without_owner_leaves_event_user_id_null() -> None:
    repo = FakeScanJobRepo()
    job = await repo.create({"universe": {"instrumentIds": ["inst-1"]}, "timeframe": "1d"})
    events = InMemoryPlatformEventRepository()
    run_scan = FakeRunScan(event_bus=PlatformEventBus(events))
    processor = ProcessScanJob(job_repo=repo, run_scan=run_scan, feature_cache=DummyFeatureCache())

    await processor.execute(job.id)

    assert run_scan.principal_seen is None
    assert events.events[0].user_id is None
