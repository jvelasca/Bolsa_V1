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
    _activity_of,
    crash_restart_readopts,
    next_tick_input,
)


def _run(coro):
    return asyncio.run(coro)


def _tick(
    *,
    seq: int,
    proposals: int = 2,
    engine_id: str = "eng-a",
    activity: str | None = None,
) -> AutoEngineTickInput:
    return AutoEngineTickInput(
        engine_id=engine_id,
        venue="simulated",
        state="RUNNING",
        seq=seq,
        proposals=proposals,
        vetoes=0,
        pending_plans=1,
        last_reason=("auto_simulated_only", "ok"),
        activity=activity,
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


def test_activity_round_trips_and_defaults_to_none() -> None:
    store = InMemoryAutoEngineStore()
    _run(store.record_tick(_tick(seq=1, activity="ANALYZING")))
    snap = _run(store.read("eng-a"))
    assert snap is not None
    assert snap.activity == "ANALYZING"
    # Un tick sin actividad queda None (la UI lo declara «Sin dato todavía»).
    _run(store.record_tick(_tick(seq=2, activity=None)))
    snap2 = _run(store.read("eng-a"))
    assert snap2 is not None
    assert snap2.activity is None


def test_activity_of_fails_closed_and_keeps_no_activity() -> None:
    """La fase operacional solo admite el conjunto cerrado; lo demás es None."""
    assert _activity_of("ANALYZING") == "ANALYZING"
    assert _activity_of("no_activity") == "NO_ACTIVITY"  # normaliza a mayúsculas.
    assert _activity_of("NO_ACTIVITY") == "NO_ACTIVITY"  # hecho válido, distinto de None.
    assert _activity_of(None) is None
    assert _activity_of("") is None
    assert _activity_of("SLEEPING") is None  # token fuera del conjunto cerrado.
