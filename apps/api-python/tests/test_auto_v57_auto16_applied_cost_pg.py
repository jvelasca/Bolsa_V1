"""AUTO-16 (V2.57) — la REFERENCIA del fill y la fricción APLICADA, contra PostgreSQL real.

Qué certifica este fichero, y por qué SOLO se puede certificar contra PostgreSQL real:

1. **La migración 046 es aditiva y reversible** — ``downgrade`` a ``045_adaptive_gate_state``
   retira ``reference_mid``; ``upgrade head`` la recrea. Sin roundtrip, "reversible" sería una
   lectura del código, no un hecho medido.
2. **La referencia SOBREVIVE al reinicio y la fricción se recomputa fuera del proceso que la
   midió** — la sesión 1 liquida la ida y la vuelta (con sus mids); la sesión 2, NUEVA, lee el
   ciclo por ``list_by_cycle_ids`` y recompone la fricción aplicada de las DOS patas. Es la
   ventana que cierra la fase: la pata de ENTRADA se liquidó en otro tick y su mid viajaba en
   una variable que se tiraba.
3. **Una fila anterior a ``2.57`` se declara sin referencia, jamás con un ``0``** — la columna
   es ``NULL`` y el ciclo queda **sin** fricción aplicada (nunca "fricción gratis", que
   regalaría R): se mide el hecho de que la referencia no se midió.
4. **La lectura por ciclo no cruza cuentas** — un ciclo es de UNA cuenta: una fila de otra
   cuenta con el mismo ``cycle_id`` no puede aportar la fricción de este ciclo.

GOBIERNO DE HONESTIDAD (patrón del repo): sin PostgreSQL real hace ``pytest.skip``; con
``APPLIED_COST_PG_REQUIRED=1`` un skip silencioso es un FALLO duro. NUNCA abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_REQUIRED_ENV = "APPLIED_COST_PG_REQUIRED"
_PREVIOUS_REVISION = "045_adaptive_gate_state"
_FILL_TABLE = "sim_fill_finance_context"
_COLUMN = "reference_mid"
_HEAD = "046_fill_reference_mid"
_CYCLE = "cyc-auto16"
_VERSION = "orb-16"
#: La ida y la vuelta de un mismo ciclo: 1.5 de fricción en la compra y 1.0 en la venta.
_BUY_PRICE = "100.15"
_BUY_REFERENCE = "100"
_SELL_PRICE = "129.90"
_SELL_REFERENCE = "130"
_EXPECTED_FRICTION = Decimal("2.500000")


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_REQUIRED_ENV) == "1":
        raise AssertionError(
            f"PostgreSQL requerido para la fricción aplicada (AUTO-16) "
            f"pero no disponible: {exc}"
        ) from exc
    pytest.skip(f"PostgreSQL/Alembic (fricción aplicada AUTO-16) no disponible: {exc}")


@pytest_asyncio.fixture
async def fills_pg_factory() -> async_sessionmaker[AsyncSession]:
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


async def _cleanup(
    factory: async_sessionmaker[AsyncSession], *accounts: str
) -> None:
    from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

    async with factory() as session:
        for account_id in accounts:
            await session.execute(
                delete(SimFillFinanceContextRow).where(
                    SimFillFinanceContextRow.account_id == account_id
                )
            )
        await session.commit()


def _fill(
    side: str,
    price: str,
    reference: str | None,
    *,
    execution_id: str,
    account_id: str,
    cycle_id: str | None = _CYCLE,
) -> Any:
    from bolsa_application.sim_durable_store import SimFillFinanceContext

    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal("10"),
        price=Decimal(price),
        reference_mid=reference,
        account_id=account_id,
        strategy_version_id=_VERSION,
        cycle_id=cycle_id,
    )


def _round_trip(account_id: str, *, reference: tuple[str, str] | None) -> tuple[Any, ...]:
    buy_reference, sell_reference = reference if reference is not None else (None, None)
    return (
        _fill("buy", _BUY_PRICE, buy_reference, execution_id="e1", account_id=account_id),
        _fill("sell", _SELL_PRICE, sell_reference, execution_id="e2", account_id=account_id),
    )


# ── 1) La migración 046 es aditiva y reversible ───────────────────────────────────


@pytest.mark.asyncio
async def test_migration_046_roundtrip_creates_and_drops_the_reference(
    fills_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``downgrade`` a 045 retira ``reference_mid``; ``upgrade head`` la recrea."""
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
        assert alembic_head() == _HEAD, "la guardia de la head tiene que apuntar a la 046"
        with engine.connect() as connection:
            assert _column_present(connection, _FILL_TABLE, _COLUMN), (
                "046 debe añadir la referencia del fill"
            )

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.downgrade(cfg, _PREVIOUS_REVISION)
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            assert not _column_present(connection, _FILL_TABLE, _COLUMN), (
                "downgrade retira la columna (symmetric)"
            )

        with engine.connect() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
            cfg.attributes.pop("connection", None)

        with engine.connect() as connection:
            assert _column_present(connection, _FILL_TABLE, _COLUMN), "upgrade la recrea"
    finally:
        engine.dispose()


