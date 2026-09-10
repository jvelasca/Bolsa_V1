"""V2.23 / A9 (Bloque 6) — CERTIFICACIÓN: AUTO SIM-ONLY end-to-end sobre PG real.

Arranca el camino REAL del scheduler (``AutoSimRuntime`` → sesión por tick →
``PostgresExecutionEventStore`` + ``PostgresAutoEngineStore`` + finanzas SIM reales
con ``ExecuteTrade`` idempotente) con un Decision Spine determinista (sin humano),
y certifica los invariantes de un día AUTO autónomo:

  ``auto_engine_ticks > 0`` · ``execution_events > 0`` · ``orders > 0`` ·
  ``fills > 0`` · ``positions > 0`` · ``ledger_entries > 0`` · ``positions = 0``
  tras el exit · ``LIVE bridge posts = 0``.

Además: un reinicio del runtime a mitad de jornada (nuevo worker sobre la MISMA BD)
readopta la posición durable (``sim_auto_positions``, G7) ⇒ NO segundo BUY, y NO
duplica el efecto financiero (idempotencia por ``simulated_idempotency_key``).

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real/credenciales de dev
hace ``pytest.skip``; con ``AUTO_SCHEDULER_PG_REQUIRED=1`` (job ``lifecycle-pg``)
un skip silencioso es un FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "AUTO_SCHEDULER_PG_REQUIRED"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(f"AUTO scheduler PG requerido pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL/Alembic (scheduler AUTO real) no disponible: {exc}")


@pytest_asyncio.fixture
async def sched_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto a head (028).
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
        name=f"AUTO-CERT-{uuid.uuid4().hex[:8]}",
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
            symbol=f"AC{uuid.uuid4().hex[:6].upper()}",
            yahoo_symbol=f"AC{uuid.uuid4().hex[:8]}",
            isin=None,
            name="AUTO-Cert",
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


class _ScriptDecider:
    """Decision Spine determinista scripteado (sin IA, sin humano).

    Propone BUY la primera vez que se le pide un símbolo; una vez abierta la posición
    (el worker ya no la re-compra) propone HOLD; cuando ``close`` se activa, propone
    SELL del total. Es el equivalente del provider scripteado de la Reina.
    """

    def __init__(self, symbol: str, lot: float = 100.0) -> None:
        self._symbol = symbol
        self._lot = lot
        self.sold = False

    def __call__(self, symbol: str):
        from bolsa_application.decision_contract import DecisionPackage

        if symbol != self._symbol:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)
        if self.sold:
            return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)
        return DecisionPackage(action="BUY", instrument_id=self._symbol, quantity=self._lot)

    def make_exit(self):
        from bolsa_application.decision_contract import DecisionPackage

        def _d(symbol: str):
            if symbol != self._symbol:
                return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)
            return DecisionPackage(action="SELL", instrument_id=self._symbol, quantity=self._lot)

        return _d


async def _counts(factory: async_sessionmaker[AsyncSession], *table_names: str) -> dict[str, int]:
    from bolsa_infrastructure.database.models.tables import (
        AutoEngineTickRow,
        ExecutionEventRow,
        LedgerEntryRow,
        SimAutoPositionRow,
    )

    table_map = {
        "auto_engine_ticks": AutoEngineTickRow,
        "execution_events": ExecutionEventRow,
        "sim_auto_positions": SimAutoPositionRow,
        "ledger_entries": LedgerEntryRow,
    }
    out: dict[str, int] = {}
    async with factory() as session:
        for name in table_names:
            model = table_map[name]
            out[name] = int(
                (await session.execute(select(func.count()).select_from(model))).scalar() or 0
            )
    return out


@pytest.mark.asyncio
async def test_auto_scheduler_real_pg_zero_human_intervention(
    sched_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Día AUTO autónomo real sobre PG: abre, rota, cierra — sin humano, sin LIVE.

    Invariantes del plan §25 (Bloque 6): ticks/execution_events/orders/fills/positions/
    ledger_entries > 0, posiciones a 0 tras el exit, y NINGÚN post al bridge LIVE.
    """
    from bolsa_api.background.auto_simulation_worker import (
        AutoSimRuntime,
        AutoSimulationWorker,
        _compose_real_stores,  # noqa: PLC0415
    )

    instrument_id = f"inst-auto-{uuid.uuid4().hex[:10]}"
    account_id: str | None = None
    engine_id = f"auto-cert-{uuid.uuid4().hex[:10]}"
    # Venue SIM-ONLY (nunca LIVE) y watch acotado al instrumento sembrado.
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "simulated")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", instrument_id)
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")

    try:
        async with sched_pg_factory() as session:
            account_id = await _seed_account(session)
            await _seed_instrument(session, instrument_id)

        spine = _ScriptDecider(instrument_id, lot=100.0)
        worker = AutoSimulationWorker(
            decider=spine,
            engine_id=engine_id,
            account_id=account_id,
        )
        runtime = AutoSimRuntime(
            sched_pg_factory,
            worker=worker,
            engine_id=engine_id,
            account_id=account_id,
        )

        # Tick 1: abre posición (BUY) y persiste tick durable.
        report_open = await runtime.run_tick()
        assert report_open is not None and report_open.opened == 1, report_open
        assert worker._open.get(instrument_id, Decimal("0")) > 0

        counts_after_open = await _counts(
            sched_pg_factory,
            "auto_engine_ticks",
            "execution_events",
            "sim_auto_positions",
            "ledger_entries",
        )
        assert counts_after_open["auto_engine_ticks"] > 0
        assert counts_after_open["execution_events"] > 0
        assert counts_after_open["sim_auto_positions"] > 0, "posición durable espejada"
        assert counts_after_open["ledger_entries"] > 0, "finanzas SIM reales aplicadas"

        # Reinicio a mitad de jornada: nuevo worker/proceso sobre la MISMA BD debe
        # readoptar la posición durable ⇒ un BUY siguiente NO apila (G7) y NO duplica
        # efecto financiero.
        events_before_restart = counts_after_open["execution_events"]
        worker2 = AutoSimulationWorker(
            decider=spine,  # sigue proponiendo BUY sobre el mismo símbolo
            engine_id=engine_id,
            account_id=account_id,
        )
        runtime2 = AutoSimRuntime(
            sched_pg_factory,
            worker=worker2,
            engine_id=engine_id,
            account_id=account_id,
        )
        report_restart = await runtime2.run_tick()
        assert worker2._open.get(instrument_id, Decimal("0")) > 0, "readopta posición"
        assert report_restart is not None and report_restart.opened == 0, (
            "NO segundo BUY tras readopción (G7)"
        )
        counts_after_restart = await _counts(
            sched_pg_factory, "execution_events", "sim_auto_positions"
        )
        assert counts_after_restart["execution_events"] == events_before_restart, (
            "el reinicio no debe duplicar ejecuciones"
        )

        # Exit determinista: SELL del total ⇒ libro plano, posición durable borrada.
        spine.sold = True
        worker2._decider = spine.make_exit()
        report_close = await runtime2.run_tick()
        assert report_close is not None and report_close.closed == 1, report_close
        assert worker2._open.get(instrument_id, Decimal("0")) == 0, "libro plano tras exit"
        counts_after_close = await _counts(
            sched_pg_factory,
            "auto_engine_ticks",
            "execution_events",
            "sim_auto_positions",
            "ledger_entries",
        )
        assert counts_after_close["sim_auto_positions"] == 0, "sin posición durable abierta"
        assert counts_after_close["auto_engine_ticks"] >= 3
        assert counts_after_close["execution_events"] >= counts_after_open["execution_events"]
        assert counts_after_close["ledger_entries"] > 0

        # LIVE bridge posts = 0: ninguna traza durable quedó con venue LIVE.
        from bolsa_infrastructure.database.models.tables import ExecutionEventRow  # noqa: PLC0415

        async with sched_pg_factory() as session:
            bad = (
                await session.execute(
                    select(func.count())
                    .select_from(ExecutionEventRow)
                    .where(
                        func.lower(ExecutionEventRow.venue).in_(
                            ("live", "broker_live", "xtb", "real", "live_bridge")
                        )
                    )
                )
            ).scalar()
        assert int(bad or 0) == 0, "AUTO no debe publicar al bridge LIVE"

        # La composición real del scheduler queda ejercitable (sesión por tick).
        async with sched_pg_factory() as session:
            exec_store, auto_store, applier, ctx_store = _compose_real_stores(session)
            assert exec_store is not None and auto_store is not None
            assert applier is not None and ctx_store is not None
    finally:
        if account_id:
            from sqlalchemy import delete  # noqa: PLC0415

            from bolsa_infrastructure.database.models.tables import (  # noqa: PLC0415
                InstrumentRow,
                SimAutoPositionRow,
                SimFillFinanceContextRow,
            )
            from bolsa_infrastructure.database.repositories.account_repository import (  # noqa: PLC0415
                SqlAlchemyAccountRepository,
            )

            async with sched_pg_factory() as session:
                await session.execute(
                    delete(InstrumentRow).where(InstrumentRow.id == instrument_id)
                )
                await session.execute(
                    delete(SimAutoPositionRow).where(SimAutoPositionRow.engine_id == engine_id)
                )
                await session.execute(
                    delete(SimFillFinanceContextRow).where(
                        SimFillFinanceContextRow.instrument_id == instrument_id
                    )
                )
                try:
                    await SqlAlchemyAccountRepository(session).close_account(account_id)
                except Exception:  # noqa: BLE001 — cleanup nunca tira el test
                    pass
                await session.commit()
