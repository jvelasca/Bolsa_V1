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
    sides: tuple[str, ...] = ("buy", "sell"),
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
        for side in sides:
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
        # Net-zero de libro: la venta llena exactamente lo comprado, también después
        # del borde float→Decimal que ExecuteTrade persiste. Si no, la posición no
        # queda plana y el aserto de cierre no certificaría el camino.
        if sum(sell, Decimal("0")) != realized:
            continue
        if _booked_qty_sum(buy) != _booked_qty_sum(sell):
            continue
        return seed, total, realized
    raise AssertionError(f"no seed con ida-y-vuelta viable para {instrument_id!r}")


def _sell_seed_with_fill(instrument_id: str, *, quantity: Decimal) -> int:
    """Elige un seed DETERMINISTA cuya pata ``sell`` produzca al menos un fill.

    **OBS-23 (2026-09-30).** ``draw_queue_noise`` deriva de ``(seed, side, instrument_id)``
    y una cola TERMINAL sin fill (``reject``/``timeout``/``market_closed``/``unavailable``/
    ``unknown``) tiene probabilidad ~5,6 % por corrida. Con un ``seed`` fijo y un
    ``instrument_id`` ALEATORIO, el caso oscilaba (``result.fills == ()``). El escenario de
    ``OBS-21`` no depende del seed, así que se ELIGE uno que llene y la entrada deja de ser
    una lotería. ``_fill_chunks`` es el espejo exacto del schedule del settlement (el corte
    no depende del ``venue_order_id``), así que el seed elegido vale para el caso real.
    """
    for seed in range(1, 100_000):
        chunks = _fill_chunks(instrument_id, "sell", seed=seed, quantity=quantity)
        if any(abs(chunk) > 0 for chunk in chunks):
            return seed
    raise AssertionError(f"no seed con fill para la pata sell de {instrument_id!r}")


_INITIAL_CASH = Decimal("100000")
_MONEY = Decimal("0.000001")


def _booked_qty(delta: Decimal) -> Decimal:
    """Cantidad que persiste ExecuteTrade: ``Decimal(str(float(delta)))``."""
    return Decimal(str(float(abs(delta))))


def _booked_qty_sum(chunks: tuple[Decimal, ...]) -> Decimal:
    return sum((_booked_qty(chunk) for chunk in chunks), Decimal("0"))


def _booked_notional(qty: Decimal, price: Decimal) -> Decimal:
    """Notional del borde real: no multiplica float por float."""
    return Decimal(str(float(qty))) * Decimal(str(float(price)))


def _booked_fee(notional: Decimal, side: str) -> Decimal:
    from bolsa_domain.account_settings import calculate_trade_fees, default_account_settings

    breakdown = calculate_trade_fees(
        float(notional),
        side,  # type: ignore[arg-type]
        default_account_settings(),
        currency="EUR",
    )
    return Decimal(str(breakdown.total))


def _cash_effect(fills: tuple, side: str) -> tuple[Decimal, Decimal, Decimal]:
    """(efecto en cash, notional firmado a favor del P&L, comisiones)."""
    cash = Decimal("0")
    notional = Decimal("0")
    fees = Decimal("0")
    for fill in fills:
        leg = _booked_notional(fill.qty_delta, fill.price)
        fee = _booked_fee(leg, side)
        notional += leg
        fees += fee
        if side == "buy":
            cash -= leg + fee
        else:
            cash += leg - fee
    return cash, notional, fees


def _priced_fills(
    instrument_id: str, side: str, *, seed: int, quantity: Decimal
) -> tuple:
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
    return tuple(fill for fill in result.fills if abs(fill.qty_delta) > 0)


async def _legacy_portfolio_id(session: AsyncSession, account_id: str) -> str:
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import InvestmentPortfolioRow

    portfolio_id = (
        await session.execute(
            select(InvestmentPortfolioRow.legacy_portfolio_id).where(
                InvestmentPortfolioRow.account_id == account_id
            )
        )
    ).scalar_one()
    assert portfolio_id is not None
    return str(portfolio_id)


