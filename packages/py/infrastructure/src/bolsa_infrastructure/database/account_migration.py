"""Migración de datos de cuentas — fuera del path de petición (P1.2/F3a).

P1.2: el ``SqlAlchemyAccountRepository.ensure_migrated`` hacía seeding/backfill
**destructivo** (``_consolidate_single_portfolio_per_account`` funde/borra) en el
path caliente de cada petición, con un flag ``_migration_done`` por-instancia que,
bajo workers múltiples, reintentaba y producía races.

F3a lo retira del repositorio y lo expone como **paso único al arranque**: tanto
FastAPI (``lifespan``) como el proceso ``scheduler_worker`` lo invocan una vez con
una sesión dedicada. Todas las operaciones son idempotentes (comprobaciones de
existencia + ``reference_id``), por lo que ejecutarlas varias veces es seguro.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from bolsa_domain.account_settings import default_account_settings, settings_to_dict
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import (
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PendingOrderRow,
    PortfolioRow,
    PositionRow,
    TransactionRow,
)
from bolsa_infrastructure.ids import new_id

DEFAULT_ACCOUNT_SEED_ID = "default-account-seed"
DEFAULT_PORTFOLIO_SEED_ID = "default-portfolio-seed"
DEFAULT_PORTFOLIO_NAME = "Cartera principal"
INITIAL_CASH = Decimal(100000)

__all__ = ["run_account_data_migration"]


class _PendingScope:
    """Relación operativa mínima necesaria para la migración (sin mapeo de dominio)."""

    __slots__ = ("account_id", "initial_deposit", "portfolio_id", "legacy_portfolio_id")

    def __init__(
        self,
        account_id: str,
        initial_deposit: Decimal,
        portfolio_id: str,
        legacy_portfolio_id: str,
    ) -> None:
        self.account_id = account_id
        self.initial_deposit = initial_deposit
        self.portfolio_id = portfolio_id
        self.legacy_portfolio_id = legacy_portfolio_id


async def _ensure_default_account(session: AsyncSession) -> None:
    now = datetime.now(UTC)

    legacy_stmt = select(PortfolioRow).where(PortfolioRow.id == DEFAULT_PORTFOLIO_SEED_ID)
    legacy = (await session.execute(legacy_stmt)).scalar_one_or_none()
    if legacy is None:
        legacy_stmt = select(PortfolioRow).where(PortfolioRow.name == DEFAULT_PORTFOLIO_NAME)
        legacy = (await session.execute(legacy_stmt)).scalar_one_or_none()
    if legacy is None:
        legacy = PortfolioRow(
            id=DEFAULT_PORTFOLIO_SEED_ID,
            name=DEFAULT_PORTFOLIO_NAME,
            currency="EUR",
            cash=INITIAL_CASH,
            created_at=now,
            updated_at=now,
        )
        session.add(legacy)
        await session.flush()

    account = await session.get(InvestmentAccountRow, DEFAULT_ACCOUNT_SEED_ID)
    if account is None:
        any_default_stmt = select(InvestmentAccountRow.id).where(
            InvestmentAccountRow.is_default.is_(True),
        )
        has_default = (await session.execute(any_default_stmt)).scalar_one_or_none()
        account = InvestmentAccountRow(
            id=DEFAULT_ACCOUNT_SEED_ID,
            user_id=None,
            name="Cuenta demo EUR",
            type="simulated",
            status="active",
            currency=legacy.currency,
            base_currency=legacy.currency,
            initial_deposit=legacy.cash if legacy.cash > 0 else INITIAL_CASH,
            leverage=Decimal(1),
            margin_call_level_pct=Decimal(100),
            is_default=has_default is None,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        session.add(account)
        await session.flush()

    inv_portfolio_stmt = select(InvestmentPortfolioRow).where(
        InvestmentPortfolioRow.account_id == account.id,
        InvestmentPortfolioRow.is_default.is_(True),
    )
    inv_portfolio = (await session.execute(inv_portfolio_stmt)).scalar_one_or_none()
    if inv_portfolio is None:
        inv_portfolio = InvestmentPortfolioRow(
            id=new_id(),
            account_id=account.id,
            legacy_portfolio_id=legacy.id,
            name=legacy.name,
            description="Cartera principal migrada",
            strategy_tag="core",
            sort_order=0,
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        session.add(inv_portfolio)
        await session.flush()

    if inv_portfolio.legacy_portfolio_id != legacy.id:
        inv_portfolio.legacy_portfolio_id = legacy.id
        inv_portfolio.updated_at = now

    if account.settings_json is None:
        account.settings_json = settings_to_dict(default_account_settings())
        account.description = account.description or "Cuenta demo migrada desde cartera única"

    deposit_stmt = select(LedgerEntryRow.id).where(
        LedgerEntryRow.account_id == account.id,
        LedgerEntryRow.type == "deposit",
        LedgerEntryRow.reference_type == "migration",
    )
    has_deposit = (await session.execute(deposit_stmt)).scalar_one_or_none()
    if has_deposit is None:
        session.add(
            LedgerEntryRow(
                id=new_id(),
                account_id=account.id,
                portfolio_id=inv_portfolio.id,
                type="deposit",
                amount=legacy.cash,
                currency=legacy.currency,
                balance_after=legacy.cash,
                reference_type="migration",
                reference_id="initial-deposit",
                description="Depósito inicial (migración)",
                executed_at=legacy.created_at,
                created_at=now,
            ),
        )

    await session.flush()


async def _load_default_scope(session: AsyncSession) -> _PendingScope:
    stmt = select(InvestmentAccountRow).where(InvestmentAccountRow.is_default.is_(True))
    account_row = (await session.execute(stmt)).scalar_one_or_none()
    if account_row is None:
        raise ValueError("No hay cuenta por defecto")

    portfolios_stmt = select(InvestmentPortfolioRow).where(
        InvestmentPortfolioRow.account_id == account_row.id,
    )
    portfolio_rows = (await session.execute(portfolios_stmt)).scalars().all()
    portfolio_row = next(
        (item for item in portfolio_rows if item.is_default),
        portfolio_rows[0] if portfolio_rows else None,
    )
    if portfolio_row is None or not portfolio_row.legacy_portfolio_id:
        raise ValueError("La cuenta no tiene cartera legacy vinculada")

    return _PendingScope(
        account_id=account_row.id,
        initial_deposit=account_row.initial_deposit,
        portfolio_id=portfolio_row.id,
        legacy_portfolio_id=portfolio_row.legacy_portfolio_id,
    )


async def _backfill_ledger_from_transactions(session: AsyncSession, scope: _PendingScope) -> None:
    existing_stmt = select(LedgerEntryRow.reference_id).where(
        LedgerEntryRow.account_id == scope.account_id,
        LedgerEntryRow.reference_type == "transaction",
    )
    existing_ids = set((await session.execute(existing_stmt)).scalars().all())

    tx_stmt = (
        select(TransactionRow)
        .where(TransactionRow.portfolio_id == scope.legacy_portfolio_id)
        .order_by(TransactionRow.executed_at.asc())
    )
    transactions = (await session.execute(tx_stmt)).scalars().all()
    if not transactions:
        return

    portfolio_row = await session.get(PortfolioRow, scope.legacy_portfolio_id)
    if portfolio_row is None:
        return

    running = scope.initial_deposit
    if existing_ids:
        last_stmt = (
            select(LedgerEntryRow.balance_after)
            .where(LedgerEntryRow.account_id == scope.account_id)
            .order_by(LedgerEntryRow.executed_at.desc())
            .limit(1)
        )
        last_balance = (await session.execute(last_stmt)).scalar_one_or_none()
        if last_balance is not None:
            running = last_balance

    now = datetime.now(UTC)
    for tx in transactions:
        if tx.id in existing_ids:
            continue
        total = float(tx.total)
        amount = -total if tx.type == "buy" else total
        running += Decimal(str(amount))
        session.add(
            LedgerEntryRow(
                id=new_id(),
                account_id=scope.account_id,
                portfolio_id=scope.portfolio_id,
                type=tx.type,
                amount=Decimal(str(amount)),
                currency=portfolio_row.currency,
                balance_after=running,
                instrument_id=tx.instrument_id,
                quantity=tx.quantity,
                price=tx.price,
                reference_type="transaction",
                reference_id=tx.id,
                description=f"Migración transacción {tx.type}",
                executed_at=tx.executed_at,
                created_at=now,
            ),
        )
    await session.flush()


async def _backfill_pending_order_accounts(session: AsyncSession, scope: _PendingScope) -> None:
    await session.execute(
        update(PendingOrderRow)
        .where(PendingOrderRow.account_id.is_(None))
        .values(account_id=scope.account_id),
    )
    await session.flush()


async def _consolidate_single_portfolio_per_account(session: AsyncSession) -> None:
    """Una cuenta = una cartera operativa (modelo XTB). Fusiona subcarteras legacy."""
    account_ids = (await session.execute(select(InvestmentAccountRow.id))).scalars().all()
    for account_id in account_ids:
        stmt = (
            select(InvestmentPortfolioRow)
            .where(InvestmentPortfolioRow.account_id == account_id)
            .order_by(InvestmentPortfolioRow.sort_order.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        if len(rows) <= 1:
            continue

        default_row = next((r for r in rows if r.is_default), rows[0])
        if not default_row.legacy_portfolio_id:
            continue
        default_legacy = await session.get(PortfolioRow, default_row.legacy_portfolio_id)
        if default_legacy is None:
            continue

        for extra in rows:
            if extra.id == default_row.id or not extra.legacy_portfolio_id:
                continue
            extra_legacy = await session.get(PortfolioRow, extra.legacy_portfolio_id)
            if extra_legacy is None:
                await session.delete(extra)
                continue

            default_legacy.cash += extra_legacy.cash
            pos_stmt = select(PositionRow).where(
                PositionRow.portfolio_id == extra.legacy_portfolio_id,
            )
            for pos in (await session.execute(pos_stmt)).scalars().all():
                pos.portfolio_id = default_row.legacy_portfolio_id

            tx_stmt = select(TransactionRow).where(
                TransactionRow.portfolio_id == extra.legacy_portfolio_id,
            )
            for tx in (await session.execute(tx_stmt)).scalars().all():
                tx.portfolio_id = default_row.legacy_portfolio_id

            await session.delete(extra_legacy)
            await session.delete(extra)

        default_legacy.updated_at = datetime.now(UTC)
        await session.flush()


async def run_account_data_migration(session: AsyncSession) -> None:
    """Migración de datos de cuentas idempotente — llamar UNA vez al arranque.

    No debe invocarse en el path de petición (P1.2): ``_consolidate_*`` y los
    backfills son destructivos/backfill y solo tienen sentido como bootstrap.
    """
    await _ensure_default_account(session)
    default_scope = await _load_default_scope(session)
    await _backfill_ledger_from_transactions(session, default_scope)
    await _backfill_pending_order_accounts(session, default_scope)
    await _consolidate_single_portfolio_per_account(session)
    await session.commit()