# ── 2) La referencia sobrevive al reinicio y la fricción se recomputa ───────────────


@pytest.mark.asyncio
async def test_the_reference_survives_the_restart_and_the_friction_is_recomputed(
    fills_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """La sesión 2, NUEVA, recompone la fricción de las DOS patas leyendo el ciclo."""
    from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE
    from bolsa_application.applied_cost import applied_cost_from_fills
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

    account_id = f"acc-applied-{uuid.uuid4().hex[:10]}"
    try:
        # Sesión 1: el settlement liquida la ida y la vuelta (una por tick, con su mid).
        async with fills_pg_factory() as session:
            store = PostgresSimFillFinanceContextStore(session)
            for fill in _round_trip(account_id, reference=(_BUY_REFERENCE, _SELL_REFERENCE)):
                await store.save(fill)

        # Sesión 2 (reinicio de verdad): el ciclo se lee por ``cycle_id`` y se mide.
        async with fills_pg_factory() as session:
            store = PostgresSimFillFinanceContextStore(session)
            fills = await store.list_by_cycle_ids(account_id, [_CYCLE])

            assert [fill.execution_id for fill in fills] == ["e1", "e2"]
            assert [fill.reference_mid for fill in fills] == [
                Decimal("100.000000"),
                Decimal("130.000000"),
            ]
            applied = applied_cost_from_fills([_CYCLE], fills)[_CYCLE]

            assert applied.measurement == MEASUREMENT_COMPLETE
            assert applied.legs == 2
            assert applied.friction == _EXPECTED_FRICTION
    finally:
        await _cleanup(fills_pg_factory, account_id)


@pytest.mark.asyncio
async def test_the_applied_friction_of_a_restart_reaches_the_assessment(
    fills_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """El hecho durable llega al neto: la base ``applied`` no viaja sin medición detrás."""
    from bolsa_analytics.cognitive.auto_self_evaluation import SELF_EVAL_COST_BASIS_APPLIED
    from bolsa_analytics.cognitive.measurement import MEASUREMENT_COMPLETE
    from bolsa_analytics.cognitive.portfolio_reservation import (
        PortfolioReservation,
        TradingCost,
    )
    from bolsa_application.auto_self_evaluation_feed import build_auto_self_evaluation
    from bolsa_application.cycle_risk import cycle_risk_from_reservations
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

    account_id = f"acc-report-{uuid.uuid4().hex[:10]}"
    try:
        async with fills_pg_factory() as session:
            store = PostgresSimFillFinanceContextStore(session)
            for fill in _round_trip(account_id, reference=(_BUY_REFERENCE, _SELL_REFERENCE)):
                await store.save(fill)

        async with fills_pg_factory() as session:
            fills = await PostgresSimFillFinanceContextStore(session).list_by_cycle_ids(
                account_id, [_CYCLE]
            )

        risk = cycle_risk_from_reservations(
            [_CYCLE],
            (
                PortfolioReservation(
                    reservation_id="res-1",
                    account_id=account_id,
                    instrument_id="AAA",
                    side="buy",
                    quantity=10.0,
                    entry=100.0,
                    stop=95.0,
                    reserved_cash=1000.0,
                    reserved_risk=250.0,
                    cost=TradingCost(
                        notional=1000.0,
                        commission=5.0,
                        spread=4.0,
                        slippage=3.5,
                        gap=0.0,
                        total=25.0,
                        measurement=MEASUREMENT_COMPLETE,
                    ),
                    created_at="2026-09-22T08:00:00+00:00",
                    cycle_id=_CYCLE,
                ),
            ),
        )
        report = build_auto_self_evaluation(
            fills=fills, min_trades=1, cycle_risk=risk
        ).by_strategy[0]

        assert report.net_r_basis == SELF_EVAL_COST_BASIS_APPLIED
        assert report.net_r_measurement == MEASUREMENT_COMPLETE
        # pnl = 10 × (129.90 − 100.15) = 297.5; aplicado = 2.5 + comisión del modelo 5.0
        # ⇒ (297.5 − 2.5 − 5.0) / 250
        assert report.net_expectancy_r == pytest.approx(1.16)
    finally:
        await _cleanup(fills_pg_factory, account_id)


# ── 3) Una fila anterior a 2.57 se declara sin referencia, jamás con un 0 ──────────


@pytest.mark.asyncio
async def test_a_row_without_reference_is_declared_and_never_reads_as_zero(
    fills_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """``NULL`` es un HECHO ("no se midió"): la fricción aplicada queda sin medir, no en cero."""
    from bolsa_analytics.cognitive.measurement import MEASUREMENT_UNKNOWN
    from bolsa_application.applied_cost import applied_cost_from_fills
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

    account_id = f"acc-legacy-{uuid.uuid4().hex[:10]}"
    try:
        async with fills_pg_factory() as session:
            store = PostgresSimFillFinanceContextStore(session)
            for fill in _round_trip(account_id, reference=None):
                await store.save(fill)

        async with fills_pg_factory() as session:
            fills = await PostgresSimFillFinanceContextStore(session).list_by_cycle_ids(
                account_id, [_CYCLE]
            )

            assert [fill.reference_mid for fill in fills] == [None, None]
            applied = applied_cost_from_fills([_CYCLE], fills)[_CYCLE]

            assert applied.friction is None
            assert applied.friction != 0, "una referencia ausente nunca vale fricción cero"
            assert applied.measurement == MEASUREMENT_UNKNOWN
    finally:
        await _cleanup(fills_pg_factory, account_id)


# ── 4) La lectura por ciclo no cruza cuentas ───────────────────────────────────────


@pytest.mark.asyncio
async def test_the_cycle_read_does_not_cross_accounts(
    fills_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Un ciclo es de UNA cuenta: la fila de otra cuenta no aporta la fricción de este ciclo."""
    from bolsa_application.applied_cost import applied_cost_from_fills
    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

    account_id = f"acc-mine-{uuid.uuid4().hex[:10]}"
    other_account = f"acc-other-{uuid.uuid4().hex[:10]}"
    try:
        async with fills_pg_factory() as session:
            store = PostgresSimFillFinanceContextStore(session)
            for fill in _round_trip(account_id, reference=(_BUY_REFERENCE, _SELL_REFERENCE)):
                await store.save(fill)
            # La OTRA cuenta declara el MISMO ``cycle_id`` (una fila no debe cruzar el muro).
            # Con otro ``execution_id``: el id del fill es identidad GLOBAL (primary key), así
            # que la colisión no es la que se prueba aquí, sino el alcance de la lectura.
            await store.save(
                _fill(
                    "sell",
                    "90.00",
                    "95",
                    execution_id="e-other",
                    account_id=other_account,
                )
            )

        async with fills_pg_factory() as session:
            store = PostgresSimFillFinanceContextStore(session)
            mine = await store.list_by_cycle_ids(account_id, [_CYCLE])
            theirs = await store.list_by_cycle_ids(other_account, [_CYCLE])

            assert [fill.account_id for fill in mine] == [account_id, account_id]
            assert [fill.execution_id for fill in theirs] == ["e-other"]
            assert applied_cost_from_fills([_CYCLE], mine)[_CYCLE].friction == _EXPECTED_FRICTION, (
                "la ida y la vuelta de MI cuenta son las que miden mi ciclo"
            )
    finally:
        await _cleanup(fills_pg_factory, account_id, other_account)
