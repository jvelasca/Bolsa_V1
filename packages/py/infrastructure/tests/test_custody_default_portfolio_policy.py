"""R-12 A2 / ADR 026 — política ``custody_charge_source = DEFAULT_PORTFOLIO``.

La custodia es obligación de la **cuenta**: el importe se calcula sobre el
``total_equity`` agregado de todas las carteras, pero el cobro se hace
**exclusivamente** desde la cartera default (``scope.portfolio`` vía
``resolve_scope(account_id)``). No hay transferencia implícita desde una
cartera no-default con cash hacia la default sin cash.

Este test lo fija contra PostgreSQL real (docker ``bolsa-postgres``): cartera A
default con cash 0, cartera B no-default con cash 10_000, ``custody_annual_pct=5.0``
→ fee ≈ 500. Si A no cubre el fee, la obligación queda PENDING, B no se toca y
no se escribe ledger de custodia. Patrón de fábrica/skip/cleanup heredado de
``test_custody_concurrency_chaos.py`` (sesiones independientes; no se toca
producción).
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from bolsa_domain.account_settings import AccountSettings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_infrastructure.database.models import (
    CustodyObligationRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PortfolioRow,
)
from bolsa_infrastructure.ids import new_id

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_FEE_PCT = 5.0
_CASH_B = Decimal("10000")
_EXPECTED_FEE = 500.0
_FEE_TOLERANCE = 0.01


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


@asynccontextmanager
async def _factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Engine nuevo + session_factory; ``pytest.skip`` si PostgreSQL no responde."""
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
    try:
        yield factory
    finally:
        await engine.dispose()


def _now() -> datetime:
    return datetime.now(UTC)


def _current_period() -> str:
    return _now().strftime("%Y")


def _settings_with_custody(pct: float) -> AccountSettings:
    from bolsa_domain.account_settings import settings_from_dict

    # ``presetId=custom``: si no, ``settings_from_dict`` ignora el override y usa
    # el preset ``standard_es`` (custody 0.2 %). Aquí el escenario exige 5 %.
    return settings_from_dict(
        {
            "commission": {"presetId": "custom", "custodyAnnualPct": pct},
            "tax": {"costBasisMethod": "FIFO"},
        }
    )


async def _cleanup(session: AsyncSession, account_id: str) -> None:
    """Cierra y borra la cuenta simulada (R000: no contaminar la BD compartida)."""
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )

    repo = SqlAlchemyAccountRepository(session)
    try:
        await repo.close_account(account_id)
        await repo.delete_simulated_account(account_id)
        await session.commit()
    except Exception:  # noqa: BLE001 - cleanup best-effort
        await session.rollback()


async def _seed_non_default_portfolio(
    session: AsyncSession,
    *,
    account_id: str,
    account_name: str,
    currency: str,
) -> str:
    """Inserta cartera B (no default, cash 10_000) + depósito ledger M-2.

    ``reference_id`` es el id de la investment portfolio (no ``account_id``) para no
    chocar con el UNIQUE parcial del depósito inicial de A (``reference_type=manual``).
    """
    now = _now()
    legacy = PortfolioRow(
        id=new_id(),
        name=f"{account_name} — cartera B",
        currency=currency,
        cash=_CASH_B,
        created_at=now,
        updated_at=now,
    )
    session.add(legacy)
    await session.flush()

    inv_portfolio = InvestmentPortfolioRow(
        id=new_id(),
        account_id=account_id,
        legacy_portfolio_id=legacy.id,
        name="Cartera B (no default)",
        description=None,
        strategy_tag="satellite",
        sort_order=1,
        is_default=False,
        created_at=now,
        updated_at=now,
    )
    session.add(inv_portfolio)

    session.add(
        LedgerEntryRow(
            id=new_id(),
            account_id=account_id,
            portfolio_id=inv_portfolio.id,
            type="deposit",
            amount=_CASH_B,
            currency=currency,
            balance_after=_CASH_B,
            reference_type="manual",
            reference_id=inv_portfolio.id,
            description="Depósito inicial cartera B",
            executed_at=now,
            created_at=now,
        ),
    )
    await session.flush()
    return legacy.id


async def _apply_custody_fees(
    factory: async_sessionmaker[AsyncSession],
    account_id: str,
) -> bool:
    """``ApplyCustodyFees.execute`` en sesión independiente (mismo patrón que chaos)."""
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

    async with factory() as session:
        acc = SqlAlchemyAccountRepository(session)
        scope = await acc.resolve_scope(account_id)
        applied = await ApplyCustodyFees(
            acc,
            SqlAlchemyPortfolioRepository(session),
            SqlAlchemyLedgerRepository(session),
            custody_obligation_repo=CustodyObligationRepository(session),
        ).execute(scope)
        await session.commit()
        return applied


