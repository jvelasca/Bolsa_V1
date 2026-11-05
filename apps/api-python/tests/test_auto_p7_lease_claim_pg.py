"""P7/P8 (auditoría .183) — lease entre procesos y claim de barra contra PostgreSQL REAL.

Qué certifica este fichero, y por qué SOLO se puede certificar contra PostgreSQL:

1. **La migración 063 es aditiva y reversible** — ``downgrade`` a
   ``062_sync_settings_check_backfill`` retira ``lease_owner``/``lease_generation``/
   ``lease_expires_at`` y su índice; ``upgrade head`` los recrea. Sin roundtrip,
   "reversible" sería una lectura del código, no un hecho medido.
2. **La adquisición es un CAS atómico, no un ``SELECT`` + ``UPDATE``** — dos sesiones
   (dos procesos) piden el lease del MISMO ``engine_id``: una lo obtiene y la otra recibe
   ``None``. El vencimiento se simula moviendo el reloj de la FILA (``lease_expires_at``
   al pasado), no el del proceso: es la columna que decide.
3. **La valla rechaza al dueño anterior** — tras reclamar el lease vencido, el tick del
   dueño viejo sube ``AutoEngineLeaseLost`` y NO deja fila de run ni de tick.
4. **Cada turno reserva su ``seq`` y se liquida en su propia fila** — el reloj de
   decisión es la barra, pero el motor ticka varias veces DENTRO de ella (stops,
   gestión de posición, salidas). Dos turnos de la misma barra obtienen claims
   distintos y cierran dos filas: bloquear por barra detendría el motor el resto del día.
5. **El claim SOBREVIVE al crash de quien lo hizo** — la reclamación se confirma antes de
   ejecutar: el ciclo interrumpido queda como ``cycle_claimed`` y el siguiente proceso
   reanuda en ``seq + 1`` sin resucitar la fila del muerto.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_P7_LEASE_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_P7_LEASE_PG_REQUIRED"
_PREVIOUS_REVISION = "062_sync_settings_check_backfill"
_HEAD = "064_strategy_account_scope"
_RUNS = "auto_engine_runs"
_LEASE_INDEX = "auto_engine_runs_lease_expires_idx"
_BAR = "2026-11-04T08:30:00+00:00"
_TTL = 180.0


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            "PostgreSQL requerido para el lease inter-proceso del motor AUTO (P7) "
            f"pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (lease inter-proceso AUTO P7) no disponible: {exc}")


@pytest_asyncio.fixture
async def lease_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


def _column_present(connection: Any, table: str, column: str) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
            ),
            {"t": table, "c": column},
        ).scalar_one_or_none()
        is not None
    )


def _index_present(connection: Any, name: str) -> bool:
    return (
        connection.execute(
            text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
            {"n": name},
        ).scalar_one_or_none()
        is not None
    )


def _engine_id() -> str:
    return f"auto-p7-{uuid.uuid4().hex[:10]}"


async def _cleanup(factory: async_sessionmaker[AsyncSession], *, engine_id: str) -> None:
    from bolsa_infrastructure.database.models.tables import (
        AutoEngineRunRow,
        AutoEngineTickRow,
    )

    async with factory() as session:
        await session.execute(
            delete(AutoEngineTickRow).where(AutoEngineTickRow.engine_id == engine_id)
        )
        await session.execute(
            delete(AutoEngineRunRow).where(AutoEngineRunRow.engine_id == engine_id)
        )
        await session.commit()


async def _expire_lease(
    factory: async_sessionmaker[AsyncSession], *, engine_id: str
) -> None:
    """Simula el paso del tiempo SOBRE LA FILA (el TTL es una columna, no un reloj de RAM)."""
    async with factory() as session:
        await session.execute(
            text(
                "UPDATE auto_engine_runs SET lease_expires_at = :past WHERE engine_id = :e"
            ),
            {"past": datetime.now(UTC) - timedelta(seconds=1), "e": engine_id},
        )
        await session.commit()


async def _tick_row(factory: async_sessionmaker[AsyncSession], *, engine_id: str) -> Any:
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import AutoEngineTickRow

    async with factory() as session:
        return (
            await session.execute(
                select(AutoEngineTickRow)
                .where(AutoEngineTickRow.engine_id == engine_id)
                .order_by(AutoEngineTickRow.seq)
                .limit(1)
            )
        ).scalar_one_or_none()


def _tick(
    *,
    engine_id: str,
    seq: int,
    claim: Any = None,
    lease: Any = None,
    proposals: int = 0,
) -> Any:
    from bolsa_application.auto_engine_state_store import AutoEngineTickInput

    return AutoEngineTickInput(
        engine_id=engine_id,
        venue="paper",
        state="RUNNING",
        seq=seq,
        proposals=proposals,
        vetoes=0,
        pending_plans=0,
        last_reason=("idle",),
        occurred_at=datetime.now(UTC),
        claim_tick_id=(claim.tick_id if claim is not None else None),
        lease_owner=(lease.owner if lease is not None else None),
        lease_generation=(lease.generation if lease is not None else None),
    )


# ── 1) La migración 063 es aditiva y reversible ───────────────────────────────


@pytest.mark.asyncio
async def test_migration_063_roundtrip_adds_and_drops_the_lease_columns(
    lease_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``downgrade`` a 062 retira las tres columnas y el índice; ``upgrade head`` los recrea."""
    pytest.importorskip("alembic")
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)

    from alembic import command
    from sqlalchemy import create_engine

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import _alembic_config, alembic_head

    get_settings.cache_clear()
    settings = get_settings()
    url = settings.database_url
    assert url is not None
    url = url.replace("postgresql://", "postgresql+psycopg://", 1).split("?", 1)[0]

    engine = create_engine(url)
    cfg = _alembic_config()
    columns = ("lease_owner", "lease_generation", "lease_expires_at")
    try:
        assert alembic_head() == _HEAD, "la guardia de la head tiene que apuntar a 064"
        with engine.connect() as connection:
            for column in columns:
                assert _column_present(connection, _RUNS, column), f"063 debe crear {column}"
            assert _index_present(connection, _LEASE_INDEX), f"falta {_LEASE_INDEX}"

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, _PREVIOUS_REVISION)
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            for column in columns:
                assert not _column_present(connection, _RUNS, column), (
                    f"downgrade retira {column} (symmetric)"
                )
            assert not _index_present(connection, _LEASE_INDEX), (
                f"downgrade retira {_LEASE_INDEX}"
            )

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            for column in columns:
                assert _column_present(connection, _RUNS, column), (
                    f"upgrade recrea {column}"
                )
            assert _index_present(connection, _LEASE_INDEX), "upgrade recrea el índice"
    finally:
        engine.dispose()


