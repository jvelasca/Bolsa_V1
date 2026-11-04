"""P6 — una transición del INTENT de salida que no se persiste queda pendiente y se reintenta."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker


class _Order:
    exit_order_id = "ex-1"


class _FlakyExitStore:
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.saved: list[object] = []

    async def save(self, order):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("db down")
        self.saved.append(order)

    async def commit(self):
        return None


def _worker(store) -> AutoSimulationWorker:
    return AutoSimulationWorker(
        clock=lambda: datetime(2026, 9, 15, 9, 0, tzinfo=UTC),
        account_id="acc-p6",
        exit_order_store=store,
    )


@pytest.mark.asyncio
async def test_failed_transition_is_kept_and_retried() -> None:
    store = _FlakyExitStore(fail_times=1)
    w = _worker(store)
    order = _Order()
    assert await w._v2_save_exit_order_or_pend(order) is False  # type: ignore[arg-type]
    assert w._v2_exit_unpersisted == {"ex-1": order}
    await w._v2_retry_unpersisted_exit_orders()
    assert store.saved == [order]
    assert w._v2_exit_unpersisted == {}


@pytest.mark.asyncio
async def test_successful_transition_leaves_nothing_pending() -> None:
    w = _worker(_FlakyExitStore(fail_times=0))
    assert await w._v2_save_exit_order_or_pend(_Order()) is True  # type: ignore[arg-type]
    assert w._v2_exit_unpersisted == {}
