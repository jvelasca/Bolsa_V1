"""M-2 (T-M2) — invariante de reconciliación cash↔ledger (método-repo + tests-postcondición).

Invariante M-2: ``cash del account == Σ amount del ledger del account``, donde el cash
del account se computa como la suma del ``PortfolioRow.cash`` de TODAS sus legacy
portfolios (vía ``InvestmentPortfolioRow.legacy_portfolio_id``) y el Σ del ledger es
``LedgerRepository.sum_cash_amounts(account_id)`` (todas las filas del account).

Postcondición: tras cada write-path de application que SÍ escribe ledger
(``CreateSimulatedAccount``/siembra, ``DepositCashToAccount``, ``WithdrawCashFromAccount``,
``ExecuteTrade``, ``ApplyCustodyFees``) el Σ ledger == cash.

Coherencia por-cuenta: el re-compute es a nivel ACCOUNT (suma de TODAS las legacy
carteras + toda la traza ledger del account), no de una legacy portfolio suelta.

Escotilla B-3 (documentada, NO se "arregla" en esta fase): ``add_cash``/``deduct_cash``
directos (repo) mutan ``PortfolioRow.cash`` SIN escribir ledger (``transfer_cash`` fue
ELIMINADO en B-3 por código muerto); un
test negativo con ``pytest.mark.xfail`` documenta que rompen el invariant. Es un test de
cobertura documental, no un guard de runtime.

PostgreSQL real (patrón ``db_session`` como ``test_ledger_entries_reference_unique.py`` /
``test_financial_invariants.py``; ``pytest.skip`` si no hay DB). Todos los ids son UUIDs.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import (
    InstrumentRow,
    InvestmentPortfolioRow,
    PortfolioRow,
)

if TYPE_CHECKING:
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
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


async def _new_account(
    session: AsyncSession, *, name: str, initial_deposit: float
) -> str:
    """Crea una cuenta simulada REAL (repo) con su cartera + seed deposit en ledger.

    Devuelve el ``account_id``. La siembra escribe la fila ``deposit`` (+initial_deposit)
    en ledger y el ``PortfolioRow.cash = initial_deposit`` (``account_repository.py``
    ``_create_investment_account``).
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    scope = await SqlAlchemyAccountRepository(session).create_simulated_account(
        name=name,
        initial_deposit=initial_deposit,
    )
    return scope.account.id


async def _account_total_cash(session: AsyncSession, account_id: str) -> Decimal:
    """Cash del account = Σ ``PortfolioRow.cash`` de TODAS sus legacy portfolios.

    Resuelve el cash del account a nivel ACCOUNT (no de una legacy cartera suelta):
    suma el cash de cada cartera legacy vinculada vía ``InvestmentPortfolioRow``.
    """
    stmt = select(PortfolioRow.cash).join(
        InvestmentPortfolioRow,
        InvestmentPortfolioRow.legacy_portfolio_id == PortfolioRow.id,
    ).where(InvestmentPortfolioRow.account_id == account_id)
    cash_values = (await session.execute(stmt)).scalars().all()
    return sum((c for c in cash_values), Decimal("0"))


async def _assert_reconciled(
    session: AsyncSession,
    ledger_repo: SqlAlchemyLedgerRepository,
    account_id: str,
    *,
    expected_cash: Decimal | None = None,
) -> None:
    """Postcondición M-2: Σ ledger (sum_cash_amounts) == cash del account."""
    ledger_total = await ledger_repo.sum_cash_amounts(account_id)
    cash_total = await _account_total_cash(session, account_id)
    if expected_cash is not None:
        assert cash_total == expected_cash
    assert ledger_total == cash_total, (
        f"Σ ledger={ledger_total} != Σ cash={cash_total} (account {account_id})"
    )


