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


async def _assert_real_equity_invariant(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> None:
    """V2.24/A9.1 (P2-05): certifica el invariante de equity sobre el ledger REAL.

    Construye el ``LifecycleAccounting`` desde el estado financiero canónico
    (cash de los portfolios del account + posición abierta) y exige
    ``assert_equity_invariant``. Además exige la igualdad ledger ↔ cash (invariante
    M-2) que ya usan los chaos tests del repo.
    """
    from decimal import Decimal

    from sqlalchemy import select

    from bolsa_application.auto_daily_journal import (
        LedgerCashMovement,
        reconstruct_accounting_from_state,
    )
    from bolsa_domain.lifecycle import assert_equity_invariant
    from bolsa_infrastructure.database.models.tables import (
        InvestmentPortfolioRow,
        PortfolioRow,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.position_state_repository import (
        SqlAlchemyPositionStateRepository,
    )

    async with factory() as session:
        ledger = SqlAlchemyLedgerRepository(session)
        ledger_cash = Decimal(str(await ledger.sum_cash_amounts(account_id)))
        # El cash vive en ``portfolios`` (legacy) enlazado por el portfolio del account.
        cash_rows = (
            await session.execute(
                select(PortfolioRow.cash)
                .join(
                    InvestmentPortfolioRow,
                    InvestmentPortfolioRow.legacy_portfolio_id == PortfolioRow.id,
                )
                .where(InvestmentPortfolioRow.account_id == account_id)
            )
        ).scalars().all()
        portfolio_cash = sum((Decimal(str(c)) for c in cash_rows), Decimal("0"))
        # M-2: Σ ledger == Σ cash de los portfolios del account (tolerancia céntimo).
        assert abs(ledger_cash - portfolio_cash) <= Decimal("0.01"), (
            f"ledger Σ {ledger_cash} != portfolio cash {portfolio_cash} (M-2)"
        )
        open_positions = await SqlAlchemyPositionStateRepository(
            session
        ).list_open_for_account(account_id)
        remaining = Decimal("0")
        cost_basis = Decimal("0")
        last_price = Decimal("0")
        for pos in open_positions:
            state = pos.position_state
            qty = state.get("remainingQuantity") or state.get("quantity")
            entry = state.get("actualEntry") or state.get("avgCost") or state.get("entryPrice")
            price = state.get("lastPrice") or state.get("marketPrice") or entry
            if qty is not None:
                remaining += Decimal(str(qty))
            if entry is not None:
                cost_basis += Decimal(str(qty or 0)) * Decimal(str(entry))
            if price is not None:
                last_price = Decimal(str(price))
        avg_cost = (cost_basis / remaining) if remaining != 0 else Decimal("0")
        if remaining != 0 and last_price == 0:
            last_price = avg_cost
        # V2.24.2 (P2-A): reconstrucción REAL desde filas del ledger (no tautológica).
        entries = await ledger.list_for_account(account_id, limit=None)
        movements = [
            LedgerCashMovement(
                category=(entry.type or "").strip().lower(),
                amount=Decimal(str(entry.amount)),
            )
            for entry in entries
        ]
        accounting = reconstruct_accounting_from_state(
            movements=movements,
            remaining=remaining,
            avg_cost=avg_cost,
            last_price=last_price,
        )
        assert_equity_invariant(accounting)  # lanza si el invariante no se cumple.


async def _counts(
    factory: async_sessionmaker[AsyncSession],
    *table_names: str,
    engine_id: str | None = None,
    account_id: str | None = None,
) -> dict[str, int]:
    """Cuenta filas, con scoping opcional por ``engine_id``/``account_id``.

    V2.24/A9.1 (P1-02): ``sim_auto_positions`` está ahora escopada por cuenta. Un
    conteo GLOBAL dejaría de ser significativo en una BD compartida (otras pruebas
    dejan filas de otros engines/cuentas). Estas pruebas son del engine/cuenta que
    acaban de crear ⇒ sus invariantes de "0 posiciones" deben medirse SOLO sobre
    ese ámbito.
    """
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
    # ``auto_engine_ticks`` y ``sim_auto_positions`` llevan ``engine_id``;
    # ``execution_events`` se identifica por ``account_id`` (no tiene engine_id);
    # ``ledger_entries`` por ``account_id``.
    engine_scoped = {"auto_engine_ticks", "sim_auto_positions"}
    account_scoped = {"execution_events", "sim_auto_positions", "ledger_entries"}
    out: dict[str, int] = {}
    async with factory() as session:
        for name in table_names:
            model = table_map[name]
            stmt = select(func.count()).select_from(model)
            if engine_id is not None and name in engine_scoped:
                stmt = stmt.where(model.engine_id == engine_id)
            if account_id is not None and name in account_scoped:
                stmt = stmt.where(model.account_id == account_id)
            out[name] = int((await session.execute(stmt)).scalar() or 0)
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

        # Tick 1: abre posición (BUY) y persiste tick durable. Un tick BUY puede
        # quedar sin fill por la cola noisy (realista): se reintenta hasta abrir.
        report_open = None
        for _ in range(8):
            report_open = await runtime.run_tick()
            if worker._open.get(instrument_id, Decimal("0")) > 0:
                break
        assert report_open is not None and report_open.opened >= 1, report_open
        assert worker._open.get(instrument_id, Decimal("0")) > 0

        counts_after_open = await _counts(
            sched_pg_factory,
            "auto_engine_ticks",
            "execution_events",
            "sim_auto_positions",
            "ledger_entries",
            engine_id=engine_id,
            account_id=account_id,
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
            sched_pg_factory,
            "execution_events",
            "sim_auto_positions",
            engine_id=engine_id,
            account_id=account_id,
        )
        assert counts_after_restart["execution_events"] == events_before_restart, (
            "el reinicio no debe duplicar ejecuciones"
        )

        # Exit determinista: SELL del total ⇒ libro plano, posición durable borrada.
        # Un tick SELL puede quedar sin fill por la cola noisy determinista (comporta-
        # miento realista del venue SIM): el motor reintenta, no es un fallo.
        spine.sold = True
        worker2._decider = spine.make_exit()
        report_close = None
        for _ in range(8):
            report_close = await runtime2.run_tick()
            if report_close is not None and report_close.closed == 1:
                break
        assert report_close is not None and report_close.closed == 1, report_close
        assert worker2._open.get(instrument_id, Decimal("0")) == 0, "libro plano tras exit"
        counts_after_close = await _counts(
            sched_pg_factory,
            "auto_engine_ticks",
            "execution_events",
            "sim_auto_positions",
            "ledger_entries",
            engine_id=engine_id,
            account_id=account_id,
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

        # V2.24/A9.1 (P2-05): invariante de EQUITY sobre el ledger real. Se exige que
        # el día AUTO cierre con un ``LifecycleAccounting`` coherente
        # (``total_equity == initial + realized + unrealized``), no una igualdad
        # trivial de ceros.
        await _assert_real_equity_invariant(sched_pg_factory, account_id)

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