async def _account_cash(session: AsyncSession, account_id: str) -> Decimal:
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import InvestmentPortfolioRow, PortfolioRow

    values = (
        await session.execute(
            select(PortfolioRow.cash)
            .join(
                InvestmentPortfolioRow,
                InvestmentPortfolioRow.legacy_portfolio_id == PortfolioRow.id,
            )
            .where(InvestmentPortfolioRow.account_id == account_id)
        )
    ).scalars().all()
    return sum((value for value in values), Decimal("0"))


async def _position_qty(
    session: AsyncSession, portfolio_id: str, instrument_id: str
) -> Decimal | None:
    from sqlalchemy import select

    from bolsa_infrastructure.database.models.tables import PositionRow

    return (
        await session.execute(
            select(PositionRow.quantity).where(
                PositionRow.portfolio_id == portfolio_id,
                PositionRow.instrument_id == instrument_id,
            )
        )
    ).scalar_one_or_none()


async def _ledger_sum_and_count(session: AsyncSession, account_id: str) -> tuple[Decimal, int]:
    from sqlalchemy import func, select

    from bolsa_infrastructure.database.models.tables import LedgerEntryRow

    total, count = (
        await session.execute(
            select(
                func.coalesce(func.sum(LedgerEntryRow.amount), 0),
                func.count(),
            ).where(LedgerEntryRow.account_id == account_id)
        )
    ).one()
    return Decimal(total), int(count)


async def _assert_fill_truths(
    session: AsyncSession,
    *,
    portfolio_id: str,
    execution_ids: list[str],
    schedule: tuple,
    side: str,
) -> Decimal:
    """Cada fill APPLIED tiene su transacción, con la clave y la cantidad del schedule."""
    from sqlalchemy import select

    from bolsa_application.execution_event import PostgresExecutionEventStore
    from bolsa_application.simulated_settlement import simulated_idempotency_key
    from bolsa_infrastructure.database.models.tables import TransactionRow

    assert len(execution_ids) == len(schedule)
    store = PostgresExecutionEventStore(session)
    booked = Decimal("0")
    for execution_id, fill in zip(execution_ids, schedule, strict=True):
        assert execution_id.rsplit("#", 1)[-1] == str(fill.fill_seq)
        event = await store.get(execution_id)
        assert event is not None and event.status == "APPLIED", event.status if event else None
        key = simulated_idempotency_key(execution_id)
        row = (
            await session.execute(
                select(TransactionRow).where(
                    TransactionRow.portfolio_id == portfolio_id,
                    TransactionRow.idempotency_key == key,
                )
            )
        ).scalar_one()
        qty = _booked_qty(fill.qty_delta)
        assert row.type == side
        assert row.quantity == qty
        assert row.price == Decimal(str(float(fill.price))).quantize(_MONEY)
        assert row.total == _booked_notional(fill.qty_delta, fill.price).quantize(_MONEY)
        booked += qty
    return booked


