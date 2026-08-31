"""Tests A2/A3 — idempotency key + runtime kill switch memory."""

from __future__ import annotations

import pytest

from bolsa_application.auto_execute_idempotency import (
    as_of_from_iso,
    make_auto_execute_idempotency_key,
    make_position_event_idempotency_key,
)
from bolsa_application.risk_runtime import (
    claim_auto_execute_idempotency,
    clear_idempotency_memory_for_tests,
    effective_kill_switch,
    get_runtime_kill_switch_memory,
    set_runtime_kill_switch_memory,
)


def test_idempotency_key_stable() -> None:
    a = make_auto_execute_idempotency_key("inst-1", "2026-08-04", "pol-1", "entry_long")
    b = make_auto_execute_idempotency_key("inst-1", "2026-08-04", "pol-1", "entry_long")
    assert a == b
    assert a == "inst-1|2026-08-04|pol-1|entry_long"


def test_as_of_from_iso() -> None:
    assert as_of_from_iso("2026-08-04T12:00:00Z") == "2026-08-04"


def test_position_event_key_distinguishes_t1_and_stop() -> None:
    t1 = make_position_event_idempotency_key(
        position_id="pos-1",
        event_type="T1",
        event_as_of="2026-08-31T16:00:00Z",
        action="reduce",
    )
    stop = make_position_event_idempotency_key(
        position_id="pos-1",
        event_type="STOP",
        event_as_of="2026-08-31T16:00:00Z",
        action="exit",
    )
    assert t1 != stop
    assert t1 == make_position_event_idempotency_key(
        position_id="pos-1",
        event_type="T1",
        event_as_of="2026-08-31",
        action="reduce",
    )


@pytest.mark.asyncio
async def test_claim_idempotency_memory() -> None:
    clear_idempotency_memory_for_tests()
    key = "test|2026-08-04|p|entry_long"
    assert await claim_auto_execute_idempotency(key) is True
    assert await claim_auto_execute_idempotency(key) is False
    clear_idempotency_memory_for_tests()


@pytest.mark.asyncio
async def test_runtime_kill_switch_memory() -> None:
    set_runtime_kill_switch_memory(False)
    assert get_runtime_kill_switch_memory() is False
    set_runtime_kill_switch_memory(True)
    assert await effective_kill_switch() is True
    set_runtime_kill_switch_memory(False)
