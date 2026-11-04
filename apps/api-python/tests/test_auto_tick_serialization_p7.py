"""P7 — un único turno a la vez por runtime/motor AUTO."""

from __future__ import annotations

import asyncio

import pytest

from bolsa_api.background.auto_simulation_worker import AutoSimRuntime
from bolsa_api.background.paper_auto_engine_worker import PaperAutoEngine, durable_tick


@pytest.mark.asyncio
async def test_runtime_skips_overlapping_tick(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = AutoSimRuntime(object(), engine_id="e-p7", account_id="acc-p7")
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def _slow() -> str:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return "done"

    monkeypatch.setattr(runtime, "_run_tick_unlocked", _slow)
    first = asyncio.create_task(runtime.run_tick())
    await started.wait()
    assert await runtime.run_tick() is None
    release.set()
    assert await first == "done"
    assert calls == 1
    release.clear()
    release.set()
    assert await runtime.run_tick() == "done"


class _Store:
    def __init__(self) -> None:
        self.active = 0
        self.peak = 0

    async def read(self, _engine_id: str) -> None:
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return None


@pytest.mark.asyncio
async def test_durable_tick_is_serialized_per_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _Store()
    engine = PaperAutoEngine(engine_id="e-p7-d")

    async def _persist(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(engine, "persist_tick", _persist)
    await asyncio.gather(*(durable_tick(engine, store) for _ in range(4)))  # type: ignore[arg-type]
    assert store.peak == 1