# ── 2) Un solo dueño por motor entre procesos ────────────────────────────────


@pytest.mark.asyncio
async def test_only_one_process_holds_the_lease_and_only_it_can_write(
    lease_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dos sesiones piden el lease del MISMO motor: una lo obtiene, la otra recibe ``None``.

    Y tras vencer el TTL, la que lo pierde NO puede escribir: la valla sube
    ``AutoEngineLeaseLost`` y no deja ni fila de run ni de tick del turno rechazado.
    """
    from bolsa_application.auto_engine_state_store import (
        AutoEngineLeaseLost,
        PostgresAutoEngineStore,
    )

    engine_id = _engine_id()
    try:
        async with lease_pg_factory() as session_a:
            store_a = PostgresAutoEngineStore(session_a)
            lease_a = await store_a.acquire_lease(engine_id, owner="proc-a", ttl_seconds=_TTL)
            assert lease_a is not None and lease_a.owner == "proc-a"
            assert lease_a.generation == 1

            async with lease_pg_factory() as session_b:
                store_b = PostgresAutoEngineStore(session_b)
                assert (
                    await store_b.acquire_lease(engine_id, owner="proc-b", ttl_seconds=_TTL)
                    is None
                ), "dos procesos no pueden conducir el mismo motor a la vez"

            renewed = await store_a.renew_lease(lease_a, ttl_seconds=_TTL)
            assert renewed is not None and renewed.generation == lease_a.generation, (
                "renovar es seguir siendo el mismo dueño: la generación no cambia"
            )

        # Vence el lease (columna) y B lo reclama: la generación avanza.
        await _expire_lease(lease_pg_factory, engine_id=engine_id)
        async with lease_pg_factory() as session_b:
            store_b = PostgresAutoEngineStore(session_b)
            lease_b = await store_b.acquire_lease(
                engine_id, owner="proc-b", ttl_seconds=_TTL
            )
            assert lease_b is not None and lease_b.owner == "proc-b"
            assert lease_b.generation == lease_a.generation + 1

        async with lease_pg_factory() as session_a:
            store_a = PostgresAutoEngineStore(session_a)
            assert await store_a.renew_lease(lease_a, ttl_seconds=_TTL) is None, (
                "el dueño anterior ya no puede renovar"
            )
            with pytest.raises(AutoEngineLeaseLost):
                await store_a.record_tick(_tick(engine_id=engine_id, seq=1, lease=lease_a))

        assert await _tick_row(lease_pg_factory, engine_id=engine_id) is None, (
            "una escritura rechazada por la valla no puede dejar fila de tick"
        )

        async with lease_pg_factory() as session_b:
            store_b = PostgresAutoEngineStore(session_b)
            await store_b.record_tick(_tick(engine_id=engine_id, seq=1, lease=lease_b))
        snapshot = await _tick_row(lease_pg_factory, engine_id=engine_id)
        assert snapshot is not None and snapshot.seq == 1
    finally:
        await _cleanup(lease_pg_factory, engine_id=engine_id)


# ── 3) Claim por barra lógica (P8) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_claim_reserves_a_distinct_seq_for_each_turn_and_settles_as_ONE_tick(
    lease_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dos turnos de la MISMA barra reservan ``seq`` distintos; cerrar cuenta UN tick por turno."""
    from bolsa_application.auto_engine_state_store import PostgresAutoEngineStore

    engine_id = _engine_id()
    try:
        async with lease_pg_factory() as session_a:
            store_a = PostgresAutoEngineStore(session_a)
            lease_a = await store_a.acquire_lease(engine_id, owner="proc-a", ttl_seconds=_TTL)
            assert lease_a is not None
            claim = await store_a.claim_cycle(engine_id, logical_bar=_BAR, lease=lease_a)
            assert claim is not None and claim.seq == 1

            # La misma barra en un turno POSTERIOR (gestión de posición) reserva el
            # siguiente ``seq``: el reloj de decisión es D1 y el motor ticka varias veces
            # dentro de la barra; bloquear por barra lo detendría el resto del día.
            second = await store_a.claim_cycle(engine_id, logical_bar=_BAR, lease=lease_a)
            assert second is not None and second.seq == claim.seq + 1
            assert second.tick_id != claim.tick_id

            await store_a.record_tick(
                _tick(engine_id=engine_id, seq=claim.seq, claim=claim, lease=lease_a, proposals=2)
            )
            await store_a.record_tick(
                _tick(
                    engine_id=engine_id,
                    seq=second.seq,
                    claim=second,
                    lease=lease_a,
                    proposals=3,
                )
            )

        from sqlalchemy import func, select

        from bolsa_infrastructure.database.models.tables import AutoEngineTickRow

        async with lease_pg_factory() as session:
            rows = (
                await session.execute(
                    select(AutoEngineTickRow)
                    .where(AutoEngineTickRow.engine_id == engine_id)
                    .order_by(AutoEngineTickRow.seq)
                )
            ).scalars().all()
            total = await session.scalar(
                select(func.count())
                .select_from(AutoEngineTickRow)
                .where(AutoEngineTickRow.engine_id == engine_id)
            )
        assert int(total or 0) == 2, "cada claim se LIQUIDA en su propia fila: 2 turnos, 2 filas"
        assert [row.reason for row in rows] == ["idle", "idle"], (
            "el cierre LIQUIDA la fila del claim con los totales del turno"
        )
        assert rows[0].proposals == 2 and rows[1].proposals == 3
    finally:
        await _cleanup(lease_pg_factory, engine_id=engine_id)


@pytest.mark.asyncio
async def test_the_claim_survives_the_crash_of_the_process_that_claimed_it(
    lease_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """La reclamación se confirma ANTES de ejecutar: el ciclo interrumpido deja traza."""
    from bolsa_application.auto_engine_state_store import PostgresAutoEngineStore

    engine_id = _engine_id()
    try:
        # Proceso 1: reclama la barra y MUERE antes de cerrarla (la sesión se cierra).
        async with lease_pg_factory() as session_a:
            store_a = PostgresAutoEngineStore(session_a)
            lease_a = await store_a.acquire_lease(engine_id, owner="proc-a", ttl_seconds=_TTL)
            assert lease_a is not None
            claim = await store_a.claim_cycle(engine_id, logical_bar=_BAR, lease=lease_a)
            assert claim is not None

        # Proceso 2: el lease de A vence; B conduce y su turno NO reutiliza el seq del
        # ciclo interrumpido (la traza del claim muerto se conserva).
        await _expire_lease(lease_pg_factory, engine_id=engine_id)
        async with lease_pg_factory() as session_b:
            store_b = PostgresAutoEngineStore(session_b)
            lease_b = await store_b.acquire_lease(engine_id, owner="proc-b", ttl_seconds=_TTL)
            assert lease_b is not None
            next_claim = await store_b.claim_cycle(engine_id, logical_bar=_BAR, lease=lease_b)
            assert next_claim is not None and next_claim.seq == claim.seq + 1
            await store_b.record_tick(
                _tick(
                    engine_id=engine_id,
                    seq=next_claim.seq,
                    claim=next_claim,
                    lease=lease_b,
                )
            )

        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import AutoEngineTickRow

        async with lease_pg_factory() as session:
            rows = (
                await session.execute(
                    select(AutoEngineTickRow)
                    .where(AutoEngineTickRow.engine_id == engine_id)
                    .order_by(AutoEngineTickRow.seq)
                )
            ).scalars().all()
        assert [row.reason for row in rows] == ["cycle_claimed", "idle"], (
            "el claim del proceso muerto queda como traza del ciclo interrumpido"
        )
    finally:
        await _cleanup(lease_pg_factory, engine_id=engine_id)
