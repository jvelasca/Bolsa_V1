from bolsa_domain.account_settings import (
    AccountSettings,
    CommissionProfile,
    TaxProfile,
)
from bolsa_domain.entities.account import (
    AccountSummary,
    CashMovementResult,
    InvestmentAccount,
    InvestmentPortfolio,
    LedgerEntry,
)
from bolsa_domain.tax_report import TaxReportSummary
from bolsa_api.schemas.accounts import (
    AccountSettingsDto,
    AccountSummaryDto,
    CashMovementResultDto,
    CommissionProfileDto,
    InvestmentAccountDto,
    InvestmentPortfolioDto,
    LedgerEntryDto,
    RealizedGainLineDto,
    TaxProfileDto,
    TaxReportSummaryDto,
    UnrealizedGainLineDto,
)


def _commission_to_dto(profile: CommissionProfile) -> CommissionProfileDto:
    return CommissionProfileDto(
        preset_id=profile.preset_id,
        label=profile.label,
        stock_commission_pct=profile.stock_commission_pct,
        stock_commission_min=profile.stock_commission_min,
        stock_commission_max=profile.stock_commission_max,
        vat_on_commission_pct=profile.vat_on_commission_pct,
        fx_conversion_pct=profile.fx_conversion_pct,
        custody_annual_pct=profile.custody_annual_pct,
    )


def _tax_to_dto(tax: TaxProfile) -> TaxProfileDto:
    return TaxProfileDto(
        jurisdiction=tax.jurisdiction,
        cost_basis_method=tax.cost_basis_method,
        stamp_duty_buy_pct=tax.stamp_duty_buy_pct,
        dividend_withholding_pct=tax.dividend_withholding_pct,
        capital_gains_tax_pct=tax.capital_gains_tax_pct,
        fiscal_year_start_month=tax.fiscal_year_start_month,
    )


def _settings_to_dto(settings: AccountSettings | None) -> AccountSettingsDto | None:
    if settings is None:
        return None
    return AccountSettingsDto(
        commission=_commission_to_dto(settings.commission),
        tax=_tax_to_dto(settings.tax),
        notes=settings.notes,
    )


def settings_dto_to_domain(dto: AccountSettingsDto) -> AccountSettings:
    return AccountSettings(
        commission=CommissionProfile(
            preset_id=dto.commission.preset_id,
            label=dto.commission.label,
            stock_commission_pct=dto.commission.stock_commission_pct,
            stock_commission_min=dto.commission.stock_commission_min,
            stock_commission_max=dto.commission.stock_commission_max,
            vat_on_commission_pct=dto.commission.vat_on_commission_pct,
            fx_conversion_pct=dto.commission.fx_conversion_pct,
            custody_annual_pct=dto.commission.custody_annual_pct,
        ),
        tax=TaxProfile(
            jurisdiction=dto.tax.jurisdiction,
            cost_basis_method=dto.tax.cost_basis_method,
            stamp_duty_buy_pct=dto.tax.stamp_duty_buy_pct,
            dividend_withholding_pct=dto.tax.dividend_withholding_pct,
            capital_gains_tax_pct=dto.tax.capital_gains_tax_pct,
            fiscal_year_start_month=dto.tax.fiscal_year_start_month,
        ),
        notes=dto.notes,
    )


def to_investment_account_dto(account: InvestmentAccount) -> InvestmentAccountDto:
    return InvestmentAccountDto(
        id=account.id,
        user_id=account.user_id,
        name=account.name,
        description=account.description,
        type=account.type,
        status=account.status,
        currency=account.currency,
        base_currency=account.base_currency,
        initial_deposit=account.initial_deposit,
        leverage=account.leverage,
        margin_call_level_pct=account.margin_call_level_pct,
        is_default=account.is_default,
        settings=_settings_to_dto(account.settings),
        active_profile_id=account.active_profile_id,
        created_at=account.created_at,
        updated_at=account.updated_at,
        last_activity_at=account.last_activity_at,
        strategy_definition_id=account.strategy_definition_id,
        source_backtest_run_id=account.source_backtest_run_id,
        lab_evidence=getattr(account, "lab_evidence", None),
    )


