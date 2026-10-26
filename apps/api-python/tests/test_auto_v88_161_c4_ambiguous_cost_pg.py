"""C-4 (auditoría .161) — coste ambiguo de una adopción contra PostgreSQL REAL.

El hallazgo C-4 no se puede certificar con dobles: la ambigüedad **existe** porque hay
más de una fila viva del mismo símbolo en ``sim_auto_positions`` (dos motores) y el
coste medio de la cuenta deja de identificar a ESTA fila. Este fichero lo mide con el
store y el lector canónico de PRODUCCIÓN sobre la base de datos real, y cubre los tres
escenarios del dictamen:

1. **Libro ambiguo CON espejo** — la adopción usa el espejo de ESTE motor
   (``projection_ambiguous_ledger``) y se declara degradada: el número no pretende ser
   el coste del libro.
2. **Libro ambiguo SIN espejo** — no se autoriza ningún coste (``ledger_ambiguous``):
   el hueco se declara con su motivo propio, distinto de ``cost_basis_missing``, y la
   fila durable NO se cura (no se inventa un precio).
3. **Plan durable frente a coste ausente/ambiguo** — un ``position_state`` persistido
   trae su PROPIA geometría y prevalece: no se declara hueco de coste ni se degrada un
   plan verificado.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real/credenciales el test hace
``pytest.skip``; con ``C4_AMBIGUOUS_COST_PG_REQUIRED=1`` un skip silencioso es un FALLO
duro. NUNCA abre el bridge LIVE (venue simulated).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, NamedTuple

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "C4_AMBIGUOUS_COST_PG_REQUIRED"

#: Precio del fill del libro canónico (el coste REAL de esta fila).
_LEDGER_ENTRY = Decimal("10.3335")
#: Precio del espejo del motor (``sim_auto_positions.entry_price``), distinto a propósito.
_MIRROR_ENTRY = Decimal("10.4")
#: Marca del tick de la adopción.
_MARK_PRICE = Decimal("10.42")


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para C-4 (coste ambiguo) pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (C-4 coste ambiguo) no disponible: {exc}")


@pytest_asyncio.fixture
async def c4_pg_factory() -> async_sessionmaker[AsyncSession]:
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


class _Case(NamedTuple):
    account_id: str
    symbol: str
    engine_id: str
    foreign_engine_id: str
    execution_id: str


def _durable_plan(symbol: str) -> dict[str, object]:
    """Plan operativo VERIFICADO con geometría propia (no depende del coste del libro)."""
    from bolsa_analytics.cognitive.position_state import build_position_state_from_fill

    plan = build_position_state_from_fill(
        {
            "decisionId": f"dec-durable-{symbol}",
            "instrumentId": symbol,
            "direction": "long",
            "status": "TRIGGERED",
            "entry": float(_LEDGER_ENTRY),
            "structuralStop": 9.8,
            "target1": 11.2,
            "target2": 12.0,
        },
        fill_price=float(_LEDGER_ENTRY),
        fill_quantity=100.0,
        filled_at="2026-09-09T09:00:00Z",
    )
    assert plan is not None
    return replace(plan, lifecycle_state="PROTECTED").to_dict()


async def _seed_case(
    factory: async_sessionmaker[AsyncSession],
    *,
    with_mirror: bool,
    with_plan: bool,
) -> _Case:
    """Siembra un caso C-4: DOS motores vivos + fill APPLIED (+ espejo/plan opcionales).

    Las dos filas con ``quantity > 0`` para el mismo ``(account_id, symbol)`` son lo que
    hace AMBIGUO el coste de la cuenta en la lectura real del store: sin ellas el test
    estaría midiendo un caso que el hallazgo no describe.
    """
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        SimAutoPositionRow,
        SimFillFinanceContextRow,
    )
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    suffix = uuid.uuid4().hex[:10]
    symbol = f"inst-c4-{suffix}"
    engine_id = f"auto-c4-{suffix}"
    foreign_engine_id = f"auto-c4-other-{suffix}"
    execution_id = f"ex-c4-{suffix}"
    now = datetime.now(UTC)

    async with factory() as session:
        scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
            name=f"C4-{suffix}",
            initial_deposit=100_000.0,
        )
        account_id = scope.account.id
        # Fila PROPIA: el espejo (``entry_price``) existe solo si el escenario lo pide y el
        # plan durable solo en el escenario 3. La ausencia se siembra como NULL, nunca como 0.
        session.add(
            SimAutoPositionRow(
                account_id=account_id,
                engine_id=engine_id,
                symbol=symbol,
                quantity=Decimal("100"),
                avg_price=_LEDGER_ENTRY,
                entry_price=_MIRROR_ENTRY if with_mirror else None,
                high_watermark=None,
                stop_price=None,
                t1_state=None,
                trailing_state=None,
                strategy_version_id=None,
                position_state=_durable_plan(symbol) if with_plan else None,
                opened_at=now,
                updated_at=now,
            )
        )
        # Fila AJENA del MISMO símbolo: el segundo motor vivo que vuelve ambiguo el coste
        # medio de la cuenta. No se toca en ninguna aserción: solo existe como hecho.
        session.add(
            SimAutoPositionRow(
                account_id=account_id,
                engine_id=foreign_engine_id,
                symbol=symbol,
                quantity=Decimal("100"),
                avg_price=Decimal("1933.3953"),
                entry_price=Decimal("1933.3953"),
                high_watermark=None,
                stop_price=None,
                t1_state=None,
                trailing_state=None,
                strategy_version_id=None,
                position_state=None,
                opened_at=now,
                updated_at=now,
            )
        )
        # El LIBRO canónico (fills APLICADOS + contexto financiero) es el hecho que
        # ``_canonical_entry_prices`` pliega: su coste es el de ESTA fila.
        session.add(
            ExecutionEventRow(
                execution_id=execution_id,
                order_id=f"ord-{execution_id}",
                venue="simulated",
                account_id=account_id,
                venue_order_id=f"sim-{execution_id}",
                fill_seq=1,
                qty=Decimal("100"),
                captured_at=now,
                status="APPLIED",
                applied_at=now,
                updated_at=now,
            )
        )
        session.add(
            SimFillFinanceContextRow(
                execution_id=execution_id,
                instrument_id=symbol,
                side="buy",
                quantity=Decimal("100"),
                price=_LEDGER_ENTRY,
                account_id=account_id,
                venue="simulated",
                created_at=now,
            )
        )
        await session.commit()

    return _Case(account_id, symbol, engine_id, foreign_engine_id, execution_id)


async def _cleanup(
    factory: async_sessionmaker[AsyncSession],
    case: _Case,
) -> None:
    from bolsa_infrastructure.database.models.tables import (
        ExecutionEventRow,
        SimAutoPositionRow,
        SimFillFinanceContextRow,
    )

    async with factory() as session:
        await session.execute(
            delete(SimAutoPositionRow).where(SimAutoPositionRow.account_id == case.account_id)
        )
        await session.execute(
            delete(SimFillFinanceContextRow).where(
                SimFillFinanceContextRow.execution_id == case.execution_id
            )
        )
        await session.execute(
            delete(ExecutionEventRow).where(ExecutionEventRow.execution_id == case.execution_id)
        )
        await session.commit()


def _worker(
    *,
    session: AsyncSession,
    engine_id: str,
    account_id: str,
):
    """Worker de PRODUCCIÓN sobre la sesión del test (store + lector canónico reales)."""
    from bolsa_application.sim_durable_store import PostgresSimAutoPositionStore

    from bolsa_api.background.auto_simulation_worker import (
        AutoSimulationWorker,
        _compose_canonical_reader,
        step_minute_clock,
    )

    _start, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    return AutoSimulationWorker(
        clock=clock,
        position_store=PostgresSimAutoPositionStore(session),
        canonical_positions_reader=_compose_canonical_reader(session),
        engine_id=engine_id,
        account_id=account_id,
    )


def _c4_env(monkeypatch: pytest.MonkeyPatch, symbol: str) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "simulated")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", symbol)
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2", "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


def _journal_detail(worker: Any, reason: str) -> list[dict[str, object]]:
    return [
        dict(entry.payload)
        for entry in worker._v2_position_journal_pending
        if entry.payload is not None and entry.payload.get("reason") == reason
    ]


@pytest.mark.asyncio
async def test_ambiguous_ledger_with_mirror_uses_the_engine_mirror(
    c4_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escenario 1 — libro ambiguo CON espejo: ``projection_ambiguous_ledger``.

    El coste de la cuenta no identifica la fila (dos motores vivos), así que el libro no
    autoriza el número; el único coste que pertenece a ESTA fila es el espejo del motor.
    La adopción se declara degradada: el nivel deja de fingir que es el coste del libro.
    """
    from bolsa_api.background.auto_simulation_worker import (
        ADOPTION_COST_SOURCE_PROJECTION_AMBIGUOUS_LEDGER,
    )

    case = await _seed_case(c4_pg_factory, with_mirror=True, with_plan=False)
    try:
        _c4_env(monkeypatch, case.symbol)
        async with c4_pg_factory() as session:
            worker = _worker(session=session, engine_id=case.engine_id, account_id=case.account_id)
            opened = await worker.readopt_positions()
            assert opened.get(case.symbol) == Decimal("100"), (
                "la readopción trae la posición de la fila PROPIA desde PG"
            )
            assert worker._entry_price[case.symbol] == _MIRROR_ENTRY, (
                "el espejo sale de sim_auto_positions.entry_price, no de RAM"
            )
            assert worker._canonical_entry_by_symbol[case.symbol] == _LEDGER_ENTRY, (
                "el libro canónico se pliega desde los fills APPLIED reales"
            )
            assert await worker._cost_basis_is_ambiguous(case.account_id, case.symbol) is True, (
                "dos motores vivos en PG hacen ambiguo el coste medio de la cuenta"
            )

            await worker._v2_position_package(case.symbol, _MARK_PRICE)

            position = worker._v2_positions.get(case.symbol)
            assert position is not None, "una adopción con coste ambiguo no deja la posición muda"
            assert position.current_stop is not None
            assert Decimal(str(position.current_stop)) < _MARK_PRICE, (
                "el stop sigue por debajo del mercado (no se liquida en el tick de adopción)"
            )
            assert position.lifecycle_state == "RECONCILIATION_REQUIRED", (
                "el nivel se declara: el coste usado no es el del libro"
            )
            assert position.trade_plan_id == f"adopted-{case.symbol}", (
                "sin plan durable, la geometría es la reconstruida"
            )

            holes = _journal_detail(worker, "cost_basis_ambiguous")
            assert holes, "el motivo viaja al journal con su nombre propio"
            assert holes[0]["entrySource"] == ADOPTION_COST_SOURCE_PROJECTION_AMBIGUOUS_LEDGER
            assert holes[0]["source"] == "reconstructed"
            assert holes[0]["entry"] == pytest.approx(float(_MIRROR_ENTRY)), (
                "el número declarado es el del espejo del motor, no el medio de la cuenta"
            )
    finally:
        await _cleanup(c4_pg_factory, case)


