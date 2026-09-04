"""V2.0.3 — SEMI Confirm protect → TRAIL_APPLIED when stage allows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    InMemoryLifecycleEventStore,
)
from bolsa_application.lifecycle_from_semi_protect import (
    TRAIL_ALLOWED_STAGES,
    maybe_append_lifecycle_semi_protect,
)
from bolsa_domain.lifecycle import LifecycleEventInput


def _at(h: int = 12) -> str:
    return datetime(2026, 9, 4, h, 0, 0, tzinfo=UTC).isoformat().replace(
        "+00:00", "Z"
    )


async def _seed_open_t1(store: InMemoryLifecycleEventStore, pid: str = "pos-1") -> None:
    append = AppendLifecycleEvent(store)
    open_ev = LifecycleEventInput(
        kind="POSITION_OPENED",
        at=_at(9),
        event_id=f"{pid}-open",
        position_id=pid,
        account_id="acc",
        instrument_id="inst",
        quantity=Decimal("10"),
        price=Decimal("100"),
        fill_id=f"{pid}-fill-open",
        fees=Decimal("0"),
        venue="PAPER",
        side="long",
    )
    r1 = await append.execute(open_ev)
    assert r1.ok, r1.error
    t1 = LifecycleEventInput(
        kind="T1_EXECUTED",
        at=_at(10),
        event_id=f"{pid}-t1",
        position_id=pid,
        account_id="acc",
        instrument_id="inst",
        quantity=Decimal("5"),
        price=Decimal("120"),
        fill_id=f"{pid}-fill-t1",
        fees=Decimal("0"),
        venue="PAPER",
        side="long",
    )
    r2 = await append.execute(t1)
    assert r2.ok, r2.error
    assert r2.stage == "t1_executed"


@pytest.mark.asyncio
async def test_semi_protect_post_t1_emits_trail_applied() -> None:
    store = InMemoryLifecycleEventStore()
    await _seed_open_t1(store)
    append = AppendLifecycleEvent(store)

    result = await maybe_append_lifecycle_semi_protect(
        lifecycle_append=append,
        lifecycle_outbox=None,
        account_id="acc",
        instrument_id="inst",
        position_id="pos-1",
        previous_stop=95.0,
        new_stop=100.0,
        event_id="rev-trail-1",
        filled_at=_at(11),
        origin="trail",
    )
    assert result["status"] == "applied"
    assert result["kind"] == "TRAIL_APPLIED"
    assert result["stage"] == "trailing"

    snap_kinds = [e.kind for e in await store.list_by_position("pos-1")]
    assert "TRAIL_APPLIED" in snap_kinds
    assert "T1_EXECUTED" in snap_kinds


@pytest.mark.asyncio
async def test_semi_protect_pre_t1_skips_without_poison() -> None:
    store = InMemoryLifecycleEventStore()
    append = AppendLifecycleEvent(store)
    open_ev = LifecycleEventInput(
        kind="POSITION_OPENED",
        at=_at(9),
        event_id="pos-open-only",
        position_id="pos-open",
        account_id="acc",
        instrument_id="inst",
        quantity=Decimal("10"),
        price=Decimal("100"),
        fill_id="fill-open-only",
        fees=Decimal("0"),
        venue="PAPER",
        side="long",
    )
    assert (await append.execute(open_ev)).ok

    result = await maybe_append_lifecycle_semi_protect(
        lifecycle_append=append,
        lifecycle_outbox=None,
        account_id="acc",
        instrument_id="inst",
        position_id="pos-open",
        previous_stop=95.0,
        new_stop=97.0,
        event_id="rev-pre-t1",
        filled_at=_at(10),
        origin="protect",
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "stage_forbids_trail"
    assert result["stage"] == "open"
    kinds = [e.kind for e in await store.list_by_position("pos-open")]
    assert kinds == ["POSITION_OPENED"]


def test_trail_allowed_stages_match_transitions() -> None:
    assert TRAIL_ALLOWED_STAGES == frozenset(
        {"t1_executed", "trailing", "t2_executed"}
    )