@pytest.mark.asyncio
async def test_finance_auto_day_materializes_executetrade_exactly_once(
    fin_pg_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Día AUTO SIM-ONLY: BUY, SELL a plano, y las cinco verdades del libro.

    Settlement → ExecuteTrade → APPLIED, y sobre PostgreSQL:

    * cada fill tiene su ``transactions`` con ``simulated_idempotency_key``;
    * la posición tras el BUY es la cantidad liquidada, y tras el SELL desaparece;
    * Σ ledger == cash, y el cash es el depósito más el P&L menos las comisiones;
    * re-aplicar el fill devuelve ``already_applied`` sin mover cash, posición ni asientos.

    La venta se dimensiona a lo que la compra liquida (``_roundtrip_plan``), también
    en la cantidad que ExecuteTrade persiste, para que el cierre quede en cero.
    """
    instrument_id = f"inst-fin-{uuid.uuid4().hex[:10]}"
    # V2.23/A9 + FLAKE-1 (2026-09-30): seed determinista con ida-y-vuelta VIABLE.
    seed, buy_qty, sell_qty = _roundtrip_plan(instrument_id)
    account_id: str | None = None
    try:
        async with fin_pg_factory() as session:
            account_id = await _seed_account_tag(session)
            await _seed_instrument(session, instrument_id)

        buy_schedule = _priced_fills(instrument_id, "buy", seed=seed, quantity=buy_qty)
        sell_schedule = _priced_fills(instrument_id, "sell", seed=seed, quantity=sell_qty)
        buy_cash, buy_notional, buy_fees = _cash_effect(buy_schedule, "buy")
        sell_cash, sell_notional, sell_fees = _cash_effect(sell_schedule, "sell")
        buy_fills = await _drive_buy_sell(
            fin_pg_factory,
            account_id=account_id,
            instrument_id=instrument_id,
            seed=seed,
            quantities={"buy": buy_qty, "sell": sell_qty},
            sides=("buy",),
        )
        assert buy_fills, "la compra debió confirmar fills reales"
        assert len(buy_fills) == len(set(buy_fills))

        async with fin_pg_factory() as session:
            portfolio_id = await _legacy_portfolio_id(session, account_id)
            bought = await _assert_fill_truths(
                session,
                portfolio_id=portfolio_id,
                execution_ids=buy_fills,
                schedule=buy_schedule,
                side="buy",
            )
            position = await _position_qty(session, portfolio_id, instrument_id)
            cash = await _account_cash(session, account_id)
            ledger_sum, ledger_count = await _ledger_sum_and_count(session, account_id)
            assert position == bought
            assert cash == _INITIAL_CASH + buy_cash
            assert ledger_sum == cash
            from bolsa_infrastructure.database.repositories.portfolio_repository import (  # noqa: PLC0415
                SqlAlchemyPortfolioRepository,
            )

            summary = await SqlAlchemyPortfolioRepository(session).get_summary(portfolio_id)
            assert len(summary.positions) == 1
            marked = summary.positions[0]
            assert marked.last_price is not None
            assert marked.market_value == pytest.approx(marked.quantity * marked.last_price)
            assert summary.total_equity == pytest.approx(
                summary.portfolio.cash + summary.total_market_value
            )
            assert summary.total_equity == pytest.approx(
                float(cash) + float(position) * marked.last_price
            )

        sell_fills = await _drive_buy_sell(
            fin_pg_factory,
            account_id=account_id,
            instrument_id=instrument_id,
            seed=seed,
            quantities={"buy": buy_qty, "sell": sell_qty},
            sides=("sell",),
        )
        assert sell_fills, "la venta debió confirmar fills reales"
        fills = buy_fills + sell_fills
        assert len(fills) == len(set(fills)), "cada execution_id es único (no-doble)"

        async with fin_pg_factory() as session:
            portfolio_id = await _legacy_portfolio_id(session, account_id)
            await _assert_fill_truths(
                session,
                portfolio_id=portfolio_id,
                execution_ids=sell_fills,
                schedule=sell_schedule,
                side="sell",
            )
            assert await _position_qty(session, portfolio_id, instrument_id) is None
            cash = await _account_cash(session, account_id)
            ledger_sum, ledger_count_after_sell = await _ledger_sum_and_count(session, account_id)
            realized_pnl = sell_notional - buy_notional
            assert cash == _INITIAL_CASH + realized_pnl - (buy_fees + sell_fees)
            assert cash == _INITIAL_CASH + buy_cash + sell_cash
            assert ledger_sum == cash
            assert ledger_count_after_sell > ledger_count

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
            portfolio_id = await _legacy_portfolio_id(session, account_id)
            cash_before = await _account_cash(session, account_id)
            position_before = await _position_qty(session, portfolio_id, instrument_id)
            ledger_before, count_before = await _ledger_sum_and_count(session, account_id)
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
            assert await _account_cash(session, account_id) == cash_before
            assert await _position_qty(session, portfolio_id, instrument_id) == position_before
            ledger_after, count_after = await _ledger_sum_and_count(session, account_id)
            assert ledger_after == ledger_before == cash_before
            assert count_after == count_before
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
    # OBS-23 (2026-09-30): el schedule del simulador puede caer en una cola TERMINAL sin
    # fill (~5,6 %) y con un seed fijo el test oscilaba (``result.fills == ()``). El seed se
    # ELIGE determinista (la pata ``sell`` llena); el escenario de OBS-21 no depende de él.
    sell_qty = Decimal("60")
    seed = _sell_seed_with_fill(instrument_id, quantity=sell_qty)
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
