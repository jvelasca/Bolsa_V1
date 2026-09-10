"""V2.24 / A9.1 (P2-04) — Reina REAL: proceso scheduler + spine determinista real.

A diferencia de ``test_auto_scheduler_real_pg_zero_human_intervention`` (que llama
``runtime.run_tick()`` directamente y usa un decider scripteado), este test arranca
el **proceso real** ``python -m bolsa_api.workers.scheduler_worker`` —con su gate de
env y su ``auto_sim_loop`` periódico— sobre PostgreSQL real, y deja que el propio
scheduler conduzca el día AUTO con el **Decision Spine determinista** (sin humano,
sin ``run_tick`` manual, sin ``_ScriptDecider``).

Gobierno de honestidad (patrón del repo): sin PostgreSQL real/credenciales hace
``pytest.skip``; con ``AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1`` un skip silencioso es
un FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import subprocess  # noqa: S404 — proceso real del scheduler (objeto del test).
import sys
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"
_REQUIRED_ENV = "AUTO_SCHEDULER_PROCESS_PG_REQUIRED"
_TIMEOUT_S = 90.0


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(f"AUTO scheduler process PG requerido pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL/Alembic (proceso scheduler AUTO) no disponible: {exc}")


def _proc_failure(msg: str, log_path: Path) -> str:
    """Mensaje de fallo con la cola del log del proceso scheduler (diagnóstico)."""
    tail = ""
    try:
        if log_path.exists():
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
    except OSError:
        pass
    return f"{msg}\n--- scheduler log tail ---\n{tail}"


@pytest_asyncio.fixture
async def sched_process_factory() -> async_sessionmaker[AsyncSession]:
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


async def _count(factory: async_sessionmaker[AsyncSession], model: object) -> int:
    async with factory() as session:
        return int(
            (await session.execute(select(func.count()).select_from(model))).scalar() or 0
        )


async def _count_scoped_ticks(
    factory: async_sessionmaker[AsyncSession], engine_id: str
) -> int:
    from bolsa_infrastructure.database.models.tables import AutoEngineTickRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(AutoEngineTickRow)
                    .where(AutoEngineTickRow.engine_id == engine_id)
                )
            ).scalar()
            or 0
        )


async def _count_scoped_events(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> int:
    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(ExecutionEventRow)
                    .where(ExecutionEventRow.account_id == account_id)
                )
            ).scalar()
            or 0
        )


async def _count_scoped_ledger(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> int:
    from bolsa_infrastructure.database.models.tables import LedgerEntryRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(LedgerEntryRow)
                    .where(LedgerEntryRow.account_id == account_id)
                )
            ).scalar()
            or 0
        )


async def _assert_equity_invariant(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> None:
    """V2.24.2 (P2-A): «assert_equity_invariant» sobre el ledger REAL, no tautológico.

    A diferencia de A9.1 (que pasaba ``last_price=0``/``avg_cost=0``/``realized_pnl=0``
    y dejaba la invariante reducida a ``cash == cash``), aquí se reconstruye la
    contabilidad desde las filas reales del ledger (depósitos, compras, ventas,
    fees) y desde la posición abierta canónica (coste medio y precio actual), de
    modo que ``total_equity == initial + realized + unrealized`` es una afirmación
    financiera de verdad.
    """
    from bolsa_application.auto_daily_journal import (
        LedgerCashMovement,
        reconstruct_accounting_from_state,
    )
    from bolsa_domain.lifecycle import assert_equity_invariant
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.position_state_repository import (
        SqlAlchemyPositionStateRepository,
    )

    async with factory() as session:
        entries = await SqlAlchemyLedgerRepository(session).list_for_account(
            account_id, limit=None
        )
        open_positions = await SqlAlchemyPositionStateRepository(session).list_open_for_account(
            account_id
        )
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
                # Precio plano determinista del día AUTO (price_script default).
                last_price = Decimal(str(price))
        avg_cost = (cost_basis / remaining) if remaining != 0 else Decimal("0")
        if remaining != 0 and last_price == 0:
            last_price = avg_cost
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
            closed_pnl=Decimal("0"),
        )
        assert_equity_invariant(accounting)


@pytest.mark.asyncio
async def test_a9_scheduler_process_full_day_pg_zero_human(
    sched_process_factory: async_sessionmaker[AsyncSession],
) -> None:
    """El proceso scheduler real conduce BUY→HOLD→SELL de un día AUTO (P2-04).

    Config: ``AUTO_SIMULATION_WORKER_ENABLED=1`` + ``AUTO_ENGINE_SIM_SPINE_AUTO=1`` +
    cuenta SIM inequívoca + venue ``simulated`` + intervalo corto. Sin HTTP, sin UI,
    sin ``run_tick()`` manual, sin decider scripteado. Se comprueba que el scheduler,
    por sí solo, produce ticks/fills/ledger y deja el libro plano.
    """

    instrument_id = f"inst-a9proc-{uuid.uuid4().hex[:10]}"
    engine_id = f"auto-a9proc-{uuid.uuid4().hex[:8]}"
    account_id: str | None = None
    log_path = Path(tempfile.gettempdir()) / f"a9proc-{engine_id}.log"

    # Semilla: cuenta SIM + instrumento + watch + cuenta en el env del proceso.
    async with sched_process_factory() as session:
        from datetime import UTC, datetime

        from bolsa_infrastructure.database.models.tables import InstrumentRow
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )

        account_id = (
            await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=f"AUTO-A9PROC-{uuid.uuid4().hex[:8]}",
                initial_deposit=100_000.0,
            )
        ).account.id
        session.add(
            InstrumentRow(
                id=instrument_id,
                symbol=f"A9{uuid.uuid4().hex[:6].upper()}",
                yahoo_symbol=f"A9{uuid.uuid4().hex[:8]}",
                isin=None,
                name="A9-Proc",
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

    env = os.environ.copy()
    env.update(
        {
            "AUTO_SIMULATION_WORKER_ENABLED": "1",
            "AUTO_ENGINE_SIM_SPINE_AUTO": "1",
            "AUTO_ENGINE_SIM_ACCOUNT_ID": account_id,
            "AUTO_ENGINE_SIM_ENGINE_ID": engine_id,
            "AUTO_ENGINE_SIMULATED_VENUE": "simulated",
            "AUTO_ENGINE_SIMULATED_WATCH": instrument_id,
            "AUTO_ENGINE_SIM_INTERVAL_SECONDS": "1.0",
            "AUTO_ENGINE_SIM_LOT_QTY": "100",
            "PYTHONUNBUFFERED": "1",
        }
    )

    proc = subprocess.Popen(  # noqa: S603 — comando fijo del repo.
        [sys.executable, "-m", "bolsa_api.workers.scheduler_worker"],
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=open(log_path, "w", encoding="utf-8"),  # noqa: SIM115 — cerrado abajo.
        stderr=subprocess.STDOUT,
    )
    try:
        # Deja correr el proceso el tiempo suficiente para varios ticks (BUY→…→SELL).
        # Todo se cuenta SCOPED a este engine_id/cuenta (nunca global): un día AUTO
        # solo es válido si ESTE proceso produjo SUS ticks/fills/ledger.
        ticks = events = ledger = 0
        for _ in range(int(_TIMEOUT_S * 2)):
            await asyncio.sleep(0.5)
            ticks = await _count_scoped_ticks(sched_process_factory, engine_id)
            events = await _count_scoped_events(sched_process_factory, account_id)
            ledger = await _count_scoped_ledger(sched_process_factory, account_id)
            if ticks >= 3 and events >= 2 and ledger >= 2:
                break
        assert ticks > 0, _proc_failure("el proceso scheduler debe persistir SUS ticks", log_path)
        assert events > 0, _proc_failure("el día AUTO del proceso debe tener ExecutionEvents", log_path)
        assert ledger > 0, _proc_failure("el día AUTO del proceso debe mover el ledger real", log_path)

        # Zero human / zero LIVE: ninguna traza de ESTA cuenta con venue live.
        from bolsa_infrastructure.database.models.tables import ExecutionEventRow as EvRow

        async with sched_process_factory() as session:
            bad = (
                await session.execute(
                    select(func.count())
                    .select_from(EvRow)
                    .where(
                        EvRow.account_id == account_id,
                        func.lower(EvRow.venue).in_(
                            ("live", "broker_live", "xtb", "real", "live_bridge")
                        ),
                    )
                )
            ).scalar()
        assert int(bad or 0) == 0, "el proceso AUTO no debe publicar al bridge LIVE"

        # V2.24/A9.1 (P2-05): invariante de equity sobre el ledger REAL del día AUTO.
        if os.environ.get("AUTO_EQUITY_INVARIANT_PG_REQUIRED") == "1":
            await _assert_equity_invariant(sched_process_factory, account_id)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        try:
            if proc.stdout is not None:
                proc.stdout.close()
        except OSError:
            pass

    # Cleanup.
    if account_id:
        from sqlalchemy import delete

        from bolsa_infrastructure.database.models.tables import (
            InstrumentRow,
        )
        from bolsa_infrastructure.database.models.tables import (
            SimAutoPositionRow as PosRow,
        )
        from bolsa_infrastructure.database.models.tables import (
            SimFillFinanceContextRow as CtxRow,
        )
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )

        async with sched_process_factory() as session:
            await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
            await session.execute(delete(PosRow).where(PosRow.account_id == account_id))
            await session.execute(
                delete(CtxRow).where(CtxRow.account_id == account_id)
            )
            try:
                await SqlAlchemyAccountRepository(session).close_account(account_id)
            except Exception:  # noqa: BLE001 — cleanup nunca tira el test
                pass
            await session.commit()


# ── V2.24.2 (P2-D): restart REAL del proceso con posición + protección abierta ────


async def _scoped_buy_fills(
    factory: async_sessionmaker[AsyncSession], account_id: str
) -> int:
    """ExecutionEvents BUY de la cuenta (para probar que el restart no re-compró).

    ``execution_events`` no tiene columna ``side``; el lado va embebido en
    ``venue_order_id`` (``sim-{engine}-{acct}-{side}-...``, P1-03), así que se filtra
    por ese patrón, scoped a la cuenta.
    """
    from bolsa_infrastructure.database.models.tables import ExecutionEventRow

    async with factory() as session:
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(ExecutionEventRow)
                    .where(
                        ExecutionEventRow.account_id == account_id,
                        ExecutionEventRow.venue_order_id.like("%-buy-%"),
                    )
                )
            ).scalar()
            or 0
        )


@pytest.mark.asyncio
async def test_a9_scheduler_process_restart_with_open_protected_position_pg(
    sched_process_factory: async_sessionmaker[AsyncSession],
) -> None:
    """V2.24.2 (P2-D): el proceso scheduler se reinicia con posición ABIERTA.

    A diferencia del restart de A9.1 (a mitad de jornada, sin garantizar protección
    activa), aquí la posición queda abierta al matar el proceso con su estado de
    protección ya persistido. Tras el reinicio del MISMO engine el proceso debe
    readoptar la posición durable: NO vuelve a comprar (los BUY no se doblan) y la
    fila de proyección sigue presente. Sin PostgreSQL real/credenciales hace skip;
    con ``AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1`` un skip es FALLO duro. NUNCA LIVE.
    """
    from bolsa_infrastructure.database.models.tables import SimAutoPositionRow as PosRow

    instrument_id = f"inst-a9restart-{uuid.uuid4().hex[:10]}"
    engine_id = f"auto-a9restart-{uuid.uuid4().hex[:8]}"
    account_id: str | None = None
    log_path = Path(tempfile.gettempdir()) / f"a9restart-{engine_id}.log"

    async with sched_process_factory() as session:
        from datetime import UTC, datetime

        from bolsa_infrastructure.database.models.tables import InstrumentRow
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )

        account_id = (
            await SqlAlchemyAccountRepository(session).create_simulated_account(
                name=f"AUTO-A9RESTART-{uuid.uuid4().hex[:8]}",
                initial_deposit=100_000.0,
            )
        ).account.id
        session.add(
            InstrumentRow(
                id=instrument_id,
                symbol=f"R9{uuid.uuid4().hex[:6].upper()}",
                yahoo_symbol=f"R9{uuid.uuid4().hex[:8]}",
                isin=None,
                name="A9-Restart",
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

    env = os.environ.copy()
    env.update(
        {
            "AUTO_SIMULATION_WORKER_ENABLED": "1",
            "AUTO_ENGINE_SIM_SPINE_AUTO": "1",
            "AUTO_ENGINE_SIM_ACCOUNT_ID": account_id,
            "AUTO_ENGINE_SIM_ENGINE_ID": engine_id,
            "AUTO_ENGINE_SIMULATED_VENUE": "simulated",
            "AUTO_ENGINE_SIMULATED_WATCH": instrument_id,
            "AUTO_ENGINE_SIM_INTERVAL_SECONDS": "1.0",
            "AUTO_ENGINE_SIM_LOT_QTY": "100",
            # Retén largo: la posición debe seguir ABIERTA cuando matemos el proceso.
            "AUTO_ENGINE_SIM_EXIT_AFTER_TICKS": "1000",
            "PYTHONUNBUFFERED": "1",
        }
    )

    def _spawn() -> subprocess.Popen[bytes]:
        return subprocess.Popen(  # noqa: S603 — comando fijo del repo.
            [sys.executable, "-m", "bolsa_api.workers.scheduler_worker"],
            cwd=str(_REPO_ROOT),
            env=env,
            stdout=open(log_path, "a", encoding="utf-8"),  # noqa: SIM115 — cerrado abajo.
            stderr=subprocess.STDOUT,
        )

    async def _stop(proc: subprocess.Popen[bytes]) -> None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        try:
            if proc.stdout is not None:
                proc.stdout.close()
        except OSError:
            pass

    proc = _spawn()
    try:
        # Espera a que el proceso abra una posición (BUY durable) antes de matarlo.
        buys_before = 0
        for _ in range(int(_TIMEOUT_S * 2)):
            await asyncio.sleep(0.5)
            buys_before = await _scoped_buy_fills(sched_process_factory, account_id)
            if buys_before > 0:
                break
        assert buys_before > 0, _proc_failure(
            "el proceso debe abrir (BUY durable) antes del restart", log_path
        )

        # Crash + restart del MISMO engine sobre la MISMA BD.
        await _stop(proc)
        proc = _spawn()

        # El restart debe readoptar (NO re-comprar): los BUY no se doblan.
        buys_after = buys_before
        for _ in range(int(_TIMEOUT_S * 2)):
            await asyncio.sleep(0.5)
            buys_after = await _scoped_buy_fills(sched_process_factory, account_id)
            if buys_after > buys_before:
                break  # re-compra detectada: falla abajo con diagnóstico.
        assert buys_after == buys_before, _proc_failure(
            "el restart con posición abierta NO debe re-comprar (readopción durable)",
            log_path,
        )
    finally:
        await _stop(proc)

    # Cleanup.
    if account_id:
        from sqlalchemy import delete

        from bolsa_infrastructure.database.models.tables import (
            InstrumentRow,
        )
        from bolsa_infrastructure.database.models.tables import (
            SimFillFinanceContextRow as CtxRow,
        )
        from bolsa_infrastructure.database.repositories.account_repository import (
            SqlAlchemyAccountRepository,
        )

        async with sched_process_factory() as session:
            await session.execute(delete(InstrumentRow).where(InstrumentRow.id == instrument_id))
            await session.execute(delete(PosRow).where(PosRow.account_id == account_id))
            await session.execute(delete(CtxRow).where(CtxRow.account_id == account_id))
            try:
                await SqlAlchemyAccountRepository(session).close_account(account_id)
            except Exception:  # noqa: BLE001 — cleanup nunca tira el test
                pass
            await session.commit()
