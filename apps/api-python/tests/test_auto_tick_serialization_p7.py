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


@pytest.mark.asyncio
async def test_the_loop_persists_through_the_store_the_engine_was_built_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """M4: el motor se queda con SU store y el bucle lo usa (antes leía un atributo inexistente).

    Sin esta referencia el bucle lanzaba ``AttributeError`` en cada tick, lo registraba como
    "tick failed" y dejaba el motor en ``DEGRADED`` sin haber ejecutado ni una pasada: el
    modo durable que el starter ofrece con ``store=`` no llegaba a correr.
    """
    import bolsa_api.background.paper_auto_engine_worker as worker_module

    store = _Store()
    engine = PaperAutoEngine(store=store, engine_id="e-p7-loop")  # type: ignore[arg-type]
    assert engine.store is store

    used: list[object] = []

    async def _fake_tick(_engine: object, _store: object) -> None:
        used.append(_store)

    monkeypatch.setattr(worker_module, "durable_tick", _fake_tick)
    monkeypatch.setattr(worker_module, "_enabled", lambda: True)
    task = asyncio.create_task(
        worker_module.paper_auto_engine_loop(engine, interval_seconds=0.01)
    )
    try:
        for _ in range(100):
            if used:
                break
            await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert used == [store], "el tick durable tiene que recibir el store del motor"
    assert engine._state != "DEGRADED"  # noqa: SLF001 — el fallo dejaba el motor degradado.
