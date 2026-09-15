"""AUTO 2.0 · P4 — durabilidad REAL del estado V2 sobre PostgreSQL (gated).

Certifica sobre la base de datos real (migración 040) los dos estados que un crash NO
puede perder:

1. **Plan operativo de la posición** (``sim_auto_positions.position_state``): tras el
   reinicio el nuevo worker REHIDRATA el mismo ``PositionState`` (mismo ``tradePlanId``
   y mismo stop), en vez de reconstruir una geometría aproximada.
2. **Señales consumidas** (``sim_consumed_signals``): la señal ya tomada sobre la barra
   corriente sigue vetada tras el reinicio ⇒ no se re-abre la MISMA oportunidad.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real/credenciales hace
``pytest.skip``; con ``AUTO_V2_DURABLE_PG_REQUIRED=1`` un skip silencioso es un FALLO
duro. NUNCA abre el bridge LIVE (venue simulated).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_V2_DURABLE_PG_REQUIRED"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para V2 durable pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (V2 durable) no disponible: {exc}")


@pytest_asyncio.fixture
async def v2_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto a head (040 incluida).
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
        name=f"AUTO-V2D-{uuid.uuid4().hex[:8]}",
        initial_deposit=100_000.0,
    )
    await session.commit()
    return scope.account.id


async def _seed_instrument(session: AsyncSession, instrument_id: str) -> None:
    from datetime import UTC, datetime

    from bolsa_infrastructure.database.models.tables import InstrumentRow

    session.add(
        InstrumentRow(
            id=instrument_id,
            symbol=f"V2{uuid.uuid4().hex[:6].upper()}",
            yahoo_symbol=f"V2{uuid.uuid4().hex[:8]}",
            isin=None,
            name="AUTO-V2-Durable",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    await session.commit()


class _BuyOnce:
    """Spine determinista: BUY mientras no haya posición abierta, si no HOLD."""

    def __init__(self, symbol: str, lot: float = 100.0) -> None:
        self._symbol = symbol
        self._lot = lot

    def __call__(self, symbol: str):
        from bolsa_application.decision_contract import DecisionPackage

        if symbol != self._symbol:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)
        return DecisionPackage(action="BUY", instrument_id=self._symbol, quantity=self._lot)


async def _durable_rows(
    factory: async_sessionmaker[AsyncSession], account_id: str, engine_id: str
) -> tuple[str | None, int]:
    """``(position_state del símbolo, nº de señales consumidas)`` leídos de PG."""
    from bolsa_infrastructure.database.models.tables import (
        SimAutoPositionRow,
        SimConsumedSignalRow,
    )

    async with factory() as session:
        position_state = (
            await session.execute(
                select(SimAutoPositionRow.position_state).where(
                    SimAutoPositionRow.account_id == account_id,
                    SimAutoPositionRow.engine_id == engine_id,
                )
            )
        ).scalar_one_or_none()
        consumed = (
            await session.execute(
                select(func.count())
                .select_from(SimConsumedSignalRow)
                .where(
                    SimConsumedSignalRow.account_id == account_id,
                    SimConsumedSignalRow.engine_id == engine_id,
                )
            )
        ).scalar()
    return position_state, int(consumed or 0)


@pytest.mark.asyncio
async def test_v2_durable_plan_and_consumed_signal_survive_real_restart(
    v2_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reinicio REAL (nueva sesión/proceso sobre la misma BD) con V2 activo.

    Tras el crash, el worker nuevo debe (1) rehidratar el plan que el anterior seguía
    —no inventar geometría— y (2) seguir considerando consumida la señal de la barra
    (el BUY del spine no puede reabrir la MISMA oportunidad).
    """
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
    )

    instrument_id = f"inst-v2d-{uuid.uuid4().hex[:10]}"
    engine_id = f"auto-v2d-{uuid.uuid4().hex[:10]}"
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "simulated")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", instrument_id)
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")

    account_id: str | None = None
    try:
        async with v2_pg_factory() as session:
            account_id = await _seed_account(session)
            await _seed_instrument(session, instrument_id)

        worker1 = AutoSimulationWorker(
            decider=_BuyOnce(instrument_id, lot=100.0),
            engine_id=engine_id,
            account_id=account_id,
        )
        runtime1 = AutoSimRuntime(
            v2_pg_factory, worker=worker1, engine_id=engine_id, account_id=account_id
        )
        for _ in range(8):
            await runtime1.run_tick()
            if worker1._open.get(instrument_id, Decimal("0")) > 0:
                break
        assert worker1._open.get(instrument_id, Decimal("0")) > 0, "abre en el camino real"
        plan1 = worker1._v2_positions.get(instrument_id)
        assert plan1 is not None, "la apertura V2 crea el PositionState"
        consumed1 = set(worker1._v2_consumed_signals)
        assert len(consumed1) == 1, "el fill consume la señal de la barra"

        # ── Durable en PG: el plan y la marca existen FUERA del proceso ──────────
        stored_state, stored_consumed = await _durable_rows(v2_pg_factory, account_id, engine_id)
        assert stored_state, "el plan operativo quedó persistido en sim_auto_positions"
        assert stored_state.get("tradePlanId") == plan1.trade_plan_id
        assert stored_consumed == 1, "la señal consumida quedó persistida"

        # ── Crash + restart: proceso nuevo (worker nuevo) sobre la MISMA BD ──────
        worker2 = AutoSimulationWorker(
            decider=_BuyOnce(instrument_id, lot=100.0),
            engine_id=engine_id,
            account_id=account_id,
        )
        runtime2 = AutoSimRuntime(
            v2_pg_factory, worker=worker2, engine_id=engine_id, account_id=account_id
        )
        report2 = await runtime2.run_tick()
        assert worker2._open.get(instrument_id, Decimal("0")) > 0, "readopta la posición"
        assert report2 is not None and report2.opened == 0, "no re-abre (señal consumida)"

        plan2 = worker2._v2_positions.get(instrument_id)
        assert plan2 is not None, "la posición sigue gestionada por AUTO 2.0"
        assert plan2.trade_plan_id == plan1.trade_plan_id, (
            "el plan durable se REHIDRATA (no se reconstruye por ATR)"
        )
        assert plan2.current_stop == plan1.current_stop
        assert worker2._v2_consumed_signals == consumed1, (
            "el dedupe de la barra sobrevive al reinicio (no re-emite la señal)"
        )
    finally:
        if account_id is not None:
            from bolsa_infrastructure.database.models.tables import (
                SimAutoPositionRow,
                SimConsumedSignalRow,
            )

            async with v2_pg_factory() as session:
                from sqlalchemy import delete

                await session.execute(
                    delete(SimAutoPositionRow).where(SimAutoPositionRow.account_id == account_id)
                )
                await session.execute(
                    delete(SimConsumedSignalRow).where(
                        SimConsumedSignalRow.account_id == account_id
                    )
                )
                await session.commit()
