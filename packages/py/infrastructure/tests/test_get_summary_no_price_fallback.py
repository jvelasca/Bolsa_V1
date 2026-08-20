"""M-1 (T-M1, Opción B) — `get_summary`: fallback mark-to-cost para posiciones sin close D1.

Cubre la rama "sin precio" que antes generaba una pérdida fantasma:
una posición sin close D1 sumaba su ``cost_basis`` a ``total_cost`` pero nada a
``total_market_value`` → ``total_unrealized_pnl`` reportaba pérdida = coste completo y
``total_equity = cash + Σ market_value`` la excluía (inconsistente).

Tras el fix:
- Caso 1: posición CON close D1 → valorada por el close (no el fallback).
- Caso 2: posición SIN close D1 pero CON transacción previa → valorada por el último
  ``TransactionRow.price`` (mark-to-cost); market_value == quantity*price, unrealized ≈ 0
  si price ≈ coste, y ``total_market_value``/``total_equity`` la incluyen.
- Caso 3: posición SIN close D1 y SIN transacción → ``market_value=None``/
  ``unrealized_pnl=None``, NO suma a ``total_market_value`` ni ``total_equity``, y además
  NO arrastra su ``cost_basis`` huérfano a ``total_cost`` (así no se fabrica la pérdida
  fantasma).

PostgreSQL real (mismas convenciones que ``test_ledger_entries_reference_unique`` y
``test_f3b_alembic_data_epoch``: fixture ``db_session`` + ``pytest.skip`` si no hay DB).
Todos los ids son UUIDs únicos.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.migrations import ensure_migrated
from bolsa_infrastructure.database.models import (
    InstrumentRow,
    OhlcvBarRow,
    PortfolioRow,
    PositionRow,
    TransactionRow,
)

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _load_env() -> None:
    from pathlib import Path

    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
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


def _now() -> datetime:
    return datetime.now(UTC)


async def _portfolio(session: AsyncSession, tag: str) -> PortfolioRow:
    return PortfolioRow(
        id=f"pf_{tag}_{uuid4().hex[:12]}",
        name=f"Summary {tag}",
        currency="EUR",
        cash=Decimal("1000"),
        created_at=_now(),
        updated_at=_now(),
    )


async def _instrument(session: AsyncSession, tag: str) -> InstrumentRow:
    return InstrumentRow(
        id=f"inst_{tag}_{uuid4().hex[:12]}",
        symbol=f"SUM{tag[:3].upper()}{uuid4().hex[:4].upper()}",
        yahoo_symbol=f"SUM{tag}_{uuid4().hex[:8]}",
        isin=None,
        name=f"Summary {tag}",
        exchange="BMAD",
        country="ES",
        currency="EUR",
        type="stock",
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )


@pytest.mark.asyncio
async def test_caso1_close_d1_valored_por_close_no_fallback(db_session: AsyncSession) -> None:
    """Posición CON close D1 → usada por last_price; el fallback transaccional NO manda."""
    assert ensure_migrated() is True
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    portfolio = await _portfolio(db_session, "close")
    instrument = await _instrument(db_session, "close")
    db_session.add_all([portfolio, instrument])
    await db_session.flush()

    db_session.add(
        PositionRow(
            id=f"pos_{uuid4().hex[:12]}",
            portfolio_id=portfolio.id,
            instrument_id=instrument.id,
            quantity=Decimal("5"),
            avg_cost=Decimal("8"),
            updated_at=_now(),
        )
    )
    # close D1 = 10 => market_value 5*10=50, unrealized 50-40=10.
    db_session.add(
        OhlcvBarRow(
            id=f"bar_{uuid4().hex[:12]}",
            instrument_id=instrument.id,
            timeframe="1d",
            timestamp=_now(),
            open=Decimal("9"),
            high=Decimal("11"),
            low=Decimal("8"),
            close=Decimal("10"),
            volume=1000,
            source="yahoo",
            created_at=_now(),
        )
    )
    # transacción previa con precio DISTINTO (9): si el fallback mandara, last_price
    # sería 9. Debe mandar el close (10) => close gana, fallback no usado.
    db_session.add(
        TransactionRow(
            id=f"tx_{uuid4().hex[:12]}",
            portfolio_id=portfolio.id,
            instrument_id=instrument.id,
            type="buy",
            quantity=Decimal("5"),
            price=Decimal("9"),
            total=Decimal("45"),
            executed_at=_now(),
        )
    )
    await db_session.flush()

    repo = SqlAlchemyPortfolioRepository(db_session)
    summary = await repo.get_summary(portfolio.id)

    pos = summary.positions[0]
    assert pos.last_price == 10.0
    assert pos.market_value == 50.0
    assert pos.unrealized_pnl == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_caso2_sin_close_pero_con_transaccion_mark_to_cost(db_session: AsyncSession) -> None:
    """Posición SIN close D1 pero CON transacción → valorada por el último TransactionRow.price."""
    assert ensure_migrated() is True
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    portfolio = await _portfolio(db_session, "txfb")
    instrument = await _instrument(db_session, "txfb")
    db_session.add_all([portfolio, instrument])
    await db_session.flush()
    # Sin OhlcvBarRow: no hay close D1 para este instrumento.

    db_session.add(
        PositionRow(
            id=f"pos_{uuid4().hex[:12]}",
            portfolio_id=portfolio.id,
            instrument_id=instrument.id,
            quantity=Decimal("5"),
            avg_cost=Decimal("10"),
            updated_at=_now(),
        )
    )
    # Dos transacciones de precios distintos: la más reciente manda (DISTINCT ON
    # ordena por executed_at desc). Old=7, new=10.
    from datetime import timedelta

    t_now = _now()

    db_session.add(
        TransactionRow(
            id=f"tx_old_{uuid4().hex[:12]}",
            portfolio_id=portfolio.id,
            instrument_id=instrument.id,
            type="buy",
            quantity=Decimal("5"),
            price=Decimal("7"),
            total=Decimal("35"),
            executed_at=t_now - timedelta(days=2),
        )
    )
    db_session.add(
        TransactionRow(
            id=f"tx_new_{uuid4().hex[:12]}",
            portfolio_id=portfolio.id,
            instrument_id=instrument.id,
            type="buy",
            quantity=Decimal("5"),
            price=Decimal("10"),
            total=Decimal("50"),
            executed_at=t_now,
        )
    )
    await db_session.flush()

    repo = SqlAlchemyPortfolioRepository(db_session)
    summary = await repo.get_summary(portfolio.id)

    pos = summary.positions[0]
    assert pos.last_price == 10.0  # el fallback usa la transacción MÁS reciente
    assert pos.market_value == pytest.approx(50.0)  # 5 * 10
    # precio ≈ coste (10 ≈ 10) => unrealized ≈ 0 (mark-to-cost, sin pérdida fantasma).
    assert pos.unrealized_pnl is not None
    assert pos.unrealized_pnl == pytest.approx(0.0, abs=1e-9)
    # La posición SÍ suma a total_market_value y por tanto a total_equity.
    assert summary.total_market_value == pytest.approx(50.0)
    assert summary.total_cost == pytest.approx(50.0)
    assert summary.total_unrealized_pnl == pytest.approx(0.0, abs=1e-9)
    assert summary.total_equity == pytest.approx(1050.0)  # cash 1000 + 50


@pytest.mark.asyncio
async def test_caso3_sin_close_y_sin_transaccion_sin_perdida_fantasma(db_session: AsyncSession) -> None:
    """Posición SIN close D1 y SIN transacción → sin valor, y NO se fabrica pérdida fantasma.

    La posición queda con ``market_value=None``/``unrealized_pnl=None``, no suma a
    ``total_market_value`` ni ``total_equity``, y además su ``cost_basis`` huérfano NO
    entra en ``total_cost``: así ``total_unrealized_pnl (= Σ mv − Σ cost)`` no reporta
    la pérdida fantasma de coste completo.
    """
    assert ensure_migrated() is True
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    portfolio = await _portfolio(db_session, "nopx")
    instrument = await _instrument(db_session, "nopx")
    db_session.add_all([portfolio, instrument])
    await db_session.flush()
    # Sin OhlcvBarRow ni TransactionRow para este instrumento.

    db_session.add(
        PositionRow(
            id=f"pos_{uuid4().hex[:12]}",
            portfolio_id=portfolio.id,
            instrument_id=instrument.id,
            quantity=Decimal("5"),
            avg_cost=Decimal("8"),
            updated_at=_now(),
        )
    )
    await db_session.flush()

    repo = SqlAlchemyPortfolioRepository(db_session)
    summary = await repo.get_summary(portfolio.id)

    pos = summary.positions[0]
    assert pos.last_price is None
    assert pos.market_value is None
    assert pos.unrealized_pnl is None
    # No suma a total_market_value ni total_equity (equity se queda en cash = 1000).
    assert summary.total_market_value == 0.0
    assert summary.total_equity == pytest.approx(1000.0)
    # total_cost NO incluye el cost_basis huérfano (5*8=40) → total_unrealized_pnl no
    # fabrica la pérdida fantasma de 40.
    assert summary.total_cost == 0.0
    assert summary.total_unrealized_pnl == 0.0