@pytest.mark.asyncio
async def test_ambiguous_ledger_without_mirror_invents_no_cost(
    c4_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escenario 2 — libro ambiguo SIN espejo: ``ledger_ambiguous``, sin coste inventado.

    Sin espejo no hay ningún número que pertenezca a esta fila: no se adopta, se declara
    el hueco con su motivo PROPIO (distinto de ``cost_basis_missing``) y la fila durable
    se queda como estaba (``entry_price`` NULL, cantidad intacta).
    """
    from bolsa_infrastructure.database.models.tables import SimAutoPositionRow

    from bolsa_api.background.auto_simulation_worker import (
        ADOPTION_COST_SOURCE_LEDGER_AMBIGUOUS,
    )

    case = await _seed_case(c4_pg_factory, with_mirror=False, with_plan=False)
    try:
        _c4_env(monkeypatch, case.symbol)
        async with c4_pg_factory() as session:
            worker = _worker(session=session, engine_id=case.engine_id, account_id=case.account_id)
            await worker.readopt_positions()
            assert case.symbol not in worker._entry_price, "sin espejo no hay coste de fila"
            assert await worker._cost_basis_is_ambiguous(case.account_id, case.symbol) is True

            package = await worker._v2_position_package(case.symbol, _MARK_PRICE)

            assert package is None
            assert case.symbol not in worker._v2_positions, (
                "sin coste autorizado no se inventa una posición gestionable"
            )
            holes = _journal_detail(worker, "cost_basis_ambiguous")
            assert holes, "el hueco de coste se declara con su motivo propio"
            assert holes[0]["entrySource"] == ADOPTION_COST_SOURCE_LEDGER_AMBIGUOUS
            assert holes[0]["source"] == "none"
            assert not _journal_detail(worker, "cost_basis_missing"), (
                "son huecos distintos: no se confunde ambiguo con ausente"
            )

        # La fila durable NO se curó: el coste de la cuenta no se escribió sobre ella.
        async with c4_pg_factory() as session:  # sesión NUEVA: lee lo DURABLE.
            row = (
                await session.execute(
                    select(SimAutoPositionRow).where(
                        SimAutoPositionRow.account_id == case.account_id,
                        SimAutoPositionRow.engine_id == case.engine_id,
                        SimAutoPositionRow.symbol == case.symbol,
                    )
                )
            ).scalar_one()
            assert row.entry_price is None, "no se inventa ni se cura un coste ambiguo"
            assert row.quantity == Decimal("100"), "la operación (cantidad) no se toca"
    finally:
        await _cleanup(c4_pg_factory, case)


@pytest.mark.asyncio
async def test_durable_plan_prevails_over_ambiguous_cost(
    c4_pg_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escenario 3 — el plan durable trae su geometría y prevalece sobre el coste.

    Con el libro ambiguo y sin espejo, un ``position_state`` persistido es suficiente:
    el plan manda en el CÓMO salir (stop/objetivos) y no se declara hueco de coste ni se
    degrada un plan verificado.
    """
    case = await _seed_case(c4_pg_factory, with_mirror=False, with_plan=True)
    try:
        _c4_env(monkeypatch, case.symbol)
        expected = _durable_plan(case.symbol)
        async with c4_pg_factory() as session:
            worker = _worker(session=session, engine_id=case.engine_id, account_id=case.account_id)
            await worker.readopt_positions()
            assert case.symbol in worker._v2_durable_plans, (
                "el plan persistido se rehidrata desde sim_auto_positions.position_state"
            )
            assert await worker._cost_basis_is_ambiguous(case.account_id, case.symbol) is True

            await worker._v2_position_package(case.symbol, _MARK_PRICE)

            position = worker._v2_positions.get(case.symbol)
            assert position is not None, "un plan durable no se descarta por coste ambiguo"
            assert position.trade_plan_id == expected["tradePlanId"]
            assert position.current_stop == pytest.approx(float(expected["currentStop"]))
            assert position.lifecycle_state == "PROTECTED", "no se degrada un plan verificado"
            assert not _journal_detail(worker, "cost_basis_ambiguous"), (
                "el plan trae su geometría: no hay hueco de coste que declarar"
            )
            assert case.symbol not in worker._v2_durable_plans, "el plan se consume una sola vez"
    finally:
        await _cleanup(c4_pg_factory, case)
