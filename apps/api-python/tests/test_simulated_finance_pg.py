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
from decimal import Decimal
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
    session: AsyncSession,
    *,
    account_id: str,
    instrument_id: str,
    side: str,
    seed: int,
    venue_order_id: str,
    quantity: Decimal,
):
    """Applier ExecuteTrade real por fill; mapper puro resuelve price sobre el schedule.

    El ``ExecutionEvent`` no lleva price/instrument/side (es contexto del order), así que
    lo resolvemos con ``resolve_execution_finance`` cerrado sobre el ``SimulatedOrderResult``
    determinista del settlement; el schedule es reproducible para los mismos inputs, por
    lo que el applier recupera el price/cantidad correctos SIN inventar (H4).

    ``quantity`` DEBE ser la MISMA que la del settlement (FLAKE-1, 2026-09-30): el
    resolver rehace el schedule para recuperar el price/qty de cada fill, así que si la
    cantidad del resolver no coincide con la de la orden, los parciales no son los mismos.
    """
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
        quantity=quantity,
        venue_order_id=venue_order_id,
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
    quantities: dict[str, Decimal],
) -> list[str]:
    """Recorre BUY→SELL materializando ExecuteTrade real por fill SIM.

    Cada lado se envía por el camino canónico del worker M5
    (``submit_simulated_order(..., apply_finance=<applier real>)``); cada fill CAPTURADO
    llega a APPLIED al materializar su ExecuteTrade idempotente. Devuelve los
    ``execution_id`` de los fills confirmados.

    **FLAKE-1 (2026-09-30).** ``quantities`` permite dimensionar la venta a lo que la
    compra LIQUIDA de verdad: los parciales NO son simétricos entre patas (el corte
    deriva de ``(seed, side, instrument_id)``), así que pedir 60 en las dos podía
    sobrevender y dejar el fill en RETRY. Ver ``_roundtrip_plan``.
    """
    from bolsa_application.execution_event import PostgresExecutionEventStore
    from bolsa_application.simulated_settlement import (
        auto_venue_order_id,
        submit_simulated_order,
    )

    fills: list[str] = []
    async with session_factory() as session:
        exec_store = PostgresExecutionEventStore(session)
        for side in ("buy", "sell"):
            # V2.24/A9.1 (P1-03): identidad namespaceada única por intención. El
            # applier y el settlement DEBEN compartir el mismo venue_order_id para
            # que el resolver del schedule case por execution_id.
            logical_order_id = f"fin-{side}-{uuid.uuid4().hex[:8]}"
            venue_order_id = auto_venue_order_id(
                engine_id="engine",
                account_id=account_id,
                instrument_id=instrument_id,
                side=side,
                logical_order_id=logical_order_id,
            )
            applier = _finance_applier_for(
                session,
                account_id=account_id,
                instrument_id=instrument_id,
                side=side,
                seed=seed,
                venue_order_id=venue_order_id,
                quantity=quantities[side],
            )
            result, _out = await submit_simulated_order(
                exec_store,
                instrument_id=instrument_id,
                side=side,
                quantity=quantities[side],
                account_id=account_id,
                venue="simulated",
                seed=seed,
                fill_chunks=3,
                base_mid=100.0,
                order_id=f"auto-fin-{side}-{uuid.uuid4().hex[:8]}",
                engine_id="engine",
                logical_order_id=logical_order_id,
                owner="fin-pg-gate",
                apply_finance=applier,
            )
            for fill in result.fills:
                if abs(fill.qty_delta) > 0:
                    fills.append(fill.execution_id)
    return fills


def _fill_chunks(
    instrument_id: str, side: str, *, seed: int, quantity: Decimal
) -> tuple[Decimal, ...]:
    """(PURA) deltas por parcial de una pata: los MISMOS inputs que el settlement.

    El corte de las parciales (``draw_queue_noise``/``mid_cut``) deriva de
    ``(seed, side, instrument_id)`` y **nunca** del ``venue_order_id``, así que este
    espejo reproduce exactamente lo que el settlement liquidará para esa pata.
    """
    from bolsa_application.simulated_broker import simulated_fill_schedule

    result = simulated_fill_schedule(
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        venue_order_id=f"sim-{side}-{instrument_id}-{seed}",
        seed=seed,
        fill_chunks=3,
        base_mid=100.0,
    )
    return tuple(f.qty_delta for f in result.fills)


