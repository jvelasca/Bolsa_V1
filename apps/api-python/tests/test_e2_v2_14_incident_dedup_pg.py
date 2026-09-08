"""V2.14 E2 (C1) — dedup OPEN real + reconcile de posición/live_drift contra
PostgreSQL real en el head FINAL ``022_live_orders_exec``.

Entrega honesta de la batería C1 de E2-full pedida por el auditor: valida sobre
**PostgreSQL real** (no stub) los dos writers gated que P2-01 y P1-02 añadieron a
``live_order_recovery_worker``:

* ``publish_order_live_drifts`` (P2-01) → abre incidente durable ``live_drift``
  por cuenta, y DOS sesiones concurrentes que intentan abrirlo "a la vez" para el
  mismo ``(account_id, kind)`` materializan **exactamente UNA** fila OPEN (dedup
  de OPEN multi-worker en la BD, P2-2, sin auto-heal de drift).
* ``sync_opening_incidents`` (reusado por P1-02/``reconcile_live_positions``) →
  un status LR-1 ``unavailable``/``drift`` abre incidentes
  ``live_unavailable``/``live_drift`` con dedup 1-por-(account,kind).
* Los CHECK financieros de ``live_orders`` (021, hoy vigilados por la BD tras
  aplicar 022) rechazan una fila impossibile (filled > quantity).

NO es un test corriente sin DB: exige ``DATABASE_URL`` apuntando a una BD en el
head ``022_live_orders_exec`` (V2.14). Sin ella → skip; con ``E2_PG_REQUIRED=1``
(CI/Release-tag) → fail hard. Escenario recomendado: base ``bolsa_c1_scratch``
recién migrada (001→022), nunca la shared/histórica en 021.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_HEAD = "023_ohlcv_bars_unique_reconcile"


def _load_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover — dep opcional
        return
    load_dotenv(env_path, override=False)


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get("E2_PG_REQUIRED") == "1":
        raise AssertionError(
            f"e2-v2-14-pg required pero PostgreSQL no está en head {_HEAD}: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/head {_HEAD} no disponible: {exc}")


@pytest_asyncio.fixture
async def pg_engine() -> AsyncIterator[AsyncEngine]:
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            version = await conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = {row[0] for row in version}
            if _HEAD not in versions:
                raise RuntimeError(
                    f"alembic_version is {versions!r}; expected {_HEAD} (V2.14 head)"
                )
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        _require_or_skip(exc)
        raise
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(
    pg_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(pg_engine, expire_on_commit=False)


async def _delete_incidents(factory: async_sessionmaker[AsyncSession], account_id: str) -> None:
    """Limpieza determinista de la faena (cuentas uuid-sufijadas, no toca otras)."""
    async with factory() as session:
        await session.execute(
            text("DELETE FROM operational_incidents WHERE account_id = :a"),
            {"a": account_id},
        )
        await session.commit()


def _cleanup_account() -> str:
    return f"acc-e2-{uuid4().hex[:10]}"


async def _active_kinds(factory: async_sessionmaker[AsyncSession], account_id: str) -> set[str]:
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    text(
                        "SELECT kind FROM operational_incidents "
                        "WHERE account_id = :a AND status IN ('open','in_review','resolved')"
                    ),
                    {"a": account_id},
                )
            )
            .scalars()
            .all()
        )
        return set(rows)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# P2-01: publish_order_live_drifts → live_drift durable (real PG)
# ---------------------------------------------------------------------------


def _report(*drifts_proto: dict) -> object:  # noqa: D401
    """Construye un report con LiveOrderDrift actionables/query_unavailable."""
    from bolsa_application.live_order_machine_reconcile import (
        LiveOrderDrift,
        LiveOrderMachineReconcileReport,
    )

    report = LiveOrderMachineReconcileReport()
    for p in drifts_proto:
        report.drifts.append(
            LiveOrderDrift(  # type: ignore[call-arg]
                order_id=p["order_id"],
                account_id=p["account_id"],
                venue_order_id=p["venue_order_id"],
                machine_state=p["machine_state"],
                broker_state=p.get("broker_state"),
                kind=p["kind"],
                suggested=p.get("suggested"),
                broker_filled=p.get("broker_filled"),
                broker_remaining=p.get("broker_remaining"),
                reason=p.get("reason"),
            )
        )
    return report


@pytest.mark.asyncio
async def test_publish_live_drift_opens_single_durable_incident(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Drift real accionable → 1 incidente ``live_drift`` OPEN durable en PG."""
    from bolsa_application.operational_incident_store import (
        PostgresOperationalIncidentStore,
    )
    from bolsa_application.order_live_drift_incident import publish_order_live_drifts

    account = _cleanup_account()
    try:
        async with session_factory() as session:
            store = PostgresOperationalIncidentStore(session)
            report = _report(
                {
                    "account_id": account,
                    "order_id": "lo-e2-1",
                    "venue_order_id": "x-1",
                    "machine_state": "CANCEL_REQUESTED",
                    "broker_state": "CANCELLED",
                    "kind": "cancel_broker_side",
                    "suggested": "CANCELLED",
                },
                # query_unavailable NO es drift: no debe contar ni abrir.
                {
                    "account_id": account,
                    "order_id": "lo-e2-2",
                    "venue_order_id": "x-2",
                    "machine_state": "SUBMITTED",
                    "broker_state": None,
                    "kind": "query_unavailable",
                    "suggested": None,
                },
            )
            res = await publish_order_live_drifts(report, holder=store)
            await session.commit()

        assert res.opened == 1, res.summary()
        assert res.accounts_with_actionable == 1, res.summary()
        assert res.skipped_unavailable == 1, res.summary()
        assert res.already_active == 0, res.summary()
        assert await _active_kinds(session_factory, account) == {"live_drift"}
    finally:
        await _delete_incidents(session_factory, account)