async def _new_instrument(session: AsyncSession, tag: str) -> InstrumentRow:
    instrument = InstrumentRow(
        id=f"inst_{tag}_{uuid4().hex[:12]}",
        symbol=f"M2{tag[:3].upper()}{uuid4().hex[:4].upper()}",
        yahoo_symbol=f"M2{tag}_{uuid4().hex[:8]}",
        isin=None,
        name=f"M2 {tag}",
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
    return instrument


@pytest.mark.asyncio
async def test_seed_nueva_cuenta_reconcilia(db_session: AsyncSession) -> None:
    """Siembra de cuenta nueva: Σ ledger == Σ cash == initial_deposit."""
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    account_id = await _new_account(
        db_session, name=f"m2-seed-{uuid4().hex[:8]}", initial_deposit=100_000.0
    )
    ledger_repo = SqlAlchemyLedgerRepository(db_session)
    await _assert_reconciled(
        db_session, ledger_repo, account_id, expected_cash=Decimal("100000")
    )


@pytest.mark.asyncio
async def test_deposit_cash_to_account_reconcilia(db_session: AsyncSession) -> None:
    """DepositCashToAccount: Σ ledger == Σ cash (una fila deposit nueva)."""
    from bolsa_application.accounts import DepositCashToAccount
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    account_repo = SqlAlchemyAccountRepository(db_session)
    ledger_repo = SqlAlchemyLedgerRepository(db_session)
    portfolio_repo = SqlAlchemyPortfolioRepository(db_session)

    account_id = await _new_account(
        db_session, name=f"m2-dep-{uuid4().hex[:8]}", initial_deposit=1000.0
    )
    await DepositCashToAccount(account_repo, portfolio_repo, ledger_repo).execute(
        account_id,
        amount=250.0,
        idempotency_key=f"dep-{uuid4().hex[:8]}",
    )
    await _assert_reconciled(
        db_session, ledger_repo, account_id, expected_cash=Decimal("1250")
    )


@pytest.mark.asyncio
async def test_withdraw_cash_from_account_reconcilia(db_session: AsyncSession) -> None:
    """WithdrawCashFromAccount: Σ ledger == Σ cash (una fila withdrawal nueva)."""
    from bolsa_application.accounts import WithdrawCashFromAccount
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    account_repo = SqlAlchemyAccountRepository(db_session)
    ledger_repo = SqlAlchemyLedgerRepository(db_session)
    portfolio_repo = SqlAlchemyPortfolioRepository(db_session)

    account_id = await _new_account(
        db_session, name=f"m2-wd-{uuid4().hex[:8]}", initial_deposit=1000.0
    )
    await WithdrawCashFromAccount(account_repo, portfolio_repo, ledger_repo).execute(
        account_id,
        amount=300.0,
        idempotency_key=f"wd-{uuid4().hex[:8]}",
    )
    await _assert_reconciled(
        db_session, ledger_repo, account_id, expected_cash=Decimal("700")
    )


@pytest.mark.asyncio
async def test_execute_trade_con_fees_reconcilia(db_session: AsyncSession) -> None:
    """ExecuteTrade con fees: Σ ledger == Σ cash (2 filas por trade: buy + fee)."""
    from bolsa_application.accounts import ExecuteTrade
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    account_repo = SqlAlchemyAccountRepository(db_session)
    ledger_repo = SqlAlchemyLedgerRepository(db_session)
    portfolio_repo = SqlAlchemyPortfolioRepository(db_session)

    account_id = await _new_account(
        db_session, name=f"m2-trade-{uuid4().hex[:8]}", initial_deposit=10_000.0
    )
    instrument = await _new_instrument(db_session, "trade")

    await ExecuteTrade(account_repo, portfolio_repo, ledger_repo).execute(
        instrument_id=instrument.id,
        trade_type="buy",
        quantity=10,
        price=500,
        account_id=account_id,
    )
    # Fees de standard_es: el trade escribe buy (-notional) + fee (-abs) en ledger.
    # Σ = seed(+10000) - notional - fees == cash tras trade.
    await _assert_reconciled(db_session, ledger_repo, account_id)


@pytest.mark.asyncio
async def test_apply_custody_fees_reconcilia(db_session: AsyncSession) -> None:
    """ApplyCustodyFees: Σ ledger == Σ cash (cargo fee/custody, incl. partial si aplica)."""
    from bolsa_application.accounts import ApplyCustodyFees
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    account_repo = SqlAlchemyAccountRepository(db_session)
    ledger_repo = SqlAlchemyLedgerRepository(db_session)
    portfolio_repo = SqlAlchemyPortfolioRepository(db_session)

    account_id = await _new_account(
        db_session, name=f"m2-custody-{uuid4().hex[:8]}", initial_deposit=100_000.0
    )
    scope = await account_repo.resolve_scope(account_id)
    applied = await ApplyCustodyFees(account_repo, portfolio_repo, ledger_repo).execute(
        scope
    )
    assert applied is True
    await _assert_reconciled(db_session, ledger_repo, account_id)


@pytest.mark.asyncio
async def test_recomputed_es_coherente_a_nivel_account(db_session: AsyncSession) -> None:
    """El re-compute M-2 es a nivel ACCOUNT, no legacy-portfolio suelto.

    Dos cuentas con distinto seed: ``sum_cash_amounts`` de la cuenta A solo suma SU
    traza ledger (nunca la de B), y el cash del account A solo suma SUS legacy carteras.
    """
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    account_a = await _new_account(
        db_session, name=f"m2-accA-{uuid4().hex[:8]}", initial_deposit=5000.0
    )
    account_b = await _new_account(
        db_session, name=f"m2-accB-{uuid4().hex[:8]}", initial_deposit=9000.0
    )
    await db_session.flush()

    ledger_repo = SqlAlchemyLedgerRepository(db_session)
    await _assert_reconciled(db_session, ledger_repo, account_a)
    await _assert_reconciled(db_session, ledger_repo, account_b)
    # Aislación: el Σ de la cuenta A no incluye filas de B.
    assert await ledger_repo.sum_cash_amounts(account_a) == Decimal("5000")
    assert await ledger_repo.sum_cash_amounts(account_b) == Decimal("9000")


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=False,
    reason=(
        "Escotilla B-3 (documentada): add_cash/deduct_cash mutan "
        "PortfolioRow.cash SIN escribir ledger → ROMPEN el invariant M-2. Es cobertura "
        "documental del agujero, NO un guard de runtime (fase B-3 lo decide). Este test "
        "demuestra que sin ledger el Σ diverge (xfail esperado)."
    ),
)
async def test_b3_deuda_directa_rompe_invariant_documental(
    db_session: AsyncSession,
) -> None:
    """Documenta que los write-paths "sucios" (B-3) rompen la reconciliación.

    ``add_cash`` mueve cash sin ledger: el Σ (via ``sum_cash_amounts``) NO refleja el
    nuevo cash, así que el invariant diverge. Pensado como registro de la escotilla;
    se marca xfail para que CI siga verde. No se invocan para "sanar" en esta fase.
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )
    from bolsa_infrastructure.database.repositories.portfolio_repository import (
        SqlAlchemyPortfolioRepository,
    )

    account_repo = SqlAlchemyAccountRepository(db_session)
    ledger_repo = SqlAlchemyLedgerRepository(db_session)
    portfolio_repo = SqlAlchemyPortfolioRepository(db_session)

    account_id = await _new_account(
        db_session, name=f"m2-b3-{uuid4().hex[:8]}", initial_deposit=1000.0
    )
    scope = await account_repo.resolve_scope(account_id)
    # add_cash muta cash SIN ledger → invariante ROMPIDO (esto es lo que documenta xfail).
    await portfolio_repo.add_cash(scope.legacy_portfolio_id, 500.0)
    await _assert_reconciled(db_session, ledger_repo, account_id)
