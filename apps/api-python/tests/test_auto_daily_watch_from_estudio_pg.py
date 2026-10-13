"""Verificación EJECUTABLE (PG real) — el watch diario AUTO deriva del universo ESTUDIO.

CERTIFICA (V2.88.123, cierre del hallazgo ``S2`` declarado en ``v2.88.122``) que, con el
flag ``AUTO_ENGINE_SIMULATED_WATCH_FROM_ESTUDIO`` ON, la lane de **operación diaria**
deriva su watch del universo **canónico** ESTUDIO sobre PostgreSQL real —el MISMO resolver
que el orquestador, vía ``SessionScopedEstudioList`` → ``resolve_estudio_universe``—:

1. Refrescar con el universo sembrado hace que ``_watch_symbols()`` sea el lote de ESTUDIO.
2. Un valor **AÑADIDO** entra en el watch tras refrescar; uno **RETIRADO** sale.
3. ESTUDIO **vacío** ⇒ watch vacío (fail-closed): la allowlist CSV **NUNCA** lo sustituye.
4. El CSV pasa a **allowlist que intersecta** (sin intersección ⇒ watch vacío).
5. El refresco se dispara dentro de ``auto_sim_loop`` **antes** de ``run_tick`` (el turno
   ve el universo ESTUDIO vigente).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_DAILY_WATCH_ESTUDIO_PG_REQUIRED=1`` (job ``lifecycle-pg``) un skip silencioso es un
FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from bolsa_api.background import auto_simulation_worker as sim
from bolsa_api.background import paper_auto_engine_worker as worker
from bolsa_api.background.estudio_watch import SessionScopedEstudioList
from tests._estudio_pg_helpers import (
    add_to_estudio,
    cleanup_instrument,
    make_pg_session_factory,
    require_or_skip,
    restore_estudio,
    seed_instrument_with_trend,
    set_estudio,
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

#: Gate propio (fail-if-skipped) del job ``lifecycle-pg``.
_REQUIRED_ENV = "AUTO_DAILY_WATCH_ESTUDIO_PG_REQUIRED"

_SIM_FROM_ESTUDIO = worker._ENV_SIM_WATCH_FROM_ESTUDIO
_DRY_FROM_ESTUDIO = worker._ENV_WATCH_FROM_ESTUDIO
_SIM_WATCH = "AUTO_ENGINE_SIMULATED_WATCH"
_N_INSTRUMENTS = 3


@pytest_asyncio.fixture
async def estudio_pg_factory() -> AsyncIterator[Any]:
    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="watch diario ESTUDIO")
        raise
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (_SIM_WATCH, _SIM_FROM_ESTUDIO, _DRY_FROM_ESTUDIO):
        monkeypatch.delenv(name, raising=False)
    worker.reset_watch_memory_for_tests()
    yield
    worker.reset_watch_memory_for_tests()


@pytest_asyncio.fixture
async def seeded_estudio(estudio_pg_factory: Any) -> AsyncIterator[list[str]]:
    """Siembra 3 instrumentos con tendencia y los AÑADE a ESTUDIO (no destructivo)."""
    suffix = uuid.uuid4().hex[:8]
    instruments = [f"inst-estco-{suffix}-{index}" for index in range(_N_INSTRUMENTS)]
    for index, instrument_id in enumerate(instruments):
        await seed_instrument_with_trend(
            estudio_pg_factory,
            instrument_id=instrument_id,
            symbol=f"DW{suffix[:3].upper()}{index}",
        )
    originals = await add_to_estudio(estudio_pg_factory, instruments)
    try:
        yield instruments
    finally:
        for instrument_id in instruments:
            await cleanup_instrument(estudio_pg_factory, instrument_id)
        await restore_estudio(estudio_pg_factory, originals)


def _port(factory: Any) -> SessionScopedEstudioList:
    return SessionScopedEstudioList(factory)


@pytest.mark.asyncio
async def test_daily_watch_derives_from_estudio_pg(
    estudio_pg_factory: Any,
    seeded_estudio: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El watch diario es el universo ESTUDIO (no el CSV) tras el refresco por tick."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    await worker.refresh_watch_from_estudio(_port(estudio_pg_factory))
    watch = worker._watch_symbols()
    assert set(seeded_estudio) <= set(watch), (
        f"el watch diario debe derivar de ESTUDIO; watch={watch}"
    )


@pytest.mark.asyncio
async def test_added_and_removed_values_follow_estudio_pg(
    estudio_pg_factory: Any,
    seeded_estudio: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un valor RETIRADO sale del watch; uno AÑADIDO entra, tras refrescar."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    port = _port(estudio_pg_factory)

    # RETIRAR el último valor de ESTUDIO ⇒ desaparece del watch.
    await set_estudio(estudio_pg_factory, seeded_estudio[:2])
    await worker.refresh_watch_from_estudio(port)
    watch = worker._watch_symbols()
    assert set(seeded_estudio[:2]) <= set(watch)
    assert seeded_estudio[2] not in watch, "un valor retirado de ESTUDIO debe salir del watch"

    # AÑADIRLO de vuelta ⇒ entra tras el refresco.
    await set_estudio(estudio_pg_factory, seeded_estudio)
    await worker.refresh_watch_from_estudio(port)
    assert set(seeded_estudio) <= set(worker._watch_symbols())


@pytest.mark.asyncio
async def test_empty_estudio_fails_closed_even_with_csv_pg(
    estudio_pg_factory: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ESTUDIO vacío ⇒ watch vacío: la allowlist CSV NUNCA sustituye al universo."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    monkeypatch.setenv(_SIM_WATCH, "AAA,IBEX")
    originals = await set_estudio(estudio_pg_factory, [])
    try:
        await worker.refresh_watch_from_estudio(_port(estudio_pg_factory))
        assert worker._watch_symbols() == []
    finally:
        await restore_estudio(estudio_pg_factory, originals)


@pytest.mark.asyncio
async def test_csv_allowlist_intersects_estudio_pg(
    estudio_pg_factory: Any,
    seeded_estudio: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El CSV pasa a allowlist que intersecta; sin intersección ⇒ watch vacío."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    port = _port(estudio_pg_factory)

    monkeypatch.setenv(_SIM_WATCH, f"{seeded_estudio[1]},ZZZ-NOT-IN-ESTUDIO")
    await worker.refresh_watch_from_estudio(port)
    assert worker._watch_symbols() == [seeded_estudio[1]]

    monkeypatch.setenv(_SIM_WATCH, "ZZZ-NOT-IN-ESTUDIO")
    await worker.refresh_watch_from_estudio(port)
    assert worker._watch_symbols() == []


@pytest.mark.asyncio
async def test_loop_refreshes_watch_before_tick_pg(
    estudio_pg_factory: Any,
    seeded_estudio: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``auto_sim_loop`` refresca el watch (resolver REAL) ANTES de ``run_tick``."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    monkeypatch.setenv(sim.AUTO_SIM_WORKER_ENABLED, "1")
    port = _port(estudio_pg_factory)
    seen: list[list[str]] = []

    class _Runtime:
        async def run_tick(self) -> None:
            seen.append(list(worker._watch_symbols()))

    async def _watch_refresher() -> None:
        await worker.refresh_watch_from_estudio(port)

    task = asyncio.create_task(
        sim.auto_sim_loop(
            _Runtime(),
            interval_seconds=0.05,
            watch_refresher=_watch_refresher,
        )
    )
    try:
        for _ in range(200):
            await asyncio.sleep(0.05)
            if seen:
                break
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert seen, "el loop debe haber ejecutado al menos un turno"
    assert set(seeded_estudio) <= set(seen[0]), (
        f"el turno debe ver el universo ESTUDIO vigente; seen={seen[0]}"
    )
