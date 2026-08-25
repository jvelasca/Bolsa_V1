from typing import Any

import pytest

from bolsa_application.context.principal import (
    get_current_principal,
    reset_current_principal,
    set_current_principal,
)
from bolsa_application.scan_jobs import OWNER_USER_ID_PAYLOAD_KEY
from bolsa_application.trackers import (
    EnqueueTrackerScanJob,
    build_tracker_definition_dict,
    tracker_to_scan_payload,
)
from bolsa_domain.entities.tracker_definition import TrackerDefinitionRecord


def _tracker(*, user_id: str | None) -> TrackerDefinitionRecord:
    return TrackerDefinitionRecord(
        id="tracker-1",
        name="EU Daily",
        definition={
            "universe": {"listId": "list-eu"},
            "barLimit": 300,
            "maxResults": 50,
        },
        strategy_definition_id="strat-1",
        strategy_version=2,
        timeframe="1wk",
        evaluation_mode="bar_close",
        origin="manual",
        enabled=True,
        user_id=user_id,
        created_at="2026-07-11T00:00:00+00:00",
        updated_at="2026-07-11T00:00:00+00:00",
    )


class _FakeTrackerRepo:
    def __init__(self, tracker: TrackerDefinitionRecord) -> None:
        self._tracker = tracker

    async def get_tracker(self, tracker_id: str) -> TrackerDefinitionRecord | None:
        if tracker_id != self._tracker.id:
            return None
        return self._tracker


class _RecordingEnqueueScan:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []
        self.tracker_definition_ids: list[str | None] = []

    async def execute(
        self,
        payload: dict[str, Any],
        *,
        tracker_definition_id: str | None = None,
    ) -> dict[str, Any]:
        self.payloads.append(payload)
        self.tracker_definition_ids.append(tracker_definition_id)
        return payload


def test_tracker_to_scan_payload() -> None:
    record = _tracker(user_id=None)
    payload = tracker_to_scan_payload(record)
    assert payload["trackerDefinitionId"] == "tracker-1"
    assert payload["strategyDefinitionId"] == "strat-1"
    assert payload["universe"] == {"listId": "list-eu"}
    assert payload["timeframe"] == "1wk"
    assert payload["barLimit"] == 300
    assert payload["maxResults"] == 50


def test_build_tracker_definition_dict_roundtrip() -> None:
    definition = build_tracker_definition_dict(
        tracker_id="t-1",
        name="Test",
        strategy_definition_id="s-1",
        strategy_version=None,
        universe={"instrumentIds": ["inst-1"]},
        timeframe="1d",
        bar_limit=500,
        max_results=100,
        evaluation_mode="bar_close",
        rank_by=None,
        default_execution_policy_id=None,
        schedule=None,
        origin="manual",
        source_prompt=None,
        enabled=True,
        created_at="2026-07-11T00:00:00+00:00",
        updated_at="2026-07-11T00:00:00+00:00",
    )
    assert definition["id"] == "t-1"
    assert definition["strategyDefinitionId"] == "s-1"
    assert definition["universe"]["instrumentIds"] == ["inst-1"]


@pytest.mark.asyncio
async def test_enqueue_tracker_scan_stamps_owner_from_tracker_without_principal() -> None:
    assert get_current_principal() is None
    enqueue = _RecordingEnqueueScan()
    use_case = EnqueueTrackerScanJob(_FakeTrackerRepo(_tracker(user_id="user-a")), enqueue)
    await use_case.execute("tracker-1")
    assert enqueue.payloads[0][OWNER_USER_ID_PAYLOAD_KEY] == "user-a"
    assert enqueue.tracker_definition_ids[0] == "tracker-1"


@pytest.mark.asyncio
async def test_enqueue_tracker_scan_leaves_owner_absent_when_tracker_has_no_user() -> None:
    assert get_current_principal() is None
    enqueue = _RecordingEnqueueScan()
    use_case = EnqueueTrackerScanJob(_FakeTrackerRepo(_tracker(user_id=None)), enqueue)
    await use_case.execute("tracker-1")
    assert OWNER_USER_ID_PAYLOAD_KEY not in enqueue.payloads[0]


@pytest.mark.asyncio
async def test_enqueue_tracker_scan_tracker_owner_wins_over_http_principal() -> None:
    enqueue = _RecordingEnqueueScan()
    use_case = EnqueueTrackerScanJob(_FakeTrackerRepo(_tracker(user_id="user-a")), enqueue)
    token = set_current_principal("user-b")
    try:
        await use_case.execute("tracker-1")
    finally:
        reset_current_principal(token)
    assert enqueue.payloads[0][OWNER_USER_ID_PAYLOAD_KEY] == "user-a"
