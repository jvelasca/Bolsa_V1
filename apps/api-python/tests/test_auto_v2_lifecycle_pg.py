"""AUTO-2 · V2.42 — durabilidad REAL del FSM de posición sobre PostgreSQL (gated).

Certifica sobre la base de datos real (migración 040, SIN migración nueva) lo que un
crash NO puede perder del ciclo de vida:

1. **Rehidratación por estado intermedio**: ``PROTECTED``, ``T1_REACHED``, ``TRAILING``,
   ``EXIT_PENDING`` y ``RECONCILIATION_REQUIRED`` vuelven del JSONB
   ``sim_auto_positions.position_state`` con ``lifecycleState``, ``currentStop`` y
   ``trailing.highWatermark`` INTACTOS (roundtrip exacto, no una proyección aproximada).
2. **El ratchet CONTINÚA tras el reinicio**: el trailing se recalcula desde el máximo
   persistido, no desde la entrada. Sin el pico durable el stop retrocedería al valor de
   nacimiento, que es exactamente el fallo que AUTO-2 cierra.
3. **Degradación declarada**: un blob con estado NO verificable (``CLOSED`` con cantidad
   viva, o un estado inventado) se rehidrata degradado a ``RECONCILIATION_REQUIRED`` +
   ``PROTECTION_MISSING``, nunca como si estuviera verificado.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_V2_LIFECYCLE_PG_REQUIRED=1`` un skip silencioso es un FALLO duro.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_analytics.cognitive.exit_plan import (
    build_exit_plan_from_position,
    is_thesis_invalidated,
)
from bolsa_analytics.cognitive.position_lifecycle import (
    advance_lifecycle,
    compute_trail_stop,
    trailing_state_dict,
    trailing_status,
)
from bolsa_analytics.cognitive.position_state import (
    PositionState,
    apply_position_mark,
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.sim_durable_store import PostgresSimAutoPositionStore

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_V2_LIFECYCLE_PG_REQUIRED"
_ENGINE_ID = "auto-sim"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para el FSM de posición (AUTO-2) pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (AUTO-2 lifecycle) no disponible: {exc}")


@pytest_asyncio.fixture
async def lifecycle_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto a head (042).
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_account(session: AsyncSession) -> str:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"AUTO-V2L-{uuid.uuid4().hex[:8]}",
        initial_deposit=100_000.0,
    )
    await session.commit()
    return scope.account.id


def _open_long(*, stop: float = 95.0, qty: float = 10.0) -> PositionState:
    """Posición V2 nacida de un plan: entry 100, stop 95 ⇒ R = 5."""
    plan = {
        "decisionId": "dec-lifecycle-pg",
        "instrumentId": "AAA",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": stop,
        "target1": 105.0,
        "target2": 110.0,
    }
    position = build_position_state_from_fill(
        plan, fill_price=100.0, fill_quantity=qty, position_id="pos-lifecycle-pg"
    )
    assert position is not None
    entered, _ = advance_lifecycle(position, "ENTRY_FILLED", at="2026-09-17T09:00:00Z")
    return entered


def _intermediate_states() -> dict[str, PositionState]:
    """Un ejemplar VERIFICABLE de cada estado intermedio del FSM."""
    base = _open_long()
    protected, _ = advance_lifecycle(base, "PROTECT_APPLIED", at="2026-09-17T09:01:00Z")
    protected = replace(
        protected,
        current_stop=100.0,
        trailing=trailing_state_dict(
            status="inactive", high_watermark=100.0, at="2026-09-17T09:01:00Z"
        ),
    )

    t1, _ = advance_lifecycle(base, "T1_HIT", at="2026-09-17T09:02:00Z")
    t1 = replace(
        t1,
        target1_achieved_at="2026-09-17T09:02:00Z",
        trailing=trailing_state_dict(
            status="armed", high_watermark=105.0, at="2026-09-17T09:02:00Z"
        ),
    )

    trailing, _ = advance_lifecycle(
        t1, "TRAIL_ADVANCED", at="2026-09-17T09:03:00Z", mark_trailing=True
    )
    trailing = replace(
        trailing,
        current_stop=103.0,
        trailing=trailing_state_dict(
            status="active", high_watermark=110.0, trail_distance_r=1.0, at="2026-09-17T09:03:00Z"
        ),
    )

    pending, _ = advance_lifecycle(trailing, "EXIT_REQUESTED", at="2026-09-17T09:04:00Z")

    degraded = replace(
        base,
        lifecycle_state="RECONCILIATION_REQUIRED",
        protection_state={
            "state": "PROTECTION_MISSING",
            "source": "reconstructed",
            "reason": "no_durable_plan",
            "at": "2026-09-17T09:05:00Z",
        },
    )
    return {
        "PROTECTED": protected,
        "T1_REACHED": t1,
        "TRAILING": trailing,
        "EXIT_PENDING": pending,
        "RECONCILIATION_REQUIRED": degraded,
    }


@pytest.mark.asyncio
async def test_v2_intermediate_states_survive_pg_roundtrip(
    lifecycle_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Cada estado intermedio vuelve EXACTO del JSONB (nueva sesión, no RAM)."""
    states = _intermediate_states()
    account_id: str | None = None
    try:
        async with lifecycle_pg_factory() as session:
            account_id = await _seed_account(session)
            store = PostgresSimAutoPositionStore(session)
            for state_name, position in states.items():
                await store.upsert(
                    account_id,
                    _ENGINE_ID,
                    state_name,
                    Decimal(str(position.remaining_quantity)),
                    entry_price=Decimal(str(position.actual_entry)),
                    high_watermark=Decimal("110"),
                    stop_price=Decimal(str(position.current_stop)),
                    position_state=position.to_dict(),
                )
            await session.commit()

        # Sesión NUEVA (frontera de proceso): sólo la BD sobrevive.
        async with lifecycle_pg_factory() as session:
            projection = await PostgresSimAutoPositionStore(session).read_projection(
                account_id, _ENGINE_ID
            )

        assert set(projection) == set(states)
        for state_name, original in states.items():
            blob = projection[state_name].position_state
            assert blob is not None, f"{state_name}: el plan debe ser durable"
            restored = position_state_from_dict(dict(blob))
            assert restored is not None, f"{state_name}: el blob debe rehidratar"
            assert restored.lifecycle_state == state_name
            assert restored.current_stop == original.current_stop
            assert restored.remaining_quantity == original.remaining_quantity
            assert restored.trailing == original.trailing
            assert restored.protection_state == original.protection_state
            # Roundtrip EXACTO: la rehidratación no inventa ni pierde campos.
            assert restored.to_dict() == original.to_dict()
            assert projection[state_name].stop_price == Decimal(str(original.current_stop))
    finally:
        await _cleanup(lifecycle_pg_factory, account_id)