def _roundtrip_plan(instrument_id: str) -> tuple[int, Decimal, Decimal]:
    """Elige un seed DETERMINISTA con ida-y-vuelta VIABLE y dimensiona la pata ``sell``.

    Devuelve ``(seed, cantidad_comprada, cantidad_a_vender)``.

    El selector clásico (``_seed_with_fills``, retirado aquí) solo exigía «algún fill en
    cada pata»: no garantizaba que la venta CUPIERA en la cartera, porque el test asumía
    la MISMA cantidad en las dos patas.

    **FLAKE-1 (2026-09-30).** El corte de la parcial deriva de ``(seed, side,
    instrument_id)``: con el mismo seed, la pata ``buy`` puede cortarse tras su primer
    chunk (30 de 60) mientras la pata ``sell`` llena los tres (30+14,1+15,9 = 60). La
    venta pedía más de lo que la compra había dejado en cartera, ``portfolio_repository``
    la rechazaba (rechazo CORRECTO y fail-closed) y el fill quedaba en ``RETRY`` → rojo
    en **~6,7 %** de los ``instrument_id`` sorteados (medido: 1336 de 20000). No era el
    entorno, ni el motor, ni la clave de idempotencia: era el fixture.

    Ahora la pata ``sell`` se dimensiona a lo que la pata ``buy`` LIQUIDA de verdad, así
    que el ida-y-vuelta es net-zero por construcción y el oversell no puede ocurrir
    (medido tras el arreglo: **0 de 20000**).
    """
    total = Decimal("60")
    for seed in range(1, 100_000):
        buy = _fill_chunks(instrument_id, "buy", seed=seed, quantity=total)
        if not buy:
            continue  # terminal noisy (reject/timeout/closed) o corte en el 1er chunk.
        realized = sum(buy, Decimal("0"))
        sell = _fill_chunks(instrument_id, "sell", seed=seed, quantity=realized)
        if not sell:
            continue
        # Invariante del FIXTURE: la venta no puede exceder lo que dejó la compra.
        assert sum(sell, Decimal("0")) <= realized
        return seed, total, realized
    raise AssertionError(f"no seed con ida-y-vuelta viable para {instrument_id!r}")


@pytest.mark.asyncio
async def test_finance_auto_day_materializes_executetrade_exactly_once(
    fin_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Día AUTO SIM-ONLY con finanzas REALES mueve el libro PG exactamente una vez.

    Ejecuta un BUY y un SELL (net-zero) por el settlement AUTO con finanzas reales y
    comprueba sobre PG que cada fill quedó ``APPLIED`` y que re-aplicar el MISMO fill
    (crash/relaunch) devuelve ``already_applied`` sin volver a tocar dinero (invariante
    C3/P2-01 idempotente por ``simulated_idempotency_key``).

    La venta se dimensiona a lo que la compra LIQUIDA de verdad (``_roundtrip_plan``):
    los parciales no son simétricos entre patas y pedir la cantidad nominal en las dos
    sobrevendía la cartera en ~6,7 % de los ``instrument_id`` (FLAKE-1, 2026-09-30).
    """
    instrument_id = f"inst-fin-{uuid.uuid4().hex[:10]}"
    # V2.23/A9 + FLAKE-1 (2026-09-30): seed determinista con ida-y-vuelta VIABLE.
    seed, buy_qty, sell_qty = _roundtrip_plan(instrument_id)
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
            quantities={"buy": buy_qty, "sell": sell_qty},
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


@pytest.mark.asyncio
async def test_permanent_rejection_materializes_failed_not_retry(
    fin_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """OBS-21 end-to-end: una venta sin acciones materializa ``FAILED``, NO ``RETRY``.

    El repo de cartera rechaza de forma DETERMINISTA (``PermanentRejectionError``) una
    venta por encima de lo que hay en cartera. Antes ese rechazo se tragaba como un
    ``False`` del applier y, con ``retryable_on_ineffective=True``, dejaba el fill en
    ``RETRY`` (reintentable indefinidamente sobre un hecho que no cambia). Ahora el
    applier RE-LANZA el rechazo permanente y el store lo sella en ``FAILED``.
    """
    instrument_id = f"inst-fin-{uuid.uuid4().hex[:10]}"
    seed = 7
    account_id: str | None = None
    try:
        async with fin_pg_factory() as session:
            account_id = await _seed_account_tag(session)
            await _seed_instrument(session, instrument_id)

        # Venta SIN posición previa: la cartera tiene 0 acciones → rechazo permanente.
        from bolsa_application.execution_event import PostgresExecutionEventStore
        from bolsa_application.simulated_settlement import (
            auto_venue_order_id,
            submit_simulated_order,
        )

        sell_qty = Decimal("60")
        logical_order_id = f"fin-sell-{uuid.uuid4().hex[:8]}"
        venue_order_id = auto_venue_order_id(
            engine_id="engine",
            account_id=account_id,
            instrument_id=instrument_id,
            side="sell",
            logical_order_id=logical_order_id,
        )
        async with fin_pg_factory() as session:
            exec_store = PostgresExecutionEventStore(session)
            applier = _finance_applier_for(
                session,
                account_id=account_id,
                instrument_id=instrument_id,
                side="sell",
                seed=seed,
                venue_order_id=venue_order_id,
                quantity=sell_qty,
            )
            result, outcomes = await submit_simulated_order(
                exec_store,
                instrument_id=instrument_id,
                side="sell",
                quantity=sell_qty,
                account_id=account_id,
                venue="simulated",
                seed=seed,
                fill_chunks=3,
                base_mid=100.0,
                order_id=f"auto-fin-sell-{uuid.uuid4().hex[:8]}",
                engine_id="engine",
                logical_order_id=logical_order_id,
                owner="fin-pg-gate-obs21",
                apply_finance=applier,
            )
            assert result.fills, "el schedule simulado debió producir fills"
            assert outcomes, "el settlement debió intentar materializar los fills"
            # NINGÚN outcome puede ser reintentable ni APPLIED: rechazo permanente.
            assert all(o == "failed" for o in outcomes.values()), outcomes
            for execution_id, _outcome in outcomes.items():
                row = await exec_store.get(execution_id)
                assert row is not None
                assert row.status == "FAILED", (execution_id, row.status)
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
