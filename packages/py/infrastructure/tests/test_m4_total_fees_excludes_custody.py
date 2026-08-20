"""M-4 (T-M5) — `total_fees_for_account` NO mezcla fees de custodia con fees de trade.

Hallazgo (mapeo read-only verificada): `GetTaxReport` sobrescribe `fees_paid_total`
del report (que en dominio solo suma trade-fees del ejercicio) con
`total_fees_for_account` (accounts.py:750-751). Ese método contaba TODAS las filas
`type == "fee"` del account, incluyendo la custodia (`reference_type="custody"`,
escrita por `append_custody_fee`) → el tax-report mezclaba comisiones de custodia
dentro de "Comisiones pagadas" (FE tax-report-page.tsx:325).

Fix (Opción B, decisión usuario, acotado): `total_fees_for_account` excluye las filas
`reference_type == "custody"`. Los trade-fees siguen usando `reference_type`
de "transaction" (append_fee) y se siguen contando. Este test lo verifica con
PostgreSQL real (patrón db_session como test_m2_ledger_cash_reconciliation.py).
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

from bolsa_infrastructure.database.models import LedgerEntryRow
from bolsa_infrastructure.ids import new_id

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


async def _new_account(
    session: AsyncSession, *, name: str, initial_deposit: float
) -> str:
    """Crea una cuenta simulada REAL (repo) con su cartera + seed deposit."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=name,
        initial_deposit=initial_deposit,
    )
    return scope.account.id


def _now_2026() -> datetime:
    return datetime(2026, 6, 1, tzinfo=UTC)


def _add_fee_entry(
    session: AsyncSession,
    *,
    account_id: str,
    reference_type: str,
    reference_id: str,
    amount: Decimal,
) -> None:
    """Inserta una fila ledger `type="fee"` (trade o custodia) de forma directa."""
    entry = LedgerEntryRow(
        id=new_id(),
        account_id=account_id,
        portfolio_id=None,
        type="fee",
        amount=amount,
        currency="EUR",
        balance_after=Decimal("0.0"),
        instrument_id=None,
        quantity=None,
        price=None,
        reference_type=reference_type,
        reference_id=reference_id,
        description=None,
        executed_at=_now_2026(),
        created_at=_now_2026(),
    )
    session.add(entry)


@pytest.mark.asyncio
async def test_total_fees_for_account_excluye_custodia(db_session: AsyncSession) -> None:
    """`total_fees_for_account` suma solo trade-fees, nunca custodia (M-4/T-M5)."""
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    account_id = await _new_account(
        db_session, name=f"m4-fees-{uuid4().hex[:8]}", initial_deposit=10_000.0
    )
    ledger_repo = SqlAlchemyLedgerRepository(db_session)

    # trade-fee (reference_type="transaction") y custodia-fee (reference_type="custody"),
    # ambos type="fee", ambos dentro del ejercicio 2026.
    _add_fee_entry(
        db_session,
        account_id=account_id,
        reference_type="transaction",
        reference_id="trade-tx-1",
        amount=Decimal("-10.0"),
    )
    _add_fee_entry(
        db_session,
        account_id=account_id,
        reference_type="custody",
        reference_id="custody-2026",
        amount=Decimal("-25.0"),
    )
    await db_session.flush()

    fiscal_start = datetime(2026, 1, 1, tzinfo=UTC)
    fiscal_end = datetime(2027, 1, 1, tzinfo=UTC)
    total = await ledger_repo.total_fees_for_account(
        account_id,
        executed_from=fiscal_start,
        executed_to=fiscal_end,
    )

    # Solo el trade-fee (10.0); la custodia (25.0) NO se cuenta.
    assert total == 10.0


@pytest.mark.asyncio
async def test_total_fees_rango_fiscal_respetado(db_session: AsyncSession) -> None:
    """El rango fiscal se sigue aplicando además de excluir custodia."""
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    account_id = await _new_account(
        db_session, name=f"m4-fees2-{uuid4().hex[:8]}", initial_deposit=10_000.0
    )
    ledger_repo = SqlAlchemyLedgerRepository(db_session)

    # Una custodia en el rango (no cuenta) y un trade-fee FUERA del rango (2025).
    _add_fee_entry(
        db_session,
        account_id=account_id,
        reference_type="custody",
        reference_id="custody-2026",
        amount=Decimal("-25.0"),
    )
    # trade-fee en 2025 (fuera del rango 2026 [inicio,fin)).
    out_of_range = LedgerEntryRow(
        id=new_id(),
        account_id=account_id,
        portfolio_id=None,
        type="fee",
        amount=Decimal("-7.0"),
        currency="EUR",
        balance_after=Decimal("0.0"),
        instrument_id=None,
        quantity=None,
        price=None,
        reference_type="transaction",
        reference_id="trade-tx-2025",
        description=None,
        executed_at=datetime(2025, 5, 1, tzinfo=UTC),
        created_at=datetime(2025, 5, 1, tzinfo=UTC),
    )
    db_session.add(out_of_range)
    await db_session.flush()

    fiscal_start = datetime(2026, 1, 1, tzinfo=UTC)
    fiscal_end = datetime(2027, 1, 1, tzinfo=UTC)
    total = await ledger_repo.total_fees_for_account(
        account_id,
        executed_from=fiscal_start,
        executed_to=fiscal_end,
    )

    # Ni la custodia del rango ni el trade-fee fuera de rango cuentan.
    assert total == 0.0
