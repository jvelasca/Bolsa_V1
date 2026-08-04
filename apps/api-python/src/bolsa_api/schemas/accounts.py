"""DTOs HTTP de cuentas de trading/DEMO."""

from pydantic import BaseModel, ConfigDict, Field


class CommissionProfileDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    preset_id: str = Field(alias="presetId")
    label: str
    stock_commission_pct: float = Field(alias="stockCommissionPct")
    stock_commission_min: float = Field(alias="stockCommissionMin")
    stock_commission_max: float | None = Field(alias="stockCommissionMax")
    vat_on_commission_pct: float = Field(alias="vatOnCommissionPct")
    fx_conversion_pct: float = Field(alias="fxConversionPct")
    custody_annual_pct: float | None = Field(alias="custodyAnnualPct")


class TaxProfileDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    jurisdiction: str
    cost_basis_method: str = Field(alias="costBasisMethod")
    stamp_duty_buy_pct: float = Field(alias="stampDutyBuyPct")
    dividend_withholding_pct: float = Field(alias="dividendWithholdingPct")
    capital_gains_tax_pct: float | None = Field(alias="capitalGainsTaxPct")
    fiscal_year_start_month: int = Field(alias="fiscalYearStartMonth")


class AccountSettingsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    commission: CommissionProfileDto
    tax: TaxProfileDto
    notes: str | None = None


class InvestmentAccountDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    user_id: str | None = Field(alias="userId")
    name: str
    description: str | None = None
    type: str
    status: str
    currency: str
    base_currency: str = Field(alias="baseCurrency")
    initial_deposit: float = Field(alias="initialDeposit")
    leverage: float
    margin_call_level_pct: float | None = Field(alias="marginCallLevelPct")
    is_default: bool = Field(alias="isDefault")
    settings: AccountSettingsDto | None = None
    active_profile_id: str | None = Field(default=None, alias="activeProfileId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    last_activity_at: str | None = Field(alias="lastActivityAt")
    strategy_definition_id: str | None = Field(default=None, alias="strategyDefinitionId")
    source_backtest_run_id: str | None = Field(default=None, alias="sourceBacktestRunId")
    lab_evidence: dict | None = Field(default=None, alias="labEvidence")


class InvestmentPortfolioDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    account_id: str = Field(alias="accountId")
    legacy_portfolio_id: str | None = Field(alias="legacyPortfolioId")
    name: str
    description: str | None
    strategy_tag: str | None = Field(alias="strategyTag")
    sort_order: int = Field(alias="sortOrder")
    is_default: bool = Field(alias="isDefault")


class AccountSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    account: InvestmentAccountDto
    default_portfolio: InvestmentPortfolioDto = Field(alias="defaultPortfolio")
    cash: float
    total_market_value: float = Field(alias="totalMarketValue")
    total_cost: float = Field(alias="totalCost")
    total_unrealized_pnl: float = Field(alias="totalUnrealizedPnl")
    total_equity: float = Field(alias="totalEquity")
    margin_used: float = Field(alias="marginUsed")
    free_margin: float = Field(alias="freeMargin")
    margin_level_pct: float | None = Field(alias="marginLevelPct")
    positions_count: int = Field(alias="positionsCount")


class LedgerEntryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    account_id: str = Field(alias="accountId")
    portfolio_id: str | None = Field(alias="portfolioId")
    type: str
    amount: float
    currency: str
    balance_after: float = Field(alias="balanceAfter")
    instrument_id: str | None = Field(alias="instrumentId")
    symbol: str | None
    quantity: float | None
    price: float | None
    reference_type: str | None = Field(alias="referenceType")
    reference_id: str | None = Field(alias="referenceId")
    description: str | None
    executed_at: str = Field(alias="executedAt")


class CreateAccountInvestorProfileDto(BaseModel):
    """Payload opcional del wizard: crea perfil ART-PROFILE y lo asigna a la cuenta."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    horizon: str = "swing"
    objectives: list[str] = Field(default_factory=lambda: ["growth"])
    risk_tolerance: str = Field(default="moderate", alias="riskTolerance")
    experience: str = "intermediate"
    max_acceptable_loss_pct: float | None = Field(default=None, alias="maxAcceptableLossPct")
    notes: str | None = None
    suggested_policy_template_id: str | None = Field(
        default=None, alias="suggestedPolicyTemplateId"
    )
    selected_policy_template_id: str | None = Field(
        default=None, alias="selectedPolicyTemplateId"
    )


class CreateInvestmentAccountDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    description: str | None = None
    currency: str = "EUR"
    base_currency: str = Field(default="EUR", alias="baseCurrency")
    initial_deposit: float = Field(alias="initialDeposit", default=100_000.0)
    leverage: float = 1.0
    margin_call_level_pct: float | None = Field(alias="marginCallLevelPct", default=100.0)
    portfolio_name: str | None = Field(alias="portfolioName", default=None)
    portfolio_description: str | None = Field(alias="portfolioDescription", default=None)
    strategy_tag: str | None = Field(alias="strategyTag", default="core")
    settings: AccountSettingsDto | None = None
    commission_preset_id: str | None = Field(alias="commissionPresetId", default=None)
    active_profile_id: str | None = Field(default=None, alias="activeProfileId")
    investor_profile: CreateAccountInvestorProfileDto | None = Field(
        default=None, alias="investorProfile"
    )


class UpdateAccountSettingsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    settings: AccountSettingsDto


class UpdateInvestmentAccountDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    description: str | None = None


class AccountsResponseDto(BaseModel):
    data: list[InvestmentAccountDto]


class AccountResponseDto(BaseModel):
    data: InvestmentAccountDto


class AccountSummaryResponseDto(BaseModel):
    data: AccountSummaryDto


class AccountSummariesResponseDto(BaseModel):
    data: list[AccountSummaryDto]


class LedgerResponseDto(BaseModel):
    data: list[LedgerEntryDto]


class RealizedGainLineDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    sell_transaction_id: str = Field(alias="sellTransactionId")
    executed_at: str = Field(alias="executedAt")
    quantity: float
    sell_price: float = Field(alias="sellPrice")
    proceeds: float
    cost_basis: float = Field(alias="costBasis")
    realized_gain: float = Field(alias="realizedGain")
    method: str
    acquisition_dates: list[str] = Field(alias="acquisitionDates")


class UnrealizedGainLineDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    quantity: float
    avg_cost: float = Field(alias="avgCost")
    market_price: float | None = Field(alias="marketPrice")
    cost_basis: float = Field(alias="costBasis")
    market_value: float | None = Field(alias="marketValue")
    unrealized_gain: float | None = Field(alias="unrealizedGain")


class TaxReportSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    account_id: str = Field(alias="accountId")
    currency: str
    method: str
    jurisdiction: str
    year: int
    period_label: str = Field(alias="periodLabel")
    realized_lines: list[RealizedGainLineDto] = Field(alias="realizedLines")
    total_gains: float = Field(alias="totalGains")
    total_losses: float = Field(alias="totalLosses")
    net_realized_gain: float = Field(alias="netRealizedGain")
    estimated_tax_liability: float | None = Field(alias="estimatedTaxLiability")
    unrealized_lines: list[UnrealizedGainLineDto] = Field(alias="unrealizedLines")
    total_unrealized_gain: float | None = Field(alias="totalUnrealizedGain")
    fees_paid_total: float = Field(alias="feesPaidTotal")
    dividend_withholding_pct: float = Field(alias="dividendWithholdingPct")
    open_position_count: int = Field(alias="openPositionCount")


class TaxReportResponseDto(BaseModel):
    data: TaxReportSummaryDto


class DepositCashDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    amount: float
    note: str | None = None


class WithdrawCashDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    amount: float
    note: str | None = None


class CashMovementResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    account_id: str = Field(alias="accountId")
    portfolio_id: str = Field(alias="portfolioId")
    kind: str
    amount: float
    currency: str
    balance_after: float = Field(alias="balanceAfter")
    executed_at: str = Field(alias="executedAt")
    description: str | None = None


class CashMovementResponseDto(BaseModel):
    data: CashMovementResultDto


class SendDailyOpsDigestDto(BaseModel):
    """R3 — envío manual del digest HTML (Asesor → Diario)."""

    model_config = ConfigDict(populate_by_name=True)

    as_of: str | None = Field(default=None, alias="asOf")
    instrument_ids: list[str] | None = Field(default=None, alias="instrumentIds")
    notify_email: str | None = Field(default=None, alias="notifyEmail")
    notify_digest_enabled: bool = Field(default=True, alias="notifyDigestEnabled")


class DailyOpsDigestNotifyDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    digest_enabled: bool = Field(alias="digestEnabled")
    sent: bool
    skipped_reason: str | None = Field(default=None, alias="skippedReason")
    as_of: str | None = Field(default=None, alias="asOf")


class DailyOpsDigestNotifyResponseDto(BaseModel):
    data: DailyOpsDigestNotifyDto
