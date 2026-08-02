import pytest
from bolsa_domain.entities.platform_event import PlatformEventRecord

from bolsa_application.events.platform_event_bus import PlatformEventBus


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
            created_at="2026-07-12T10:00:00+00:00",
        )
        self.events.append(record)
        return record

    async def list_events(
        self,
        *,
        limit: int = 50,
        event_type: str | None = None,
        correlation_id: str | None = None,
    ) -> list[PlatformEventRecord]:
        items = self.events
        if event_type:
            items = [item for item in items if item.type == event_type]
        if correlation_id:
            items = [item for item in items if item.correlation_id == correlation_id]
        return list(reversed(items[-limit:]))


class RecordingHandler:
    def __init__(self) -> None:
        self.handled: list[PlatformEventRecord] = []

    async def handle(self, event: PlatformEventRecord) -> None:
        self.handled.append(event)


@pytest.mark.asyncio
async def test_platform_event_bus_persists_and_dispatches() -> None:
    repo = InMemoryPlatformEventRepository()
    handler = RecordingHandler()
    bus = PlatformEventBus(repo, handlers=[handler])

    event = await bus.publish(
        "scan.completed",
        {"hitCount": 2, "scannedCount": 10},
        correlation_id="scan-1",
    )

    assert event.type == "scan.completed"
    assert len(repo.events) == 1
    assert handler.handled[0].id == event.id

    listed = await repo.list_events(event_type="scan.completed")
    assert len(listed) == 1
    assert listed[0].payload["hitCount"] == 2
