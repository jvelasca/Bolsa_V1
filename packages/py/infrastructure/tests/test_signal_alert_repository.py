from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    filter_signal_events_by_kinds,
    should_emit_for_bar,
)


class _FakeEvent:
    def __init__(self, kind: str) -> None:
        self.kind = kind


def test_should_emit_for_bar_dedupes_same_bar() -> None:
    assert should_emit_for_bar(None, "2024-01-10") is True
    assert should_emit_for_bar("2024-01-10", "2024-01-10") is False
    assert should_emit_for_bar("2024-01-10", "2024-01-11") is True


def test_filter_signal_events_by_kinds() -> None:
    events = [_FakeEvent("entry_long"), _FakeEvent("watch"), _FakeEvent("exit")]
    filtered = filter_signal_events_by_kinds(events, ["entry_long", "exit"])
    assert [event.kind for event in filtered] == ["entry_long", "exit"]
