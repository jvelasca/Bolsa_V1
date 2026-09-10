"""V2.22 / A9 (M4) — Estado durable AUTO Engine readopción crash/restart en PG real.

Prueba la propiedad P2 del audit sobre el espejo durable del AUTO Engine
(tablas ``auto_engine_runs`` / ``auto_engine_ticks``, Alembic ``027``):

1. un motor corre y persiste un tick (RUNNING + contadores) vía
   ``PostgresAutoEngineStore.record_tick``;
2. "crash": descartamos el engine/sesión en-memoria por completo;
3. "restart": abrimos un store NUEVO (nueva sesión/factory) que relee del mismo
   PG (``crash_restart_readopts`` / ``store.read``) y readopta RUNNING + tick sin
   re-ejecutar el tick del crash (el contador de ticks NO se dobla a 2).

Enfoque "restart the store, read counts" (estilo a7-gate / C3). Corre contra la
BD que da ``DATABASE_URL`` del entorno; requiere que Alembic 027 esté aplicado
(``ensure_migrated`` se invoca aquí para auto-llevar a head 027, igual que la
suite chaos/live_a7). Si PG no está disponible se salta con skip salvo que
``AUTO_M4_PG_REQUIRED=1`` (entonces falla: gate de CI del job dedicado).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_ENV_FILE = "AUTO_M4_PG_REQUIRED"

# V2.23/A9 (Bloque 1, CI GREEN): marker explícito. El job `lifecycle-pg` mezcla este
# archivo con rutas fuera de `apps/api-python` (p.ej. `packages/py/infrastructure/...`),
# con lo que el rootdir cae en la raíz y NO aplica `asyncio_mode=auto` del
# `apps/api-python/pyproject.toml`. Sin este marker, pytest trata el test async como
# función síncrona y falla ("async def functions are not natively supported").
pytestmark = pytest.mark.asyncio


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_ENV_FILE) == "1":
        raise AssertionError(f"AUTO M4 PG requerido pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL/Alembic (M4 AUTO durable) no disponible: {exc}")


@pytest_asyncio.fixture
async def auto_pg_factory() -> tuple[async_sessionmaker[AsyncSession], str]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto head 027 sobre la BD dada.
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    from bolsa_infrastructure.database.session import create_session_factory

    factory = create_session_factory(engine)
    db_name = os.environ.get("DB_NAME") or "bolsa_v1"
    try:
        yield factory, db_name
    finally:
        await engine.dispose()


async def test_crash_restart_readopts_running_without_doubling_tick(
    auto_pg_factory: tuple[async_sessionmaker[AsyncSession], str],
) -> None:
    import uuid

    from sqlalchemy import select, text

    from bolsa_application.auto_engine_state_store import (
        AutoEngineTickInput,
        PostgresAutoEngineStore,
        crash_restart_readopts,
    )
    from bolsa_infrastructure.database.models.tables import AutoEngineRunRow

    factory, _db_name = auto_pg_factory
    engine_id = f"m4-pg-{uuid.uuid4().hex[:10]}"

    # ── "proceso A": motor corre y persiste UN tick (RUNNING + 2 propuestas) ──
    async with factory() as session:
        store_a = PostgresAutoEngineStore(session)
        snap0 = await store_a.read(engine_id)
        assert snap0 is None  # primer arranque de esta engine (DB dedicada).
        tick = AutoEngineTickInput(
            engine_id=engine_id,
            venue="simulated",
            state="RUNNING",
            seq=1,
            proposals=2,
            vetoes=1,
            pending_plans=1,
            last_reason=("auto_simulated_only", "veto_risk"),
        )
        await store_a.record_tick(tick)
        # verify durable row present
        runs = (
            await session.execute(
                select(AutoEngineRunRow).where(AutoEngineRunRow.engine_id == engine_id)
            )
        ).scalar_one_or_none()
        assert runs is not None
        assert runs.state == "RUNNING"
        assert int(runs.proposals) == 2

    # ── crash: descartamos sesión/factory por completo (sin memoria en proceso) ──
    # ── "proceso B": ABRIMOS un store NUEVO que relee del MISMO PG (restart) ──
    async with factory() as session_b:
        store_b = PostgresAutoEngineStore(session_b)  # nueva instancia = restart
        snap = await crash_restart_readopts(store_b, engine_id=engine_id)
        assert snap is not None
        # Readopta RUNNING + contadores del tick que persistió ANTES del crash.
        assert snap.state == "RUNNING"
        assert snap.venue == "simulated"
        assert snap.ticks == 1  # NO 2: reiniciar NO vuelve a correr el tick.
        assert snap.proposals == 2
        assert snap.vetoes == 1
        assert snap.pending_plans == 1

        # Relectura vía SQL puro para contar los ticks matriculados exact-una-vez.
        ticks = await session_b.scalar(
            text("SELECT count(*) FROM auto_engine_ticks WHERE engine_id = :e"),
            {"e": engine_id},
        )
        assert int(ticks) == 1

    # limpieza (solo renglones de ESTA prueba)
    async with factory() as session_c:
        await session_c.execute(
            text("DELETE FROM auto_engine_ticks WHERE engine_id = :e"),
            {"e": engine_id},
        )
        await session_c.execute(
            text("DELETE FROM auto_engine_runs WHERE engine_id = :e"),
            {"e": engine_id},
        )
        await session_c.commit()
