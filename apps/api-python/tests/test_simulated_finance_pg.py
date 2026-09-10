"""V2.22 / A9 (last gap) — Finance AUTO SIM-ONLY sobre PG real (GATE en vivo).

Cierra el tramo 1 de *Next steps* del relevo de A9: correr una jornada AUTO SIM-ONLY cuyo
settlement (``submit_simulated_order``/``apply_simulated_order_once``) materializa la
finance REAL de cada fill simulado vía ``ExecuteTrade`` idempotente por
``simulated_idempotency_key`` (Positions/Ledger/cash reales), reutilizando el tornillo
``build_simulated_execute_trade_applier`` de ``simulated_finance`` y el mapper puro
``resolve_execution_finance``.

GOBIERNO DE HONESTIDAD (patrón del repo): este test necesita una PostgreSQL real con el
esquema a la head de Alembic (incluye la migración ``027``) y credenciales que resuelvan
``DATABASE_URL``. Es GATE en vivo: sin credenciales/PG hace ``pytest.skip`` honesto,
salvo que se fuerce ``AUTO_M5_FIN_PG_REQUIRED=1`` (entonces FALLA — gatilla un job
real-PG del job dedicado `lifecycle-pg`). En una re-verificación local sin credenciales
de dev este test se salta; NO se reclama un verde en vivo que no se corrió.

A diferencia de la Reina hermética (que liquida con ``apply_finance=None`` y deja las
trazas ``CAPTURED`` sin dinero), aquí se inyecta un applier de finanzas real por fill:
cada ``execution_id`` materializa ExecuteTrade de la MISMA cuenta/cartera real
exactamente una vez (idempotencia por ``simulated_idempotency_key``) y su traza durable
llega a ``APPLIED``. Venue SIM-ONLY: se ejecuta sobre la cuenta simulada (``simulated``)
que ExecuteTrade ya toca; jamás se abre un bridge LIVE.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_DOTENV = Path(__file__).resolve().parents[3] / ".env"
_FIN_ENV_REQUIRED = "AUTO_M5_FIN_PG_REQUIRED"


def _require_or_skip(exc: Exception) -> None:
    if os.environ.get(_FIN_ENV_REQUIRED) == "1":
        raise AssertionError(f"AUTO M5 FIN PG requerido pero no disponible: {exc}") from exc
    pytest.skip(f"PostgreSQL/Alembic (finanzas AUTO real) no disponible: {exc}")


@pytest_asyncio.fixture
async def fin_pg_factory() -> async_sessionmaker[AsyncSession]:
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.migrations import ensure_migrated
    from bolsa_infrastructure.database.session import create_engine

    get_settings.cache_clear()
    settings = get_settings()
    try:
        await asyncio.to_thread(ensure_migrated)  # auto a head (incluye 027 fin de A9).
        engine = create_engine(settings)
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        _require_or_skip(exc)
        raise
    from bolsa_infrastructure.database.session import create_session_factory

    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_account_tag(session: AsyncSession) -> str:
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"FIN-AUTO-{uuid.uuid4().hex[:8]}",
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
            symbol=f"FA{uuid.uuid4().hex[:6].upper()}",
            yahoo_symbol=f"FA{uuid.uuid4().hex[:8]}",
            isin=None,
            name="FinAUTO-Seam",
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


def _finance_applier_for(
    session: AsyncSession, *, account_id: str, instrument_id: str, side: str, seed: int
):
    """Applier ExecuteTrade real por fill; mapper puro resuelve price sobre el schedule.

    El ``ExecutionEvent`` no lleva price/instrument/side (es contexto del order), así que
    lo resolvemos con ``resolve_execution_finance`` cerrado sobre el ``SimulatedOrderResult``
    determinista del settlement; el schedule es reproducible para los mismos inputs, por
    lo que el applier recupera el price/cantidad correctos SIN inventar (H4).
    """
    from decimal import Decimal

    from bolsa_application.accounts.trade import ExecuteTrade
    from bolsa_application.execution_event import ExecutionEvent
    from bolsa_application.simulated_broker import simulated_fill_schedule
    from bolsa_application.simulated_finance import (
        build_simulated_execute_trade_applier,
        resolve_execution_finance,
    )
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    schedule = simulated_fill_schedule(
        instrument_id=instrument_id,
        side=side,
        quantity=Decimal("60"),
        venue_order_id=f"sim-{side}-{instrument_id}-{seed}",
        seed=seed,
        fill_chunks=3,
        base_mid=100.0,
    )

    def _resolver(execution: object):
        if not isinstance(execution, ExecutionEvent):
            return None
        return resolve_execution_finance(
            schedule,
            execution=execution,
            instrument_id=instrument_id,
            side=side,
            account_id=account_id,
        )

    trade = ExecuteTrade(
        SqlAlchemyAccountRepository(session),
        SqlAlchemyPortfolioRepository(session),
        SqlAlchemyLedgerRepository(session),
    )
    return build_simulated_execute_trade_applier(trade, _resolver)


async def _drive_buy_sell(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    instrument_id: str,
    seed: int,
) -> list[str]:
    """Recorre BUY→SELL (net-zero) materializando ExecuteTrade real por fill SIM.

    Cada lado se envía por el camino canónico del worker M5
    (``submit_simulated_order(..., apply_finance=<applier real>)``); cada fill CAPTURADO
    llega a APPLIED al materializar su ExecuteTrade idempotente. Devuelve los
    ``execution_id`` de los fills confirmados.
    """
    from decimal import Decimal

    from bolsa_application.execution_event import PostgresExecutionEventStore
    from bolsa_application.simulated_settlement import submit_simulated_order

    fills: list[str] = []
    async with session_factory() as session:
        exec_store = PostgresExecutionEventStore(session)
        for side in ("buy", "sell"):
            applier = _finance_applier_for(
                session,
                account_id=account_id,
                instrument_id=instrument_id,
                side=side,
                seed=seed,
            )
            result, _out = await submit_simulated_order(
                exec_store,
                instrument_id=instrument_id,
                side=side,
                quantity=Decimal("60"),
                account_id=account_id,
                venue="simulated",
                seed=seed,
                fill_chunks=3,
                base_mid=100.0,
                order_id=f"auto-fin-{side}-{uuid.uuid4().hex[:8]}",
                owner="fin-pg-gate",
                apply_finance=applier,
            )
            for fill in result.fills:
                if abs(fill.qty_delta) > 0:
                    fills.append(fill.execution_id)
    return fills


def _seed_with_fills(instrument_id: str, *, side: str = "buy") -> int:
    """Elige un seed DETERMINISTA que garantice fills (no dependa de la lotería).

    ``draw_queue_noise(seed, side, instrument_id)`` puede devolver una terminal
    noisy (reject/closed/timeout) que deja ``fills=()``. El test asumía que el seed
    aleatorio SIEMPRE llenaba → flaky ~13% de las corridas. Aquí se busca el primer
    seed con fills para los DOS lados (buy/sell) del instrumento dado.
    """
    from decimal import Decimal

    from bolsa_application.simulated_broker import simulated_fill_schedule

    for seed in range(1, 100_000):
        ok = True
        for s in ("buy", "sell"):
            r = simulated_fill_schedule(
                instrument_id=instrument_id,
                side=s,
                quantity=Decimal("60"),
                venue_order_id=f"sim-{s}-{instrument_id}-{seed}",
                seed=seed,
                fill_chunks=3,
                base_mid=100.0,
            )
            if not r.fills:
                ok = False
                break
        if ok:
            return seed
    raise AssertionError(f"no seed con fills para {instrument_id!r}")


@pytest.mark.asyncio
async def test_finance_auto_day_materializes_executetrade_exactly_once(
    fin_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Día AUTO SIM-ONLY con finanzas REALES mueve el libro PG exactamente una vez.

    Ejecuta un BUY y un SELL (net-zero) por el settlement AUTO con finanzas reales y
    comprueba sobre PG que cada fill quedó ``APPLIED`` y que re-aplicar el MISMO fill
    (crash/relaunch) devuelve ``already_applied`` sin volver a tocar dinero (invariante
    C3/P2-01 idempotente por ``simulated_idempotency_key``).
    """
    instrument_id = f"inst-fin-{uuid.uuid4().hex[:10]}"
    # V2.23/A9: seed determinista con fills garantizados (antes aleatorio ⇒ flaky ~13%).
    seed = _seed_with_fills(instrument_id)
    account_id: str | None = None
    try:
        async with fin_pg_factory() as session:
            account_id = await _seed_account_tag(session)
            await _seed_instrument(session, instrument_id)

        fills = await _drive_buy_sell(
            fin_pg_factory,
            account_id=account_id,
            instrument_id=instrument_id,
            seed=seed,
        )
        assert fills, "la corrida finance debió confirmar fills reales"
        assert len(fills) == len(set(fills)), "cada execution_id es único (no-doble)"

        from bolsa_application.accounts.trade import ExecuteTrade  # noqa: PLC0415
        from bolsa_application.execution_event import (  # noqa: PLC0415
            PostgresExecutionEventStore,
            apply_execution_financial_once,
        )
        from bolsa_application.simulated_finance import (  # noqa: PLC0415
            build_simulated_execute_trade_applier,
        )
        from bolsa_infrastructure.database.repositories.account_repository import (  # noqa: PLC0415
            SqlAlchemyAccountRepository,
        )
        from bolsa_infrastructure.database.repositories.ledger_repository import (  # noqa: PLC0415
            SqlAlchemyLedgerRepository,
        )
        from bolsa_infrastructure.database.repositories.portfolio_repository import (  # noqa: PLC0415
            SqlAlchemyPortfolioRepository,
        )

        async with fin_pg_factory() as session:
            store = PostgresExecutionEventStore(session)
            trade = ExecuteTrade(
                SqlAlchemyAccountRepository(session),
                SqlAlchemyPortfolioRepository(session),
                SqlAlchemyLedgerRepository(session),
            )
            for _eid in fills:
                row = await store.get(_eid)
                assert row is not None and row.status == "APPLIED", row.status if row else None
                # Re-aplicar el MISMO fill (crash) NO vuelve a tocar dinero: always
                # already_applied (la traza ya se marcó APPLIED de forma durable).
                second = await apply_execution_financial_once(
                    store,
                    execution=row,
                    apply_finance=build_simulated_execute_trade_applier(trade, lambda _e: None),  # noqa: PLC0415
                    owner="fin-pg-gate-replay",
                )
                assert second == "already_applied", second
    finally:
        if account_id:
            from sqlalchemy import delete  # noqa: PLC0415

            from bolsa_infrastructure.database.models.tables import InstrumentRow  # noqa: PLC0415
            from bolsa_infrastructure.database.repositories.account_repository import (  # noqa: PLC0415
                SqlAlchemyAccountRepository,
            )

            async with fin_pg_factory() as session:
                await session.execute(
                    delete(InstrumentRow).where(InstrumentRow.id == instrument_id)
                )
                try:
                    await SqlAlchemyAccountRepository(session).close_account(account_id)
                except Exception:  # noqa: BLE001 — cleanup nunca tira el test
                    pass
                await session.commit()
