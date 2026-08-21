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

Los tests crean cuentas simuladas ``m2-*`` y las limpian físicamente al final
(``_cleanup_account``: ``close_account`` + ``delete_simulated_account`` + commit,
R000 post-v1.3.0) para no dejar residuos ``simulated`` en la DB compartida.
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


async def _cleanup_account(session: AsyncSession, account_id: str) -> None:
    """Cierra y borra físicamente una cuenta simulada creada por ``_new_account``.

    R000 (deuda post-v1.3.0): cada test que crea una cuenta simulada vía repo debe
    limpiarla (``close_account`` + ``delete_simulated_account``) y COMMITEAR el borrado,
    para que no queden filas ``simulated`` sobre la DB compartida entre ejecuciones de
    la suite (rompían el invariante A del verify). Canon: account_repository ``:431``/``:444``.
    Los tests que además crean instrumentos vía ``_new_instrument`` deben llamar también
    ``_cleanup_instrument`` (los instrumentos no los borra ``delete_simulated_account``).
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    repo = SqlAlchemyAccountRepository(session)
    await repo.close_account(account_id)
    await repo.delete_simulated_account(account_id)
    await session.commit()


async def _cleanup_instrument(session: AsyncSession, instrument: InstrumentRow) -> None:
    """Borra físicamente un instrumento creado por ``_new_instrument``.

    R000 (deuda post-v1.3.0): ``delete_simulated_account`` NO borra los instrumentos
    (no cuelgan de la cuenta por FK), así que los tests que crean instrumento con
    ``_new_instrument`` deben borrarlo aparte para no dejar filas ``M2 trade``/``M2 insf``
    huérfanas en la DB compartida.
    """
    from sqlalchemy import delete as _delete

    await session.execute(_delete(InstrumentRow).where(InstrumentRow.id == instrument.id))
    await session.commit()


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
    """Siembra de cuenta nueva: Σ ledger == Σ cash == initial_deposit.

    Limpieza (R000): la cuenta simulada se cierra y borra físicamente al final.
    """
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
    await _cleanup_account(db_session, account_id)


@pytest.mark.asyncio
async def test_deposit_cash_to_account_reconcilia(db_session: AsyncSession) -> None:
    """DepositCashToAccount: Σ ledger == Σ cash (una fila deposit nueva).

    Limpieza (R000): la cuenta simulada se cierra y borra físicamente al final.
    """
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
    await _cleanup_account(db_session, account_id)


@pytest.mark.asyncio
async def test_withdraw_cash_from_account_reconcilia(db_session: AsyncSession) -> None:
    """WithdrawCashFromAccount: Σ ledger == Σ cash (una fila withdrawal nueva).

    Limpieza (R000): la cuenta simulada se cierra y borra físicamente al final.
    """
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
    await _cleanup_account(db_session, account_id)


@pytest.mark.asyncio
async def test_execute_trade_con_fees_reconcilia(db_session: AsyncSession) -> None:
    """ExecuteTrade con fees: Σ ledger == Σ cash (2 filas por trade: buy + fee).

    Limpieza (R000): la cuenta simulada (y el instrument asociado) se limpia al final.
    """
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
        idempotency_key=f"trade-{uuid4().hex[:8]}",
    )
    # Fees de standard_es: el trade escribe buy (-notional) + fee (-abs) en ledger.
    # Σ = seed(+10000) - notional - fees == cash tras trade.
    await _assert_reconciled(db_session, ledger_repo, account_id)
    await _cleanup_account(db_session, account_id)
    await _cleanup_instrument(db_session, instrument)


@pytest.mark.asyncio
async def test_apply_custody_fees_reconcilia(db_session: AsyncSession) -> None:
    """ApplyCustodyFees: Σ ledger == Σ cash (cargo completo fee/custody con saldo).

    Limpieza (R000): la cuenta simulada se cierra y borra físicamente al final.
    """
    from bolsa_application.accounts import ApplyCustodyFees
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.custody_obligation_repository import (
        CustodyObligationRepository,
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
    obligation_repo = CustodyObligationRepository(db_session)

    account_id = await _new_account(
        db_session, name=f"m2-custody-{uuid4().hex[:8]}", initial_deposit=100_000.0
    )
    scope = await account_repo.resolve_scope(account_id)
    applied = await ApplyCustodyFees(
        account_repo,
        portfolio_repo,
        ledger_repo,
        custody_obligation_repo=obligation_repo,
    ).execute(scope)
    assert applied is True
    await _assert_reconciled(db_session, ledger_repo, account_id)
    await _cleanup_account(db_session, account_id)


@pytest.mark.asyncio
async def test_custody_cash_insuficiente_no_escribe_ledger(db_session: AsyncSession) -> None:
    """F4a (ADR 026): con cash < fee la custodia NO descuenta ni escribe ledger.

    Se monta una cartera con patrimonio alto (equity de posición) y cash bajo, de modo
    que ``fee = equity*pct/100 > cash``. ``ApplyCustodyFees`` debe:
    - NO descontar cash ni escribir fila ledger ``custody`` (invariante Σ ledger (no
      añadido) intacto);
    - registrar la obligación como ``PENDING`` con ``outstanding = fee - cash``.

    Limpieza (R000): la cuenta simulada se cierra y borra físicamente al final.
    """
    from bolsa_application.accounts import ApplyCustodyFees
    from bolsa_infrastructure.database.models import (
        CustodyObligationRow,
        LedgerEntryRow,
        PositionRow,
        TransactionRow,
    )
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.custody_obligation_repository import (
        CustodyObligationRepository,
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
    obligation_repo = CustodyObligationRepository(db_session)

    account_id = await _new_account(
        db_session, name=f"m2-insf-{uuid4().hex[:8]}", initial_deposit=1000.0
    )
    scope = await account_repo.resolve_scope(account_id)
    legacy_id = scope.portfolio.legacy_portfolio_id
    assert legacy_id is not None

    # Posición con valor de mercado alto (via precio transaccional) → equity >> cash.
    instrument = await _new_instrument(db_session, "insf")
    await db_session.flush()
    portfolio_row = (
        await db_session.execute(select(PortfolioRow).where(PortfolioRow.id == legacy_id))
    ).scalar_one()
    position = PositionRow(
        id=f"pos-{uuid4().hex[:8]}",
        portfolio_id=portfolio_row.id,
        instrument_id=instrument.id,
        quantity=Decimal("1000"),
        avg_cost=Decimal("100"),
        updated_at=_now(),
    )
    db_session.add(position)
    tx = TransactionRow(
        id=f"tx-{uuid4().hex[:8]}",
        portfolio_id=portfolio_row.id,
        instrument_id=instrument.id,
        type="buy",
        quantity=Decimal("1000"),
        price=Decimal("150"),
        total=Decimal("150000"),
        executed_at=_now(),
        idempotency_key=None,
    )
    db_session.add(tx)
    # Cash bajo (se reduce DIRECTAMENTE en la fila, B-3: muta cash SIN ledger; es la
    # escena documental del agujero, no un guard). cash=10 << fee.
    portfolio_row.cash = Decimal("10")
    portfolio_row.updated_at = _now()
    await db_session.commit()

    # fee = (cash + market_value) * pct/100 = (10 + 150000) * 0.2/100 ≈ 300 > cash 10.
    n_custody_before = len(
        (
            await db_session.execute(
                select(LedgerEntryRow.id).where(
                    LedgerEntryRow.account_id == account_id,
                    LedgerEntryRow.reference_type == "custody",
                )
            )
        ).scalars().all()
    )

    applied = await ApplyCustodyFees(
        account_repo,
        portfolio_repo,
        ledger_repo,
        custody_obligation_repo=obligation_repo,
    ).execute(scope)

    # El cargo queda registrado como pendiente; get devuelve True pero NO hay cargo.
    assert applied is True

    # NO se escribió ninguna fila ledger de custodia nueva.
    n_custody_after = len(
        (
            await db_session.execute(
                select(LedgerEntryRow).where(
                    LedgerEntryRow.account_id == account_id,
                    LedgerEntryRow.reference_type == "custody",
                )
            )
        ).scalars().all()
    )
    assert n_custody_after == n_custody_before == 0

    # Cash sin cambio (no se descuenta).
    fresh = (
        await db_session.execute(select(PortfolioRow).where(PortfolioRow.id == legacy_id))
    ).scalar_one()
    assert fresh.cash == Decimal("10")

    # Obligación PENDING con el resto pendiente por cobrar.
    oblig = (
        await db_session.execute(
            select(CustodyObligationRow).where(
                CustodyObligationRow.account_id == account_id
            )
        )
    ).scalar_one()
    assert oblig.status == "PENDING"
    assert float(oblig.total_fee) > 10.0  # fee > cash
    assert oblig.outstanding == oblig.total_fee - 10  # resto pendiente
    # Limpieza R000: este test hizo commit (montaje de posición + cash bajo), así que la
    # cuenta simulada persiste → ciérrala y bórrala físicamente (m2-insf, confirmada en el plan).
    await _cleanup_account(db_session, account_id)
    await _cleanup_instrument(db_session, instrument)


@pytest.mark.asyncio
async def test_recomputed_es_coherente_a_nivel_account(db_session: AsyncSession) -> None:
    """El re-compute M-2 es a nivel ACCOUNT, no legacy-portfolio suelto.

    Dos cuentas con distinto seed: ``sum_cash_amounts`` de la cuenta A solo suma SU
    traza ledger (nunca la de B), y el cash del account A solo suma SUS legacy carteras.

    Limpieza (R000): ambas cuentas simuladas se cierran y borran físicamente al final.
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
    # Limpieza R000: ambas cuentas (crea 2 por test).
    await _cleanup_account(db_session, account_a)
    await _cleanup_account(db_session, account_b)


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

    Limpieza (R000): la cuenta simulada se cierra y borra físicamente SIEMPRE (``finally``),
    incluso cuando el assert de reconciliación falla (que es precisamente lo que documenta el xfail).
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
    try:
        await _assert_reconciled(db_session, ledger_repo, account_id)
    finally:
        # Limpieza R000: garantizada aunque el assert (xfail) falle antes de llegar aquí.
        await _cleanup_account(db_session, account_id)
