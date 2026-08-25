"""Cola de sync: los fallos permanentes (símbolo no-resoluble) no reintentan."""

from __future__ import annotations

import pytest
from bolsa_domain.value_objects.market import SyncResult
from bolsa_infrastructure.database.repositories.sync_scheduler_repository import (
    SyncQueueItemRecord,
    SyncSettingsRecord,
)

from bolsa_application.sync_scheduler import ProcessNextSyncQueueItem


class _FakeSchedulerRepo:
    def __init__(
        self,
        settings: SyncSettingsRecord,
        pending_items: list[SyncQueueItemRecord],
    ) -> None:
        self._settings = settings
        self._pending = list(pending_items)
        self.fail_calls: list[tuple[str, bool]] = []
        self.completed: list[str] = []

    async def get_settings(self) -> SyncSettingsRecord:
        return self._settings

    async def claim_next(self) -> SyncQueueItemRecord | None:
        return self._pending.pop(0) if self._pending else None

    async def fail_item(
        self,
        item_id: str,
        *,
        error: str,
        retry: bool,
        backoff_minutes: int,
        max_retries: int,
    ) -> None:
        self.fail_calls.append((item_id, retry))

    async def complete_item(self, item_id: str) -> None:
        self.completed.append(item_id)


class _StubSync:
    def __init__(self, result: SyncResult | None) -> None:
        self._result = result

    async def execute(self, instrument_id: str) -> SyncResult | None:
        return self._result


def _settings() -> SyncSettingsRecord:
    return SyncSettingsRecord(
        auto_sync_enabled=True,
        scan_interval_minutes=30,
        min_delay_seconds=3,
        post_market_only=False,
        max_retries=5,
        retry_backoff_minutes=45,
        scope="lists",
        updated_at="2026-08-12T00:00:00+00:00",
    )


def _item() -> SyncQueueItemRecord:
    return SyncQueueItemRecord(
        id="queue_item_1",
        instrument_id="7e858cffa2284bf4a0521c74c",
        symbol="BP/",
        status="pending",
        priority=0,
        scheduled_at="2026-08-12T00:00:00+00:00",
        attempts=0,
        last_error=None,
        created_at="2026-08-12T00:00:00+00:00",
        updated_at="2026-08-12T00:00:00+00:00",
    )


def _make_use_case(repo: _FakeSchedulerRepo, result: SyncResult) -> ProcessNextSyncQueueItem:
    return ProcessNextSyncQueueItem(repo, _StubSync(result))  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_permanent_failure_is_flagged_non_retryable() -> None:
    repo = _FakeSchedulerRepo(settings=_settings(), pending_items=[_item()])
    result = await _make_use_case(
        repo,
        SyncResult(
            bars_added=0,
            status="failed",
            error="Yahoo no encontró histórico para este símbolo. Revisa el ticker (ej. AENA.MC).",
            retryable=False,
        ),
    ).execute()

    assert result.status == "failed"
    assert repo.fail_calls == [("queue_item_1", False)]
    assert repo.completed == []


@pytest.mark.asyncio
async def test_transient_failure_is_retryable() -> None:
    repo = _FakeSchedulerRepo(settings=_settings(), pending_items=[_item()])
    result = await _make_use_case(
        repo,
        SyncResult(bars_added=0, status="failed", error="429 Too Many Requests"),
    ).execute()

    assert result.status == "failed"
    assert repo.fail_calls == [("queue_item_1", True)]
    assert repo.completed == []