@pytest.mark.asyncio
async def test_publish_live_drift_two_sessions_single_open(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """DOS sesiones concurrentes abren el mismo (account,live_drift) → 1 OPEN.

    La condición del P2-2/auditor se prueba sobre PostgreSQL REAL: la carrera por
    el partial-unique activo (account_id,kind) + el remezcla de IntegrityError
    del store no fabrica una 2ª fila OPEN. Al cierre hay exactamente UN
    ``live_drift`` activo (quien perdió deduplica hacia el ganador, sin crear ni
    auto-heal).
    """
    from bolsa_application.operational_incident_store import (
        PostgresOperationalIncidentStore,
    )
    from bolsa_application.order_live_drift_incident import publish_order_live_drifts

    account = _cleanup_account()

    async def _publish(worker: str) -> int:
        async with session_factory() as session:
            store = PostgresOperationalIncidentStore(session)
            report = _report(
                {
                    "account_id": account,
                    "order_id": f"lo-race-{worker}",
                    "venue_order_id": f"x-{worker}",
                    "machine_state": "CANCEL_REQUESTED",
                    "broker_state": "CANCELLED",
                    "kind": "cancel_broker_side",
                    "suggested": "CANCELLED",
                },
            )
            res = await publish_order_live_drifts(report, holder=store)
            # El que gana commitea; el que cae en IntegrityError deduplica (no hace
            # commit propio per se, el store ya gestiona rollback+reconsulta).
            try:
                await session.commit()
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                raise exc
            return res.opened

    try:
        a_task = asyncio.create_task(_publish("a"))
        b_task = asyncio.create_task(_publish("b"))
        (opened_a, opened_b) = await asyncio.gather(a_task, b_task)
        # El invariante: la unión NUNCA es > 1 OPEN materializado por (account,kind).
        # (alguno de los dos pudo ver 'already_active' si el otro ya commitó.)
        assert (opened_a + opened_b) >= 1, "nadie materializó el OPEN"
        assert await _active_kinds(session_factory, account) == {"live_drift"}
        # Invariante físico: una sola fila activa de live_drift (la guardamos ya
        # verificando cardinalidad del set; abajo lo reforzamos con COUNT).
        async with session_factory() as session:
            count = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM operational_incidents "
                        "WHERE account_id = :a AND kind = 'live_drift' "
                        "AND status IN ('open','in_review','resolved')"
                    ),
                    {"a": account},
                )
            ).scalar_one()
            assert count == 1, f"doble-OPEN en PG real: {count}"
    finally:
        await _delete_incidents(session_factory, account)


# ---------------------------------------------------------------------------
# P1-02: sync_opening_incidents (LR-1) → live_unavailable/live_drift (real PG)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_opening_live_unavailable_idempotent_on_pg(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """LR-1 'unavailable' → live_unavailable durable; DOS pasadas → 1 OPEN."""
    from bolsa_application.operational_incident_store import (
        PostgresOperationalIncidentStore,
        sync_opening_incidents,
    )

    account = _cleanup_account()
    try:
        async with session_factory() as session:
            store = PostgresOperationalIncidentStore(session)
            first = await sync_opening_incidents(
                store, account_id=account, live_recon_status="unavailable", broker_venue="live"
            )
            await session.commit()
            second = await sync_opening_incidents(
                store, account_id=account, live_recon_status="unavailable", broker_venue="live"
            )
            await session.commit()
        assert first == "unresolved"
        assert second == "unresolved"
        assert await _active_kinds(session_factory, account) == {"live_unavailable"}
        async with session_factory() as session:
            count = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM operational_incidents "
                        "WHERE account_id = :a AND kind = 'live_unavailable' "
                        "AND status IN ('open','in_review','resolved')"
                    ),
                    {"a": account},
                )
            ).scalar_one()
            assert count == 1, f"dedup roto en PG real: {count}"
    finally:
        await _delete_incidents(session_factory, account)


@pytest.mark.asyncio
async def test_live_orders_check_constraints_reject_impossible_fill(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """021 finance CHECK se ejecutan en la BD (022 no los elimina): filled>qty → fail.

    Vulnera volontairemente el invariante (filled_quantity + remaining = quantity)
    y los bounds (filled <= quantity) exigiendo que PostgreSQL lo RECHAZE con
    IntegrityError (la 2ª línea de defensa real del pipeline, no solo el dominio
    Python), y que la fila NO quede materializada.
    """
    order_id = f"lo-ck-{uuid4().hex[:10]}"
    account = _cleanup_account()
    rejected = False
    async with session_factory() as session:
        try:
            await session.execute(
                text(
                    "INSERT INTO live_orders (order_id, account_id, status, venue, "
                    "instrument_id, side, quantity, filled_quantity, remaining_quantity, "
                    "venue_order_id, created_at, updated_at) VALUES "
                    "(:oid, :acc, 'PARTIAL', 'live', 'inst', 'buy', 100, 120, -20, "
                    ":vo, now(), now())"
                ),
                {"oid": order_id, "acc": account, "vo": "x-ck-zz"},
            )
            await session.commit()
        except IntegrityError:
            rejected = True
            await session.rollback()

    assert rejected, "el CHECK financiero no rechazó filled>quantity/remaining<0"

    # La fila imposible no quedó materializada.
    async with session_factory() as session:
        exists = (
            (
                await session.execute(
                    text("SELECT 1 FROM live_orders WHERE order_id = :oid LIMIT 1"),
                    {"oid": order_id},
                )
            )
            .scalars()
            .first()
        )
    assert exists is None, "fila imposible persistida pese al CHECK"
