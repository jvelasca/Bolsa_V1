"""R-8A (P0-B) — backstop de idempotencia: el repo relanza ``IdempotencyKeyExists``.

Verifica contra PostgreSQL REAL (patrón ``db_session`` como
``test_ledger_entries_reference_unique.py``; ``pytest.skip`` si no hay DB) que el
backstop concurrente de idempotencia devuelve una señal de dominio en lugar de un
``IntegrityError`` pelado:

- ``execute_trade`` con una ``idempotency_key`` ya persistida → ``IdempotencyKeyExists``
  (y el ganador sigue teniendo UNA sola transacción / posición / cash aplicado).
- ``append_cash_movement`` con ``reference_type="external"`` y un ``reference_id`` ya
  persistido → ``IdempotencyKeyExists`` (el write-path de deposit/withdraw no dobla).

Estos tests cubren el caso concurrente real (dos requests que pasan el pre-check a la
vez). El happy-path idempotente (pre-check) ya lo cubre la suite de application con fakes.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from bolsa_domain.errors import IdempotencyKeyExists
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import (
    InstrumentRow,
    LedgerEntryRow,
    TransactionRow,
)

if TYPE_CHECKING:
    pass

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


async def _make_cuenta_cartera_instrumento(
    session: AsyncSession, tag: str
) -> tuple[str, str, str, str]:
    """Crea cuenta simulada + cartera con seed + instrumento.

    Devuelve (account_id, legacy_pf_id, investment_pf_id, instrument_id). El ledger usa el
    ``investment_pf_id`` (FK a ``investment_portfolios``); el trade usa la ``legacy_pf_id``.
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=f"R8A {tag}",
        initial_deposit=100_000.0,
    )
    legacy_pf_id = scope.portfolio.legacy_portfolio_id
    if not legacy_pf_id:
        raise AssertionError("cartera seed sin legacy_portfolio_id")

    instrument = InstrumentRow(
        id=f"inst_{tag}_{uuid4().hex[:12]}",
        symbol=f"R8A{tag[:3].upper()}{uuid4().hex[:4].upper()}",
        yahoo_symbol=f"R8A{tag}_{uuid4().hex[:8]}",
        isin=None,
        name=f"R8A {tag}",
        exchange="BMAD",
        country="ES",
        currency="EUR",
        type="stock",
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(instrument)
    await session.flush()
    return scope.account.id, legacy_pf_id, scope.portfolio.id, instrument.id


@pytest.mark.asyncio
async def test_execute_trade_misma_key_relanza_idempotency(
    db_session: AsyncSession,
) -> None:
    """La 2ª ejecución con la MISMA idempotency_key → IdempotencyKeyExists (no dobla)."""
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    _, legacy_pf_id, _, instrument_id = await _make_cuenta_cartera_instrumento(db_session, "trade")
    repo = SqlAlchemyPortfolioRepository(db_session)

    result = await repo.execute_trade(
        instrument_id=instrument_id,
        trade_type="buy",
        quantity=10,
        price=100.0,
        legacy_portfolio_id=legacy_pf_id,
        fee_amount=0.0,
        idempotency_key="r8a-trade-key-1",
    )
    assert result.transaction.id

    with pytest.raises(IdempotencyKeyExists):
        await repo.execute_trade(
            instrument_id=instrument_id,
            trade_type="buy",
            quantity=10,
            price=100.0,
            legacy_portfolio_id=legacy_pf_id,
            fee_amount=0.0,
            idempotency_key="r8a-trade-key-1",
        )

    # El ganador tiene UNA sola transacción y el cash se debitó una sola vez.
    from sqlalchemy import func

    count = (
        await db_session.execute(
            select(func.count(TransactionRow.id)).where(
                TransactionRow.idempotency_key == "r8a-trade-key-1"
            )
        )
    ).scalar_one()
    assert int(count) == 1


@pytest.mark.asyncio
async def test_append_cash_movement_mismo_reference_relanza_idempotency(
    db_session: AsyncSession,
) -> None:
    """Depósito con un reference_id (idempotency_key) ya persistido → IdempotencyKeyExists."""
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    account_id, _, investment_pf_id, _ = await _make_cuenta_cartera_instrumento(db_session, "cash")
    repo = SqlAlchemyLedgerRepository(db_session)
    entry = await repo.append_cash_movement(
        account_id=account_id,
        portfolio_id=investment_pf_id,
        entry_type="deposit",
        amount=1000.0,
        currency="EUR",
        balance_after=101000.0,
        reference_id="r8a-dep-key-1",
        reference_type="external",
        description="dep r8a",
    )
    assert entry.id

    with pytest.raises(IdempotencyKeyExists):
        await repo.append_cash_movement(
            account_id=account_id,
            portfolio_id=investment_pf_id,
            entry_type="deposit",
            amount=1000.0,
            currency="EUR",
            balance_after=102000.0,
            reference_id="r8a-dep-key-1",
            reference_type="external",
            description="dep r8a duplicado",
        )

    # Solo una entrada con ese reference en la cuenta.
    from sqlalchemy import func

    count = (
        await db_session.execute(
            select(func.count(LedgerEntryRow.id)).where(
                LedgerEntryRow.account_id == account_id,
                LedgerEntryRow.reference_id == "r8a-dep-key-1",
            )
        )
    ).scalar_one()
    assert int(count) == 1