def to_investment_portfolio_dto(portfolio: InvestmentPortfolio) -> InvestmentPortfolioDto:
    return InvestmentPortfolioDto(
        id=portfolio.id,
        account_id=portfolio.account_id,
        legacy_portfolio_id=portfolio.legacy_portfolio_id,
        name=portfolio.name,
        description=portfolio.description,
        strategy_tag=portfolio.strategy_tag,
        sort_order=portfolio.sort_order,
        is_default=portfolio.is_default,
    )


def to_account_summary_dto(summary: AccountSummary) -> AccountSummaryDto:
    return AccountSummaryDto(
        account=to_investment_account_dto(summary.account),
        default_portfolio=to_investment_portfolio_dto(summary.default_portfolio),
        cash=summary.cash,
        total_market_value=summary.total_market_value,
        total_cost=summary.total_cost,
        total_unrealized_pnl=summary.total_unrealized_pnl,
        total_equity=summary.total_equity,
        margin_used=summary.margin_used,
        free_margin=summary.free_margin,
        margin_level_pct=summary.margin_level_pct,
        positions_count=summary.positions_count,
    )


def to_ledger_entry_dto(entry: LedgerEntry) -> LedgerEntryDto:
    return LedgerEntryDto(
        id=entry.id,
        account_id=entry.account_id,
        portfolio_id=entry.portfolio_id,
        type=entry.type,
        amount=entry.amount,
        currency=entry.currency,
        balance_after=entry.balance_after,
        instrument_id=entry.instrument_id,
        symbol=entry.symbol,
        quantity=entry.quantity,
        price=entry.price,
        reference_type=entry.reference_type,
        reference_id=entry.reference_id,
        description=entry.description,
        executed_at=entry.executed_at,
    )


def to_cash_movement_result_dto(result: CashMovementResult) -> CashMovementResultDto:
    return CashMovementResultDto(
        id=result.id,
        account_id=result.account_id,
        portfolio_id=result.portfolio_id,
        kind=result.kind,
        amount=result.amount,
        currency=result.currency,
        balance_after=result.balance_after,
        executed_at=result.executed_at,
        description=result.description,
    )


def to_tax_report_dto(report: TaxReportSummary) -> TaxReportSummaryDto:
    return TaxReportSummaryDto(
        account_id=report.account_id,
        currency=report.currency,
        method=report.method,
        jurisdiction=report.jurisdiction,
        year=report.year,
        period_label=report.period_label,
        realized_lines=[
            RealizedGainLineDto(
                id=line.id,
                instrument_id=line.instrument_id,
                symbol=line.symbol,
                sell_transaction_id=line.sell_transaction_id,
                executed_at=line.executed_at,
                quantity=line.quantity,
                sell_price=line.sell_price,
                proceeds=line.proceeds,
                cost_basis=line.cost_basis,
                realized_gain=line.realized_gain,
                method=line.method,
                acquisition_dates=list(line.acquisition_dates),
            )
            for line in report.realized_lines
        ],
        total_gains=report.total_gains,
        total_losses=report.total_losses,
        net_realized_gain=report.net_realized_gain,
        estimated_tax_liability=report.estimated_tax_liability,
        unrealized_lines=[
            UnrealizedGainLineDto(
                instrument_id=line.instrument_id,
                symbol=line.symbol,
                quantity=line.quantity,
                avg_cost=line.avg_cost,
                market_price=line.market_price,
                cost_basis=line.cost_basis,
                market_value=line.market_value,
                unrealized_gain=line.unrealized_gain,
            )
            for line in report.unrealized_lines
        ],
        total_unrealized_gain=report.total_unrealized_gain,
        fees_paid_total=report.fees_paid_total,
        dividend_withholding_pct=report.dividend_withholding_pct,
        open_position_count=report.open_position_count,
    )