async def _portfolio_cash(session: AsyncSession, legacy_id: str) -> Decimal:
    cash = (
        await session.execute(select(PortfolioRow.cash).where(PortfolioRow.id == legacy_id))
    ).scalar_one()
    return Decimal(str(cash))


async def _count_custody_entries(session: AsyncSession, account_id: str, period: str) -> int:
    stmt = select(func.count(LedgerEntryRow.id)).where(
        LedgerEntryRow.account_id == account_id,
        LedgerEntryRow.reference_type == "custody",
        LedgerEntryRow.reference_id == f"custody-{period}",
    )
    return int((await session.execute(stmt)).scalar_one())


async def _account_total_cash(session: AsyncSession, account_id: str) -> Decimal:
    stmt = (
        select(PortfolioRow.cash)
        .join(
            InvestmentPortfolioRow,
            InvestmentPortfolioRow.legacy_portfolio_id == PortfolioRow.id,
        )
        .where(InvestmentPortfolioRow.account_id == account_id)
    )
    cash_values = (await session.execute(stmt)).scalars().all()
    return sum((c for c in cash_values), Decimal("0"))


@pytest.mark.asyncio
async def test_default_portfolio_policy_no_implicit_transfer_from_funded_sibling() -> None:
    """Fee sobre equity agregado; cobro SOLO desde A (default). B no se descuenta.

    Consecuencia de negocio (auditor P2 / ADR 026 ``DEFAULT_PORTFOLIO``): si la
    cartera default no tiene cash y otra cartera de la misma cuenta sí, el job
    **no** transfiere implícitamente de B a A. Se registra la obligación PENDING
    (``outstanding ≈ fee``, ``total_fee ≈ 500``), A sigue en 0, B conserva sus
    10_000 y no hay filas ledger ``reference_type="custody"`` del periodo.
    ``Σ ledger == Σ cash`` se mantiene (depósito 0 de A + depósito 10k de B).
    """
    from bolsa_infrastructure.database.repositories.account_repository import (
        SqlAlchemyAccountRepository,
    )
    from bolsa_infrastructure.database.repositories.ledger_repository import (
        SqlAlchemyLedgerRepository,
    )

    account_id: str | None = None
    async with _factory() as factory:
        try:
            async with factory() as setup:
                scope = await SqlAlchemyAccountRepository(setup).create_simulated_account(
                    name=f"R12A2 default-pf {new_id()[:8]}",
                    initial_deposit=0.0,
                    settings=_settings_with_custody(_FEE_PCT),
                )
                account_id = scope.account.id
                legacy_a_id = scope.portfolio.legacy_portfolio_id
                assert legacy_a_id is not None
                assert scope.portfolio.is_default is True

                legacy_b_id = await _seed_non_default_portfolio(
                    setup,
                    account_id=account_id,
                    account_name=scope.account.name,
                    currency=scope.account.currency,
                )
                await setup.commit()

            applied = await _apply_custody_fees(factory, account_id)
            assert applied is True, "la obligación del periodo debe registrarse (PENDING)"

            period = _current_period()
            async with factory() as check:
                obligation = (
                    await check.execute(
                        select(CustodyObligationRow).where(
                            CustodyObligationRow.account_id == account_id,
                            CustodyObligationRow.period == period,
                        )
                    )
                ).scalar_one()
                assert obligation.status == "PENDING"
                assert float(obligation.outstanding) == pytest.approx(
                    _EXPECTED_FEE, abs=_FEE_TOLERANCE
                )
                assert float(obligation.total_fee) == pytest.approx(
                    _EXPECTED_FEE, abs=_FEE_TOLERANCE
                )

                cash_a = await _portfolio_cash(check, legacy_a_id)
                cash_b = await _portfolio_cash(check, legacy_b_id)
                assert cash_a == Decimal("0")
                assert cash_b == _CASH_B

                assert await _count_custody_entries(check, account_id, period) == 0

                ledger_total = await SqlAlchemyLedgerRepository(check).sum_cash_amounts(
                    account_id
                )
                cash_total = await _account_total_cash(check, account_id)
                assert cash_total == _CASH_B
                assert ledger_total == cash_total, (
                    f"Σ ledger={ledger_total} != Σ cash={cash_total} (account {account_id})"
                )
        finally:
            if account_id is not None:
                async with factory() as cleanup_session:
                    await _cleanup(cleanup_session, account_id)
