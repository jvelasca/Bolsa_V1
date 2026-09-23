"""AUTO-15 (V2.56) — la racha de fallos del gate, DURABLE, contra PostgreSQL real.

Qué certifica este fichero, y por qué SOLO se puede certificar contra PostgreSQL real:

1. **La migración 045 es aditiva y reversible** — ``downgrade`` a ``044_auto_cycle_trace``
   retira ``adaptive_gate_state`` y su índice; ``upgrade head`` los recrea. Sin roundtrip,
   "reversible" sería una lectura del código, no un hecho medido.
2. **La racha SOBREVIVE al reinicio y el gate la sigue viendo** — el proceso 1 acumula 3
   fallos consecutivos del sink y los PERSISTE; el proceso 2 (otra sesión) los LEE y su gate
   sigue en ``STALE`` (congela el reparto) en vez de arrancar en ``OK``. Es el cierre de la
   ventana que ``AUTO-13`` declaró como límite: el contador era de proceso y el journal **no**
   puede reconstruirlo (una escritura que falló no dejó fila).
3. **El incremento es ATÓMICO y la clave es ``(account_id, engine_id)``** — el segundo fallo
   entra por ``ON CONFLICT DO UPDATE`` (no por un ``load``+``save`` que perdería carreras), y
   la racha de una cuenta/motor NO se filtra a otra clave.
4. **El reset no amplifica** — ``record_success`` con racha viva escribe una vez y conserva
   ``last_failure_at`` (cuándo empezó sigue siendo auditable); sin racha viva devuelve 0 y **no
   toca la fila**, para que un despliegue sano no pague una escritura por tick.
5. **Un fallo de escritura deja LIMPIA la sesión del tick** — el store escribe en la misma sesión
   del turno, así que hace ``rollback`` y sube el error: si no, el siguiente store del turno
   moriría con ``PendingRollbackError`` y esa traza rota tumbaría el compromiso de capital.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``ADAPTIVE_GATE_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "ADAPTIVE_GATE_PG_REQUIRED"
_PREVIOUS_REVISION = "044_auto_cycle_trace"
_ENGINE_ID = "auto-sim"
_GATE_TABLE = "adaptive_gate_state"
_GATE_INDEX = "adaptive_gate_state_account_failures_idx"
_REGIME = "BULL_TREND"
_FLOOR = 0.35


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la racha durable del Data Gate (AUTO-15) "
            f"pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (racha durable del Data Gate AUTO-15) no disponible: {exc}")


@pytest_asyncio.fixture
async def gate_pg_factory() -> async_sessionmaker[AsyncSession]:
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


def _table_present(connection: Any, name: str) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=:t"
            ),
            {"t": name},
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


async def _cleanup(
    factory: async_sessionmaker[AsyncSession], *, account_id: str
) -> None:
    from bolsa_infrastructure.database.models.tables import AdaptiveGateStateRow

    async with factory() as session:
        await session.execute(
            delete(AdaptiveGateStateRow).where(
                AdaptiveGateStateRow.account_id == account_id
            )
        )
        await session.commit()


class _DeadSink:
    """Sink que SIEMPRE falla: el journal caído es el escenario que el gate debe recordar."""

    async def __call__(self, _entry: Any) -> None:
        raise RuntimeError("journal caído")


def _plan() -> Any:
    from bolsa_analytics.cognitive.auto_adaptive import (
        ADAPTIVE_POLICY_VERSION,
        AdaptivePlan,
        AllocationPlan,
        RotationDecision,
        RotationPlan,
    )

    return AdaptivePlan(
        rotation=RotationPlan((RotationDecision(strategy_version="v42", active=True),)),
        allocation=AllocationPlan({}),
        regime="TREND_UP",
        policy_version=ADAPTIVE_POLICY_VERSION,
    )


class _Clock:
    """Reloj mínimo: ``_v2_instant`` solo llama a ``strftime`` con el formato ISO-UTC."""

    def __init__(self, instant: str) -> None:
        self._instant = instant

    def strftime(self, _fmt: str) -> str:
        return self._instant


def _worker(
    session: AsyncSession, *, account_id: str, now: str, failures: int = 0
) -> Any:
    """Worker mínimo (sin turno) con el store REAL del gate sobre la sesión dada."""
    from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
    from bolsa_application.adaptive_gate_store import PostgresAdaptiveGateStore

    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = account_id
    worker._engine_id = _ENGINE_ID
    worker._adaptive_sink = _DeadSink()
    worker._adaptive_reader = None
    worker._adaptive_gate_store = PostgresAdaptiveGateStore(session)
    worker._v2_adaptive_paused_cycles = {}
    worker._v2_adaptive_reactivated_at = {}
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_adaptive_state_recovered = False
    worker._v2_cycle_trace_reconciled = False
    worker._v2_adaptive_sink_failures = failures
    worker._v2_adaptive_sink_failures_durable = False
    worker._v2_adaptive_sink_last_success_at = None
    worker._v2_adaptive_journal_anchor_age = None
    worker._v2_adaptive_state_reading = None
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=True, adaptive_win_rate_floor=_FLOOR, regime_override=None
    )
    worker._time = _Clock(now)
    return worker


def _gate(worker: Any) -> Any:
    """La lectura del gate por el MISMO método que usa el tick."""
    return worker._v2_adaptive_data_gate(
        report=SimpleNamespace(by_strategy=()),
        confidence=SimpleNamespace(by_strategy=None, recent_available=None),
        regime=_REGIME,
    )


# ── 1) La migración 045 es aditiva y reversible ───────────────────────────────────


@pytest.mark.asyncio
async def test_migration_045_roundtrip_creates_and_drops_the_gate_state(
    gate_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``downgrade`` a 044 retira tabla e índice; ``upgrade head`` los recrea."""
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
    try:
        with engine.connect() as connection:
            assert _table_present(connection, _GATE_TABLE), (
                "045 debe crear la tabla de la racha durable"
            )
            assert _index_present(connection, _GATE_INDEX), f"falta {_GATE_INDEX}"

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, _PREVIOUS_REVISION)
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            assert not _table_present(connection, _GATE_TABLE), (
                "downgrade retira la tabla (symmetric)"
            )
            assert not _index_present(connection, _GATE_INDEX), f"downgrade retira {_GATE_INDEX}"

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            assert _table_present(connection, _GATE_TABLE), "upgrade recrea la tabla"
            assert _index_present(connection, _GATE_INDEX), "upgrade recrea el índice"
        assert alembic_head() != _PREVIOUS_REVISION
    finally:
        engine.dispose()


