"""V2.22 / A9 (M4) — Hermetic durable AUTO state store (in-memory, sin PG).

Prueba del espejo durable (auto_engine_state_store) que sustituye la telemetría
en-memoria del AUTO Engine: readopción tras crash (RUNNING + contadores) y
no-doble de tick. Usa solo ``InMemoryAutoEngineStore`` + el driver
``crash_restart_readopts`` (el mismo contrato que el Postgres store real-PG del
repo, probado en apps/api-python/tests con PG).
"""

from __future__ import annotations

import asyncio

from bolsa_application.auto_engine_state_store import (
    AutoEngineTickInput,
    InMemoryAutoEngineStore,
    crash_restart_readopts,
    next_tick_input,
)


def _run(coro):
    return asyncio.run(coro)


def _tick(*, seq: int, proposals: int = 2, engine_id: str = "eng-a") -> AutoEngineTickInput:
    return AutoEngineTickInput(
        engine_id=engine_id,
        venue="simulated",
        state="RUNNING",
        seq=seq,
        proposals=proposals,
        vetoes=0,
        pending_plans=1,
        last_reason=("auto_simulated_only", "ok"),
    )


def test_store_start_empty() -> None:
    store = InMemoryAutoEngineStore()
    assert _run(store.read("eng-a")) is None  # primer arranque: aún sin fila.


def test_record_then_read_readopts_running_and_counters() -> None:
    store = InMemoryAutoEngineStore()
    _run(store.record_tick(_tick(seq=1)))
    snap = _run(store.read("eng-a"))
    assert snap is not None
    assert snap.state == "RUNNING"
    assert snap.ticks == 1
    assert snap.proposals == 2
    assert snap.vetoes == 0
    assert snap.pending_plans == 1


def test_record_same_seq_does_not_double_tick() -> None:
    store = InMemoryAutoEngineStore()
    tick = _tick(seq=1)
    _run(store.record_tick(tick))
    # "Crash/re-registro": reintentar el MISMO seq no dobla el conteo.
    _run(store.record_tick(tick))
    snap = _run(store.read("eng-a"))
    assert snap.ticks == 1
    assert snap.proposals == 2


def test_next_seq_after_readopt_is_monotonic() -> None:
    store = InMemoryAutoEngineStore()
    _run(store.record_tick(_tick(seq=1, proposals=2)))
    prev = _run(store.read("eng-a"))
    nxt = next_tick_input(
        prev,
        venue="simulated",
        state="RUNNING",
        more_proposals=1,
        more_vetoes=0,
        more_pending_plans=0,
        reason=("ok",),
    )
    assert nxt.seq == 2  # siguiente posición tras el tick 1 durable.
    assert nxt.proposals == 3  # acumulado monotónico previo + delta.
    assert nxt.engine_id == "eng-a"


def test_crash_restart_readopts_does_not_double_tick() -> None:
    store = InMemoryAutoEngineStore()
    _run(store.record_tick(_tick(seq=1)))  # worker persistió antes del crash.
    # Crash → el worker reinicia y SOLO readopta (no vuelve a correr el tick).
    snap = _run(crash_restart_readopts(store, engine_id="eng-a"))
    assert snap is not None
    assert snap.state == "RUNNING"
    assert snap.ticks == 1  # NO 2: el reinicio no dobla el tick del crash.
    assert snap.proposals == 2


def test_empty_snapshot_computes_first_seq() -> None:
    nxt = next_tick_input(
        None,
        venue="paper",
        state="RUNNING",
        more_proposals=0,
        more_vetoes=0,
        more_pending_plans=0,
    )
    assert nxt.seq == 1
