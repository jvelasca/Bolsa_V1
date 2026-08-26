"""Repositorio SQLAlchemy de cuentas de inversión (CRUD + scope operativo)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bolsa_domain.account_settings import (
    AccountSettings,
    default_account_settings,
    settings_from_dict,
    settings_to_dict,
)
from bolsa_domain.entities.account import AccountScope, InvestmentAccount, InvestmentPortfolio
from bolsa_infrastructure.config import get_settings as load_app_settings
from bolsa_infrastructure.database.models import (
    ConfidenceStateRow,
    DecisionMemoryRow,
    DecisionSessionRow,
    EdgeReportRow,
    InvestmentAccountRow,
    InvestmentPortfolioRow,
    LedgerEntryRow,
    PendingOrderRow,
    PortfolioRow,
    PositionRow,
    TransactionRow,
    TrialRecordRow,
)
from bolsa_infrastructure.ids import new_id


def _app_owner_id() -> str:
    return load_app_settings().owner_principal()


def _account_visible_to_owner(user_id: str | None, owner_user_id: str) -> bool:
    """F7c: match estricto ``user_id == owner``; NULL nunca visible."""
    return user_id == owner_user_id


def _owner_visibility_clause(owner_user_id: str) -> Any:
    """F7c: filtra solo ``user_id == owner`` (legacy NULL excluido)."""
    return InvestmentAccountRow.user_id == owner_user_id


def _account_from_row(row: InvestmentAccountRow) -> InvestmentAccount:
    raw_settings = dict(row.settings_json) if row.settings_json else None
    if raw_settings and "investorProfile" in raw_settings:
        # Clave obsoleta: perfil vive en investor_profiles + active_profile_id
        raw_settings = {k: v for k, v in raw_settings.items() if k != "investorProfile"}
    lab_evidence = None
    if raw_settings and isinstance(raw_settings.get("labEvidence"), dict):
        lab_evidence = dict(raw_settings["labEvidence"])
    return InvestmentAccount(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        description=row.description,
        type=row.type,
        status=row.status,
        currency=row.currency,
        base_currency=row.base_currency,
        initial_deposit=float(row.initial_deposit),
        leverage=float(row.leverage),
        margin_call_level_pct=float(row.margin_call_level_pct)
        if row.margin_call_level_pct is not None
        else None,
        is_default=row.is_default,
        settings=settings_from_dict(raw_settings),
        strategy_definition_id=row.strategy_definition_id,
        source_backtest_run_id=row.source_backtest_run_id,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
        last_activity_at=row.last_activity_at.isoformat() if row.last_activity_at else None,
        active_profile_id=getattr(row, "active_profile_id", None),
        lab_evidence=lab_evidence,
    )


def _portfolio_from_row(row: InvestmentPortfolioRow) -> InvestmentPortfolio:
    return InvestmentPortfolio(
        id=row.id,
        account_id=row.account_id,
        legacy_portfolio_id=row.legacy_portfolio_id,
        name=row.name,
        description=row.description,
        strategy_tag=row.strategy_tag,
        sort_order=row.sort_order,
        is_default=row.is_default,
    )


class SqlAlchemyAccountRepository:
    """Persistencia de cuentas; altas nuevas llevan ``user_id`` del owner single-tenant."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_scope(
        self,
        account_id: str | None,
        portfolio_id: str | None = None,
    ) -> AccountScope:
        if account_id:
            stmt = (
                select(InvestmentAccountRow)
                .where(
                    InvestmentAccountRow.id == account_id,
                    InvestmentAccountRow.status == "active",
                )
                .options(selectinload(InvestmentAccountRow.portfolios))
            )
            account_row = (await self._session.execute(stmt)).scalar_one_or_none()
            if account_row is None:
                raise ValueError("Cuenta no encontrada o inactiva")
        else:
            stmt = (
                select(InvestmentAccountRow)
                .where(InvestmentAccountRow.is_default.is_(True))
                .options(selectinload(InvestmentAccountRow.portfolios))
            )
            account_row = (await self._session.execute(stmt)).scalar_one_or_none()
            if account_row is None:
                raise ValueError("No hay cuenta por defecto")

        # Una cuenta = una cartera operativa (modelo XTB; portfolio_id ignorado).
        portfolio_row = next(
            (item for item in account_row.portfolios if item.is_default),
            account_row.portfolios[0] if account_row.portfolios else None,
        )
        if portfolio_row is None or not portfolio_row.legacy_portfolio_id:
            raise ValueError("La cuenta no tiene cartera legacy vinculada")

        return AccountScope(
            account=_account_from_row(account_row),
            portfolio=_portfolio_from_row(portfolio_row),
            legacy_portfolio_id=portfolio_row.legacy_portfolio_id,
        )

    async def resolve_scope(
        self,
        account_id: str | None,
        portfolio_id: str | None = None,
    ) -> AccountScope:
        return await self._load_scope(account_id, portfolio_id)

    async def list_accounts(
        self,
        account_type: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[InvestmentAccount]:
        """Lista cuentas del owner; match estricto ``user_id == owner`` (F7c)."""
        owner = owner_user_id if owner_user_id is not None else _app_owner_id()
        stmt = (
            select(InvestmentAccountRow)
            .where(_owner_visibility_clause(owner))
            .order_by(
                InvestmentAccountRow.is_default.desc(),
                InvestmentAccountRow.created_at.asc(),
            )
        )
        if account_type:
            stmt = stmt.where(InvestmentAccountRow.type == account_type)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_account_from_row(row) for row in rows]

    async def list_active_accounts(
        self,
        *,
        owner_user_id: str | None = None,
        for_custody_job: bool = False,
    ) -> list[InvestmentAccount]:
        """Cuentas ACTIVAS (R-10 F4b): mismo orden que ``list_accounts``, filtrando
        ``status == "active"`` (literal idéntico al de ``_load_scope``).

        - ``for_custody_job=True``: **system job scope** — todas las cuentas activas
          (custodia per-account; solo jobs internos, nunca HTTP).
        - ``owner_user_id`` explícito: misma visibilidad que ``list_accounts`` (F7c).
        - Sin ``for_custody_job`` y sin ``owner_user_id``: scope al owner bootstrap
          (nunca lista all-tenants por omisión)."""
        stmt = select(InvestmentAccountRow).where(
            InvestmentAccountRow.status == "active",
        )
        if for_custody_job:
            if owner_user_id is not None:
                raise ValueError(
                    "for_custody_job y owner_user_id son mutuamente excluyentes",
                )
        else:
            owner = owner_user_id if owner_user_id is not None else _app_owner_id()
            stmt = stmt.where(_owner_visibility_clause(owner))
        stmt = stmt.order_by(
            InvestmentAccountRow.is_default.desc(),
            InvestmentAccountRow.created_at.asc(),
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_account_from_row(row) for row in rows]

    async def get_account(
        self,
        account_id: str,
        owner_user_id: str | None = None,
    ) -> InvestmentAccount:
        """Carga por id. ``user_id`` ajeno se trata como no encontrada (no 500)."""
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            raise ValueError("Cuenta no encontrada")
        owner = owner_user_id if owner_user_id is not None else _app_owner_id()
        if not _account_visible_to_owner(row.user_id, owner):
            raise ValueError("Cuenta no encontrada")
        return _account_from_row(row)

    async def _create_investment_account(
        self,
        *,
        account_type: str,
        name: str,
        description: str | None = None,
        currency: str = "EUR",
        base_currency: str | None = None,
        initial_deposit: float = 100_000.0,
        leverage: float = 1.0,
        margin_call_level_pct: float | None = 100.0,
        portfolio_name: str | None = None,
        portfolio_description: str | None = None,
        strategy_tag: str | None = "core",
        settings: AccountSettings | None = None,
        commission_preset_id: str | None = None,
        strategy_definition_id: str | None = None,
        source_backtest_run_id: str | None = None,
    ) -> AccountScope:
        now = datetime.now(UTC)
        deposit = Decimal(str(initial_deposit))
        base = base_currency or currency
        resolved_settings = settings or default_account_settings(
            commission_preset_id or "standard_es",
            "ES",
        )
        if commission_preset_id and settings is None:
            resolved_settings = default_account_settings(commission_preset_id, "ES")

        default_name = "Cuenta simulada" if account_type == "simulated" else "Cuenta paper"
        account = InvestmentAccountRow(
            id=new_id(),
            user_id=_app_owner_id(),
            name=name.strip() or default_name,
            description=description,
            type=account_type,
            status="active",
            currency=currency,
            base_currency=base,
            initial_deposit=deposit,
            leverage=Decimal(str(leverage)),
            margin_call_level_pct=Decimal(str(margin_call_level_pct))
            if margin_call_level_pct is not None
            else None,
            is_default=False,
            settings_json=settings_to_dict(resolved_settings),
            strategy_definition_id=strategy_definition_id,
            source_backtest_run_id=source_backtest_run_id,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
        )
        self._session.add(account)
        await self._session.flush()

        legacy = PortfolioRow(
            id=new_id(),
            name=f"{account.name} — cartera",
            currency=currency,
            cash=deposit,
            created_at=now,
            updated_at=now,
        )
        self._session.add(legacy)
        await self._session.flush()

        inv_portfolio = InvestmentPortfolioRow(
            id=new_id(),
            account_id=account.id,
            legacy_portfolio_id=legacy.id,
            name=portfolio_name or "Cartera principal",
            description=portfolio_description,
            strategy_tag=strategy_tag,
            sort_order=0,
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        self._session.add(inv_portfolio)

        deposit_label = "Depósito inicial"
        if account_type == "paper":
            deposit_label = "Depósito inicial (paper forward-test)"
        self._session.add(
            LedgerEntryRow(
                id=new_id(),
                account_id=account.id,
                portfolio_id=inv_portfolio.id,
                type="deposit",
                amount=deposit,
                currency=currency,
                balance_after=deposit,
                reference_type="manual",
                reference_id=account.id,
                description=deposit_label,
                executed_at=now,
                created_at=now,
            ),
        )
        await self._session.flush()

        return AccountScope(
            account=_account_from_row(account),
            portfolio=_portfolio_from_row(inv_portfolio),
            legacy_portfolio_id=legacy.id,
        )

    async def create_simulated_account(
        self,
        *,
        name: str,
        description: str | None = None,
        currency: str = "EUR",
        base_currency: str | None = None,
        initial_deposit: float = 100_000.0,
        leverage: float = 1.0,
        margin_call_level_pct: float | None = 100.0,
        portfolio_name: str | None = None,
        portfolio_description: str | None = None,
        strategy_tag: str | None = "core",
        settings: AccountSettings | None = None,
        commission_preset_id: str | None = None,
    ) -> AccountScope:
        return await self._create_investment_account(
            account_type="simulated",
            name=name,
            description=description,
            currency=currency,
            base_currency=base_currency,
            initial_deposit=initial_deposit,
            leverage=leverage,
            margin_call_level_pct=margin_call_level_pct,
            portfolio_name=portfolio_name,
            portfolio_description=portfolio_description,
            strategy_tag=strategy_tag,
            settings=settings,
            commission_preset_id=commission_preset_id,
        )

    async def create_paper_account(
        self,
        *,
        name: str,
        description: str | None = None,
        currency: str = "EUR",
        base_currency: str | None = None,
        initial_deposit: float = 10_000.0,
        leverage: float = 1.0,
        margin_call_level_pct: float | None = 100.0,
        portfolio_name: str | None = None,
        portfolio_description: str | None = None,
        strategy_tag: str | None = "paper",
        settings: AccountSettings | None = None,
        commission_preset_id: str | None = None,
        strategy_definition_id: str,
        source_backtest_run_id: str | None = None,
    ) -> AccountScope:
        return await self._create_investment_account(
            account_type="paper",
            name=name,
            description=description,
            currency=currency,
            base_currency=base_currency,
            initial_deposit=initial_deposit,
            leverage=leverage,
            margin_call_level_pct=margin_call_level_pct,
            portfolio_name=portfolio_name,
            portfolio_description=portfolio_description,
            strategy_tag=strategy_tag,
            settings=settings,
            commission_preset_id=commission_preset_id,
            strategy_definition_id=strategy_definition_id,
            source_backtest_run_id=source_backtest_run_id,
        )

    async def update_settings(self, account_id: str, settings: AccountSettings) -> InvestmentAccount:
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            raise ValueError("Cuenta no encontrada")
        previous = dict(row.settings_json) if row.settings_json else {}
        merged = settings_to_dict(settings)
        # Preservar claves operativas no modeladas en AccountSettings
        for key in ("equityMarks", "labEvidence", "brokerVenue"):
            if key in previous and key not in merged:
                merged[key] = previous[key]
        row.settings_json = merged
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _account_from_row(row)

    async def get_settings_json(self, account_id: str) -> dict[str, Any] | None:
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            raise ValueError("Cuenta no encontrada")
        return dict(row.settings_json) if row.settings_json else None

    async def merge_settings_json(self, account_id: str, fragment: dict[str, Any]) -> dict[str, Any]:
        """Fusiona claves en settings_json sin pasar por AccountSettings (F4 equityMarks)."""
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            raise ValueError("Cuenta no encontrada")
        current = dict(row.settings_json) if row.settings_json else settings_to_dict(default_account_settings())
        current.update(fragment)
        row.settings_json = current
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return current

    async def get_settings(self, account_id: str) -> AccountSettings:
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            raise ValueError("Cuenta no encontrada")
        return settings_from_dict(row.settings_json)

    async def touch_activity(self, account_id: str) -> None:
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            return
        now = datetime.now(UTC)
        row.last_activity_at = now
        row.updated_at = now

    async def list_portfolios(self, account_id: str) -> list[InvestmentPortfolio]:
        stmt = (
            select(InvestmentPortfolioRow)
            .where(InvestmentPortfolioRow.account_id == account_id)
            .order_by(InvestmentPortfolioRow.sort_order.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_portfolio_from_row(row) for row in rows]

    async def update_account(
        self,
        account_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> InvestmentAccount:
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            raise ValueError("Cuenta no encontrada")
        if row.status == "closed":
            raise ValueError("No se puede editar una cuenta cerrada")
        now = datetime.now(UTC)
        if name is not None and name.strip():
            row.name = name.strip()
        if description is not None:
            row.description = description.strip() or None
        row.updated_at = now
        await self._session.flush()
        return _account_from_row(row)

    async def set_default_account(self, account_id: str) -> InvestmentAccount:
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            raise ValueError("Cuenta no encontrada")
        if row.status != "active":
            raise ValueError("Solo una cuenta activa puede marcarse como principal")
        await self._session.execute(
            update(InvestmentAccountRow)
            .where(InvestmentAccountRow.id != account_id)
            .values(is_default=False),
        )
        row.is_default = True
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _account_from_row(row)

    async def close_account(self, account_id: str) -> InvestmentAccount:
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            raise ValueError("Cuenta no encontrada")
        if row.status == "closed":
            return _account_from_row(row)
        now = datetime.now(UTC)
        row.status = "closed"
        row.updated_at = now
        row.last_activity_at = now
        await self._session.flush()
        return _account_from_row(row)

    async def delete_simulated_account(self, account_id: str) -> None:
        row = await self._session.get(InvestmentAccountRow, account_id)
        if row is None:
            raise ValueError("Cuenta no encontrada")
        if row.type != "simulated":
            raise ValueError("Solo se pueden eliminar cuentas simuladas (modo demo)")
        if row.status != "closed":
            raise ValueError("Cierra la cuenta antes de eliminarla (conservación contable)")

        portfolios_stmt = select(InvestmentPortfolioRow).where(
            InvestmentPortfolioRow.account_id == account_id,
        )
        portfolio_rows = (await self._session.execute(portfolios_stmt)).scalars().all()
        legacy_ids = [p.legacy_portfolio_id for p in portfolio_rows if p.legacy_portfolio_id]

        # Orden de borrado respeta las FK:
        #   positions/transactions -> portfolios (legacy)
        #   ledger_entries        -> investment_portfolios
        #   investment_portfolios -> portfolios (legacy)
        # Por eso se borran primero los hijos, luego investment_portfolios y por
        # último las portfolios legacy (evita ForeignKeyViolation).
        for legacy_id in legacy_ids:
            await self._session.execute(
                delete(PositionRow).where(PositionRow.portfolio_id == legacy_id),
            )
            await self._session.execute(
                delete(TransactionRow).where(TransactionRow.portfolio_id == legacy_id),
            )

        await self._session.execute(
            delete(LedgerEntryRow).where(LedgerEntryRow.account_id == account_id),
        )
        await self._session.execute(
            delete(PendingOrderRow).where(PendingOrderRow.account_id == account_id),
        )
        await self._session.execute(
            delete(InvestmentPortfolioRow).where(InvestmentPortfolioRow.account_id == account_id),
        )
        for legacy_id in legacy_ids:
            await self._session.execute(delete(PortfolioRow).where(PortfolioRow.id == legacy_id))

        # Referencias sueltas (sin FK): desvincular, conservar filas de auditoría cognitiva
        for model in (
            DecisionMemoryRow,
            DecisionSessionRow,
            TrialRecordRow,
            ConfidenceStateRow,
            EdgeReportRow,
        ):
            await self._session.execute(
                update(model).where(model.account_id == account_id).values(account_id=None),
            )

        was_default = row.is_default
        await self._session.delete(row)
        await self._session.flush()

        if was_default:
            stmt = (
                select(InvestmentAccountRow)
                .where(InvestmentAccountRow.status == "active")
                .order_by(InvestmentAccountRow.created_at.asc())
                .limit(1)
            )
            next_default = (await self._session.execute(stmt)).scalar_one_or_none()
            if next_default is not None:
                next_default.is_default = True
                await self._session.flush()