# ── 2) La racha sobrevive al reinicio y el gate la sigue viendo ────────────────────


@pytest.mark.asyncio
async def test_the_streak_survives_a_restart_and_the_gate_still_sees_it(
    gate_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """3 fallos en el proceso 1 ⇒ el proceso 2 lee 3 y su gate sigue en ``STALE`` (no ``OK``)."""
    from bolsa_analytics.cognitive.auto_adaptive_data_gate import DATA_GATE_STALE
    from bolsa_application.adaptive_gate_store import PostgresAdaptiveGateStore

    account_id = f"acc-gate-{uuid.uuid4().hex[:10]}"
    try:
        # Proceso 1: tres publicaciones fallidas consecutivas, persistidas una a una.
        async with gate_pg_factory() as session:
            worker = _worker(
                session, account_id=account_id, now="2026-09-15T09:01:00Z"
            )
            for _ in range(3):
                await worker._v2_journal_adaptive_recommendation(_plan())
            assert worker._v2_adaptive_sink_failures == 3
            assert worker._v2_adaptive_sink_failures_durable is True
            stored = await PostgresAdaptiveGateStore(session).load(account_id, _ENGINE_ID)
            assert stored is not None and stored.sink_failures == 3, (
                "el fallo tiene que quedar en la BD, no solo en el proceso"
            )

        # Proceso 2 (reinicio, otra sesión): la racha se LEE y el gate no se cree sano.
        async with gate_pg_factory() as session:
            restarted = _worker(
                session, account_id=account_id, now="2026-09-15T09:11:00Z"
            )
            await restarted._v2_recover_adaptive_gate_streak()
            assert restarted._v2_adaptive_sink_failures == 3
            reading = _gate(restarted)
            assert reading.status == DATA_GATE_STALE
            payload = reading.as_dict()
            assert payload["sinkFailures"] == 3
            assert payload["sinkFailuresDurable"] is True
    finally:
        await _cleanup(gate_pg_factory, account_id=account_id)


@pytest.mark.asyncio
async def test_a_publication_after_the_restart_cures_the_durable_streak(
    gate_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """La racha durable se CURA publicando: el reset llega a la BD y conserva el rastro."""
    from bolsa_analytics.cognitive.auto_adaptive_data_gate import DATA_GATE_OK
    from bolsa_application.adaptive_gate_store import PostgresAdaptiveGateStore

    account_id = f"acc-cure-{uuid.uuid4().hex[:10]}"
    try:
        async with gate_pg_factory() as session:
            worker = _worker(session, account_id=account_id, now="2026-09-15T09:01:00Z")
            await worker._v2_journal_adaptive_recommendation(_plan())
            await worker._v2_journal_adaptive_recommendation(_plan())
            assert worker._v2_adaptive_sink_failures == 2

        async with gate_pg_factory() as session:
            worker = _worker(session, account_id=account_id, now="2026-09-15T09:11:00Z")
            await worker._v2_recover_adaptive_gate_streak()
            assert worker._v2_adaptive_sink_failures == 2

            # El journal se recupera: la primera publicación cura la racha (y la persiste).
            async def _good_sink(_entry: Any) -> None:
                return None

            worker._adaptive_sink = _good_sink
            await worker._v2_journal_adaptive_recommendation(_plan())

            stored = await PostgresAdaptiveGateStore(session).load(account_id, _ENGINE_ID)
            assert stored is not None
            assert stored.sink_failures == 0
            assert stored.last_success_at is not None
            assert stored.last_failure_at is not None, (
                "curarse no borra cuándo empezó el fallo: el rastro sigue siendo auditable"
            )
            assert _gate(worker).status == DATA_GATE_OK
    finally:
        await _cleanup(gate_pg_factory, account_id=account_id)


# ── 3) Incremento atómico y clave (account_id, engine_id) ─────────────────────────


@pytest.mark.asyncio
async def test_the_increment_is_atomic_on_conflict_and_scoped_to_its_key(
    gate_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dos incrementos sobre la misma clave suman (``ON CONFLICT``); otra clave no se contagia."""
    from bolsa_application.adaptive_gate_store import PostgresAdaptiveGateStore

    account_id = f"acc-atomic-{uuid.uuid4().hex[:10]}"
    other_account = f"acc-other-{uuid.uuid4().hex[:10]}"
    try:
        async with gate_pg_factory() as session:
            store = PostgresAdaptiveGateStore(session)
            assert await store.load(account_id, _ENGINE_ID) is None, (
                "sin fila = no hay constancia durable de fallos (la ausencia es información)"
            )
            assert await store.record_failure(account_id, _ENGINE_ID) == 1
            assert await store.record_failure(account_id, _ENGINE_ID) == 2
            # Otra CLAVE (cuenta y motor) arranca su propia racha, sin heredar la anterior.
            assert await store.record_failure(other_account, _ENGINE_ID) == 1
            assert await store.record_failure(account_id, "otro-motor") == 1

        async with gate_pg_factory() as session:
            store = PostgresAdaptiveGateStore(session)
            first = await store.load(account_id, _ENGINE_ID)
            assert first is not None and first.sink_failures == 2
            scoped = await store.load(account_id, "otro-motor")
            assert scoped is not None and scoped.sink_failures == 1
    finally:
        await _cleanup(gate_pg_factory, account_id=account_id)
        await _cleanup(gate_pg_factory, account_id=other_account)


# ── 4) El reset no amplifica ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_reset_writes_once_and_does_not_amplify_when_idle(
    gate_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Con racha viva, un reset (``1``); sin racha, ``0`` y la fila NO se toca."""
    from bolsa_application.adaptive_gate_store import PostgresAdaptiveGateStore

    account_id = f"acc-reset-{uuid.uuid4().hex[:10]}"
    try:
        async with gate_pg_factory() as session:
            store = PostgresAdaptiveGateStore(session)
            assert await store.record_failure(
                account_id, _ENGINE_ID, at="2026-09-15T09:01:00Z"
            ) == 1
            assert await store.record_success(
                account_id, _ENGINE_ID, at="2026-09-15T09:02:00Z"
            ) == 1, "había racha viva: el reset escribe"
            before = await store.load(account_id, _ENGINE_ID)
            assert before is not None and before.sink_failures == 0
            assert before.updated_at is not None

            # Segundo reset: sin racha viva no escribe (ni crea fila ni mueve updated_at).
            assert await store.record_success(
                account_id, _ENGINE_ID, at="2026-09-15T09:03:00Z"
            ) == 0, "sin racha viva el reset NO escribe"
            after = await store.load(account_id, _ENGINE_ID)
            assert after is not None
            assert after.updated_at == before.updated_at, (
                "el camino sano no amplifica escrituras por tick"
            )
            assert after.last_success_at == before.last_success_at

        # Un store idempotente por clave: el reset sin fila tampoco inventa una.
        missing = f"acc-missing-{uuid.uuid4().hex[:10]}"
        try:
            async with gate_pg_factory() as session:
                store = PostgresAdaptiveGateStore(session)
                assert await store.record_success(missing, _ENGINE_ID) == 0
                assert await store.load(missing, _ENGINE_ID) is None
        finally:
            await _cleanup(gate_pg_factory, account_id=missing)
    finally:
        await _cleanup(gate_pg_factory, account_id=account_id)


# ── 5) Un fallo de escritura deja LIMPIA la sesión del tick ───────────────────────


@pytest.mark.asyncio
async def test_a_failed_write_leaves_the_tick_session_usable(
    gate_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Sesión envenenada ⇒ el gate falla, se DECLARA, y el siguiente store del turno escribe.

    El worker escribe la racha en la MISMA sesión del tick. Se envenena la transacción a mano
    (``SELECT 1/0``) para medir lo que pasa de verdad cuando la escritura del gate falla: el store
    hace ``rollback`` (sin él, el siguiente store del turno moriría con ``PendingRollbackError``) y
    el error SUBE para que el worker lo declare (la racha cae al proceso, no se finge durable).
    """
    from sqlalchemy.exc import DBAPIError

    from bolsa_application.adaptive_gate_store import PostgresAdaptiveGateStore

    account_id = f"acc-poisoned-{uuid.uuid4().hex[:10]}"
    try:
        async with gate_pg_factory() as session:
            store = PostgresAdaptiveGateStore(session)

            # 1) La sesión del tick queda envenenada (lo que haría cualquier store que fallase).
            with pytest.raises(DBAPIError):
                await session.execute(text("SELECT 1 / 0"))

            # 2) La escritura del gate falla... y el error se declara (no se traga).
            with pytest.raises(DBAPIError):
                await store.record_failure(account_id, _ENGINE_ID)

            # 3) ...pero la sesión queda LIMPIA: el siguiente store del MISMO turno escribe.
            assert await store.record_failure(account_id, _ENGINE_ID) == 1, (
                "sin rollback, esto moriría con PendingRollbackError: la traza rota tumbaría el "
                "turno"
            )
            stored = await store.load(account_id, _ENGINE_ID)
            assert stored is not None and stored.sink_failures == 1, (
                "el fallo declarado no puede dejar la racha persistida a medias"
            )
    finally:
        await _cleanup(gate_pg_factory, account_id=account_id)