@pytest.mark.asyncio
async def test_v2_trailing_continues_from_persisted_watermark_after_restart(
    lifecycle_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """El ratchet continúa desde el máximo PERSISTIDO (no desde la entrada).

    Tras el reinicio, el trailing debe proponer ``máximo durable − 1R``. Si el máximo se
    perdiera, el stop propuesto volvería al valor de nacimiento y la protección ganada
    se esfumaría con el crash (el fallo que AUTO-2 cierra).
    """
    account_id: str | None = None
    original = _intermediate_states()["TRAILING"]
    try:
        async with lifecycle_pg_factory() as session:
            account_id = await _seed_account(session)
            await PostgresSimAutoPositionStore(session).upsert(
                account_id,
                _ENGINE_ID,
                "AAA",
                Decimal(str(original.remaining_quantity)),
                entry_price=Decimal("100"),
                high_watermark=Decimal("110"),
                stop_price=Decimal(str(original.current_stop)),
                position_state=original.to_dict(),
            )
            await session.commit()

        # Reinicio: nueva sesión, máximo leído del espejo (columna), no de la RAM.
        async with lifecycle_pg_factory() as session:
            row = (
                await PostgresSimAutoPositionStore(session).read_projection(account_id, _ENGINE_ID)
            )["AAA"]
        restored = position_state_from_dict(dict(row.position_state or {}))
        assert restored is not None
        assert trailing_status(restored) == "active"
        watermark = float(row.high_watermark or 0)
        assert watermark == 110.0, "el máximo persistido es la única memoria del pico"

        # Con el máximo durable, el trailing sigue subiendo; sin él, no habría trailing.
        next_stop = compute_trail_stop(restored, trail_width="medium", high_watermark=watermark)
        assert next_stop is not None
        assert next_stop > restored.current_stop, "el ratchet continúa tras el reinicio"
        assert next_stop == 105.0, "110 − 1R (R=5)"
        # Sin máximo no se inventa un stop (H-4): ``compute_trail_stop`` devuelve ``None``
        # en vez de caer a la entrada o al stop vigente, así que el llamante no aplica
        # ningún ratchet y la posición conserva el stop que ya tenía.
        without_peak = replace(restored, trailing={"status": "active"})
        assert (
            compute_trail_stop(without_peak, trail_width="medium", high_watermark=None) is None
        )
        assert restored.current_stop == original.current_stop, "el stop vivo no se toca"
    finally:
        await _cleanup(lifecycle_pg_factory, account_id)


@pytest.mark.asyncio
async def test_v2_unverifiable_state_degrades_on_rehydration(
    lifecycle_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Un estado no verificable se degrada al rehidratar: nunca se confía en él.

    ``CLOSED`` con cantidad viva (o un estado inventado) es la firma de un blob corrupto
    o de un bug: la posición queda ``RECONCILIATION_REQUIRED`` + ``PROTECTION_MISSING``
    (fail-closed declarado), no "sin problema".
    """
    account_id: str | None = None
    try:
        async with lifecycle_pg_factory() as session:
            account_id = await _seed_account(session)
            store = PostgresSimAutoPositionStore(session)
            corrupt = _open_long().to_dict()
            corrupt["lifecycleState"] = "CLOSED"  # contradice remaining > 0
            assert corrupt["remainingQuantity"] > 0
            await store.upsert(
                account_id,
                _ENGINE_ID,
                "CORRUPT",
                Decimal("10"),
                position_state=corrupt,
            )
            invented = _open_long().to_dict()
            invented["lifecycleState"] = "NO_EXISTE"
            await store.upsert(
                account_id,
                _ENGINE_ID,
                "INVENTED",
                Decimal("10"),
                position_state=invented,
            )
            await session.commit()

        async with lifecycle_pg_factory() as session:
            projection = await PostgresSimAutoPositionStore(session).read_projection(
                account_id, _ENGINE_ID
            )
        for symbol in ("CORRUPT", "INVENTED"):
            restored = position_state_from_dict(dict(projection[symbol].position_state or {}))
            assert restored is not None
            assert restored.lifecycle_state == "RECONCILIATION_REQUIRED"
            assert restored.protection_state["state"] == "RECONCILIATION_REQUIRED"
    finally:
        await _cleanup(lifecycle_pg_factory, account_id)


@pytest.mark.asyncio
async def test_v2_holding_deadline_survives_pg_and_stays_frozen(
    lifecycle_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """E1: el techo de mantenimiento es durable y NO se re-deriva con el reloj del reinicio.

    El techo se congela en el nacimiento (decisión D1). Si el reinicio lo recalculara con
    su propio reloj, la fecha de salida se movería sola: la posición viviría más (o menos)
    de lo que la plantilla declaró. Aquí se persiste, se lee de una sesión NUEVA y se
    comprueba que el valor es el del nacimiento, no uno nuevo.
    """
    account_id: str | None = None
    try:
        async with lifecycle_pg_factory() as session:
            account_id = await _seed_account(session)
            born, _ = advance_lifecycle(
                _open_long(), "ENTRY_FILLED", at="2026-09-17T09:00:00Z"
            )
            frozen = replace(
                born,
                holding_deadline_at="2026-11-01T09:00:00Z",
                invalidation_price=97.5,
            )
            await PostgresSimAutoPositionStore(session).upsert(
                account_id,
                _ENGINE_ID,
                "AAA",
                Decimal(str(frozen.remaining_quantity)),
                entry_price=Decimal("100"),
                stop_price=Decimal(str(frozen.current_stop)),
                position_state=frozen.to_dict(),
            )
            await session.commit()

        async with lifecycle_pg_factory() as session:
            row = (
                await PostgresSimAutoPositionStore(session).read_projection(account_id, _ENGINE_ID)
            )["AAA"]
        assert row.position_state is not None
        restored = position_state_from_dict(dict(row.position_state))
        assert restored is not None
        assert restored.holding_deadline_at == "2026-11-01T09:00:00Z"
        assert restored.invalidation_price == 97.5
        assert restored.to_dict() == frozen.to_dict(), "roundtrip exacto, sin re-derivar"

        # Un tick con OTRO reloj no mueve el techo: la gestión lee el valor persistido.
        before = build_exit_plan_from_position(
            restored, now="2026-10-31T09:00:00Z", expires_at=restored.holding_deadline_at
        )
        after = build_exit_plan_from_position(
            restored, now="2026-11-01T09:00:00Z", expires_at=restored.holding_deadline_at
        )
        assert before is not None and before.primary_reason is None
        assert after is not None and after.primary_reason == "TIME_STOP"
    finally:
        await _cleanup(lifecycle_pg_factory, account_id)


@pytest.mark.asyncio
async def test_v2_confirmed_thesis_invalidation_survives_pg(
    lifecycle_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """E3: una invalidación ya CONFIRMADA sigue confirmada tras el reinicio.

    La confirmación vive en hechos persistidos: el nivel congelado al nacer
    (``invalidationPrice``) y el peor adverso del MAE (``mfeMae.maeR``). Si el precio se
    recuperó después, un motor que sólo mirara el mark actual "olvidaría" que la tesis ya
    estaba muerta y dejaría viva una posición que debía venderse.
    """
    account_id: str | None = None
    try:
        async with lifecycle_pg_factory() as session:
            account_id = await _seed_account(session)
            born = replace(
                _open_long(),
                invalidation_price=98.0,
                holding_deadline_at="2026-11-01T09:00:00Z",
            )
            dipped = apply_position_mark(born, 97.0, at="2026-09-17T09:05:00Z")
            assert dipped is not None
            recovered = apply_position_mark(dipped, 108.0, at="2026-09-17T09:10:00Z")
            assert recovered is not None
            assert is_thesis_invalidated(recovered, mark_price=108.0) is True
            await PostgresSimAutoPositionStore(session).upsert(
                account_id,
                _ENGINE_ID,
                "AAA",
                Decimal(str(recovered.remaining_quantity)),
                entry_price=Decimal("100"),
                high_watermark=Decimal("108"),
                stop_price=Decimal(str(recovered.current_stop)),
                position_state=recovered.to_dict(),
            )
            await session.commit()

        async with lifecycle_pg_factory() as session:
            row = (
                await PostgresSimAutoPositionStore(session).read_projection(account_id, _ENGINE_ID)
            )["AAA"]
        assert row.position_state is not None
        restored = position_state_from_dict(dict(row.position_state))
        assert restored is not None
        assert restored.invalidation_price == 98.0
        assert restored.mfe_mae.get("maeR") is not None
        assert float(restored.mfe_mae["maeR"]) < 0, "el peor adverso es un hecho persistido"
        # Ya recuperado, el mark actual NO desmiente la invalidación confirmada.
        assert is_thesis_invalidated(restored, mark_price=108.0) is True
        # Y el gestor de salida la declara con su precedencia propia (por debajo del stop).
        plan = build_exit_plan_from_position(restored, mark_price=108.0, thesis_invalid=True)
        assert plan is not None
        assert "THESIS_INVALIDATION" in plan.reasons
    finally:
        await _cleanup(lifecycle_pg_factory, account_id)


@pytest.mark.asyncio
async def test_v2_real_atr_geometry_survives_pg(
    lifecycle_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """E2: la geometría construida con ATR REAL es la que sobrevive (no se re-deriva).

    ``atrSource`` es provenance de journal, no una columna: lo durable es la geometría que
    ese ATR produjo. Si el reinicio la re-derivara con el fallback sintético, el stop de
    una posición abierta cambiaría con el crash.
    """
    account_id: str | None = None
    try:
        real_atr = 2.5  # entry 100, k=1.5 ⇒ stop 96.25, R=3.75
        async with lifecycle_pg_factory() as session:
            account_id = await _seed_account(session)
            plan = {
                "decisionId": "dec-atr-pg",
                "instrumentId": "AAA",
                "direction": "long",
                "status": "TRIGGERED",
                "entry": 100.0,
                "structuralStop": 96.25,
                "target1": 100.0 + real_atr * 1.5,
                "target2": 100.0 + real_atr * 1.5 * 2,
            }
            position = build_position_state_from_fill(
                plan, fill_price=100.0, fill_quantity=10.0, position_id="pos-atr-pg"
            )
            assert position is not None
            assert position.initial_stop == 96.25
            await PostgresSimAutoPositionStore(session).upsert(
                account_id,
                _ENGINE_ID,
                "AAA",
                Decimal("10"),
                entry_price=Decimal("100"),
                stop_price=Decimal(str(position.current_stop)),
                position_state=position.to_dict(),
            )
            await session.commit()

        async with lifecycle_pg_factory() as session:
            row = (
                await PostgresSimAutoPositionStore(session).read_projection(account_id, _ENGINE_ID)
            )["AAA"]
        assert row.position_state is not None
        restored = position_state_from_dict(dict(row.position_state))
        assert restored is not None
        assert restored.initial_stop == 96.25, "la geometría real no se re-deriva al rehidratar"
        assert restored.current_stop == 96.25
        assert restored.initial_risk == 3.75
        assert row.stop_price == Decimal("96.2500") or row.stop_price == Decimal(
            str(restored.current_stop)
        )
    finally:
        await _cleanup(lifecycle_pg_factory, account_id)


async def _cleanup(
    factory: async_sessionmaker[AsyncSession], account_id: str | None
) -> None:
    if account_id is None:
        return
    from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

    async with factory() as session:
        await session.execute(
            delete(SimAutoPositionRow).where(SimAutoPositionRow.account_id == account_id)
        )
        await session.commit()
