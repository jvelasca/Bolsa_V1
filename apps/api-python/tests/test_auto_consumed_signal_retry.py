"""P5 — la marca durable de señal consumida que falla se reintenta (no se pierde en silencio)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker


class _FlakyStore:
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.marked: list[str] = []

    async def mark(self, account_id, engine_id, signal_id, *, instrument_id, bar_timestamp):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("db down")
        self.marked.append(signal_id)

    async def list_bar(self, account_id, engine_id, bar_start):
        return list(self.marked)


def _worker(store: _FlakyStore) -> AutoSimulationWorker:
    w = AutoSimulationWorker(
        clock=lambda: datetime(2026, 9, 15, 9, 0, tzinfo=UTC),
        account_id="acc-p5",
        consumed_signal_store=store,
    )
    w._v2_tick_signals = {"AAA": "sig-1"}
    w._v2_current_bar_start = lambda: "2026-09-15T00:00:00+00:00"  # type: ignore[method-assign]
    return w


@pytest.mark.asyncio
async def test_failed_mark_is_retried_next_tick() -> None:
    store = _FlakyStore(fail_times=1)
    w = _worker(store)
    await w._v2_mark_signal_consumed("AAA")
    assert store.marked == []
    assert "sig-1" in w._v2_consumed_unpersisted
    await w._v2_load_consumed_signals()
    assert store.marked == ["sig-1"]
    assert w._v2_consumed_unpersisted == {}


@pytest.mark.asyncio
async def test_successful_mark_leaves_nothing_pending() -> None:
    store = _FlakyStore(fail_times=0)
    w = _worker(store)
    await w._v2_mark_signal_consumed("AAA")
    assert store.marked == ["sig-1"]
    assert w._v2_consumed_unpersisted == {}
