"""F1/M5 — invariantes contables (cash≥0, qty≥0, coherencia balance_after, anti-doble-gasto).

Requiere PostgreSQL + migración (patrón `db_session` de infra). Los tests con bloqueo
concurrente demuestran que `with_for_update()` (M1) impide el sobregiro/doble gasto.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

from bolsa_infrastructure.database.models import InstrumentRow, PortfolioRow

# psycopg async no soporta ProactorEventLoop en Windows (como en application/tests/conftest.py)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _load_env() -> None:
    env_path = _repo_root() / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@pytest_asyncio.fixture
async def db_session():
    _load_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"PostgreSQL no disponible: {exc}")

    factory = create_session_factory(engine)
    async with factory() as session:
        try:
            yield session
            await session.rollback()
        except Exception:
            await session.rollback()
            raise
    await engine.dispose()


async def _new_environment(db_session) -> tuple[str, str]:
    """Crea una cartera con efectivo y un instrumento. Devuelve (portfolio_id, instrument_id)."""
    import uuid

    from bolsa_infrastructure.ids import new_id

    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:8]
    pid = new_id()
    db_session.add(
        PortfolioRow(
            id=pid,
            name=f"inv-portfolio-{suffix}",
            currency="EUR",
            cash=1500,
            created_at=now,
            updated_at=now,
        )
    )
    iid = new_id()
    db_session.add(
        InstrumentRow(
            id=iid,
            symbol=f"INV{suffix}",
            yahoo_symbol=f"INV{suffix}.MC",
            isin=None,
            name="Invariantes Test",
            exchange="BMAD",
            country="ES",
            currency="EUR",
            type="stock",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()
    return pid, iid


async def _query_cash(db_session, pid: str) -> float:
    row = await db_session.get(PortfolioRow, pid)
    assert row is not None
    return float(row.cash)


async def _query_qty(db_session, pid: str, iid: str) -> float:
    from bolsa_infrastructure.database.models import PositionRow

    stmt = select(PositionRow.quantity).where(
        PositionRow.portfolio_id == pid,
        PositionRow.instrument_id == iid,
    )
    qty = (await db_session.execute(stmt)).scalar_one_or_none()
    return float(qty) if qty is not None else 0.0


@pytest.mark.asyncio
async def test_buy_insufficient_never_overdraws(db_session) -> None:
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    pid, iid = await _new_environment(db_session)
    await db_session.commit()
    # cash=1500; buy notional 100*100=10000 > 1500 → rechazado, cash intacto ≥ 0.
    with pytest.raises(ValueError, match="Efectivo insuficiente"):
        await SqlAlchemyPortfolioRepository(db_session).execute_trade(
            instrument_id=iid,
            trade_type="buy",
            quantity=100,
            price=100,
            legacy_portfolio_id=pid,
        )
    await db_session.rollback()
    assert await _query_cash(db_session, pid) == 1500.0


@pytest.mark.asyncio
async def test_sell_more_than_held_never_negative_qty(db_session) -> None:
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    pid, iid = await _new_environment(db_session)
    repo = SqlAlchemyPortfolioRepository(db_session)
    # Compra válida 5@100 → cash 1000, qty 5.
    await repo.execute_trade(
        instrument_id=iid,
        trade_type="buy",
        quantity=5,
        price=100,
        legacy_portfolio_id=pid,
    )
    await db_session.commit()
    assert await _query_qty(db_session, pid, iid) == 5.0

    # Vender más de lo que se tiene → ValueError, qty se mantiene 5 (no negativa).
    with pytest.raises(ValueError, match="No tienes suficientes acciones"):
        await repo.execute_trade(
            instrument_id=iid,
            trade_type="sell",
            quantity=99,
            price=100,
            legacy_portfolio_id=pid,
        )
    await db_session.rollback()
    assert await _query_qty(db_session, pid, iid) == 5.0


@pytest.mark.asyncio
async def test_round_trip_balance_coherent(db_session) -> None:
    """Balance_after (summary.portfolio.cash) siempre coincide con el cash grabado."""
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    pid, iid = await _new_environment(db_session)
    repo = SqlAlchemyPortfolioRepository(db_session)
    r1 = await repo.execute_trade(
        instrument_id=iid,
        trade_type="buy",
        quantity=5,
        price=100,
        legacy_portfolio_id=pid,
        fee_amount=5,
    )
    await db_session.commit()
    # buy: 1500 - 500 - 5 = 995
    assert r1.summary.portfolio.cash == 995.0
    assert await _query_cash(db_session, pid) == 995.0

    r2 = await repo.execute_trade(
        instrument_id=iid,
        trade_type="sell",
        quantity=2,
        price=120,
        legacy_portfolio_id=pid,
        fee_amount=3,
    )
    await db_session.commit()
    # sell: 995 + 240 - 3 = 1232
    assert r2.summary.portfolio.cash == 1232.0
    assert await _query_cash(db_session, pid) == 1232.0
    assert await _query_qty(db_session, pid, iid) == 3.0


@pytest.mark.asyncio
async def test_idempotency_key_does_not_duplicate(db_session) -> None:
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    pid, iid = await _new_environment(db_session)
    repo = SqlAlchemyPortfolioRepository(db_session)
    first = await repo.execute_trade(
        instrument_id=iid,
        trade_type="buy",
        quantity=5,
        price=100,
        legacy_portfolio_id=pid,
        idempotency_key="order-single",
    )
    await db_session.commit()

    duplicate = await repo.find_transaction_by_idempotency(pid, "order-single")
    assert duplicate is not None
    assert duplicate.id == first.transaction.id
    # Una sola transacción: comprar 5@100 deja cash 1000 (no 500 por duplicado).
    assert await _query_cash(db_session, pid) == 1000.0


@pytest.mark.asyncio
async def test_concurrent_buys_no_double_spend() -> None:
    """Anti-doble-gasto bajo concurrencia: dos buys simultáneos que juntos exceden el cash.

    Con with_for_update(), las transacciones se serializan sobre la fila de cartera:
    solo una puede agotar cash; la final nunca es negativa y exactamente una tiene éxito
    (la otra lanza Efectivo insuficiente), en vez de que ambas lean 1500 y sobregiren.
    """
    _load_env()

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    factory = create_session_factory(engine)

    # Setup (committido): cash=1500, instrumento.
    async with factory() as setup:
        pid, iid = await _new_environment(setup)
        await setup.commit()

    # cash=1500 en split: trade A usa 1000, trade B usa 1000 → solo 1 cabe.
    async def _try_buy() -> bool:
        async with factory() as session:
            repo = SqlAlchemyPortfolioRepository(session)
            try:
                await repo.execute_trade(
                    instrument_id=iid,
                    trade_type="buy",
                    quantity=10,
                    price=100,
                    legacy_portfolio_id=pid,
                )
                await session.commit()
                return True
            except ValueError:
                await session.rollback()
                return False

    results = await asyncio.gather(_try_buy(), _try_buy())
    assert sum(1 for ok in results if ok) == 1, f"esperaba exactamente 1 éxito, obtuve {results}"

    # Invariantes: cash >= 0.
    async with factory() as check:
        cash = await _query_cash(check, pid)
        qty = await _query_qty(check, pid, iid)
    assert cash == 500.0
    assert cash >= 0.0
    assert qty == 10.0  # solo una de las compras aplicó
    await engine.dispose()
