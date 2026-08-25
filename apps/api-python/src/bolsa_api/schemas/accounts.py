"""DTOs HTTP de cuentas de trading/DEMO."""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CommissionProfileDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    preset_id: str = Field(alias="presetId")
    label: str
    stock_commission_pct: float = Field(alias="stockCommissionPct", ge=0, allow_inf_nan=False)
    stock_commission_min: float = Field(
        alias="stockCommissionMin", ge=0, allow_inf_nan=False
    )
    stock_commission_max: float | None = Field(
        alias="stockCommissionMax", ge=0, allow_inf_nan=False
    )
    vat_on_commission_pct: float = Field(
        alias="vatOnCommissionPct", ge=0, allow_inf_nan=False
    )
    fx_conversion_pct: float = Field(alias="fxConversionPct", ge=0, allow_inf_nan=False)
    custody_annual_pct: float | None = Field(
        alias="custodyAnnualPct", ge=0, allow_inf_nan=False
    )

    @model_validator(mode="after")
    def max_commission_cannot_be_below_min(self) -> Self:
        """Inviolable: un tope máximo menor que el mínimo sería un contrato absurdo."""
        if (
            self.stock_commission_max is not None
            and self.stock_commission_max < self.stock_commission_min
        ):
            raise ValueError(
                "stockCommissionMax must be >= stockCommissionMin "
                f"({self.stock_commission_max} < {self.stock_commission_min})"
            )
        return self


class TaxProfileDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    jurisdiction: str
    cost_basis_method: str = Field(alias="costBasisMethod")
    stamp_duty_buy_pct: float = Field(alias="stampDutyBuyPct", ge=0, allow_inf_nan=False)
    dividend_withholding_pct: float = Field(
        alias="dividendWithholdingPct", ge=0, allow_inf_nan=False
    )
    capital_gains_tax_pct: float | None = Field(
        alias="capitalGainsTaxPct", ge=0, allow_inf_nan=False
    )
    fiscal_year_start_month: int = Field(alias="fiscalYearStartMonth")

    @model_validator(mode="after")
    def fiscal_year_start_month_in_range(self) -> Self:
        """Inviolable: el mes de inicio del año fiscal debe ser un mes válido [1,12]."""
        if not 1 <= self.fiscal_year_start_month <= 12:
            raise ValueError(
                "fiscalYearStartMonth must be in [1,12] "
                f"(got {self.fiscal_year_start_month})"
            )
        return self


class AccountSettingsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    commission: CommissionProfileDto
    tax: TaxProfileDto
    notes: str | None = None


class InvestmentAccountDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    lab_evidence: dict[str, Any] | None = Field(default=None, alias="labEvidence")


class InvestmentPortfolioDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    account_id: str = Field(alias="accountId")
    legacy_portfolio_id: str | None = Field(alias="legacyPortfolioId")
    name: str
    description: str | None
    strategy_tag: str | None = Field(alias="strategyTag")
    sort_order: int = Field(alias="sortOrder")
    is_default: bool = Field(alias="isDefault")


class AccountSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    initial_deposit: float = Field(
        alias="initialDeposit", default=100_000.0, ge=0, allow_inf_nan=False
    )
    leverage: float = Field(1.0, gt=0, allow_inf_nan=False)
    margin_call_level_pct: float | None = Field(
        alias="marginCallLevelPct", default=100.0, ge=0, allow_inf_nan=False
    )
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
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    quantity: float
    avg_cost: float = Field(alias="avgCost")
    market_price: float | None = Field(alias="marketPrice")
    cost_basis: float = Field(alias="costBasis")
    market_value: float | None = Field(alias="marketValue")
    unrealized_gain: float | None = Field(alias="unrealizedGain")


class TaxReportSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    # P2.7: dinero en movimiento (alimenta deposit → ledger). Estricto: >0 y sin
    # NaN/Inf (mismo contrato que TradeRequestDto desde F1/M4).
    amount: float = Field(gt=0, allow_inf_nan=False)
    note: str | None = None
    # A-2 (R-7): idempotencia de movimientos. Obligatoria (R-10 F1): sin clave no
    # se permite el depósito, para que un retry HTTP no cree una 2ª operación.
    # R-11 C2: validación estricta end-to-end — longitud 16–128 y sin whitespace
    # exterior (str_strip_whitespace convierte `""`/`"   "` en vacío → min_length→422).
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=16, max_length=128
    )


class WithdrawCashDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    amount: float = Field(gt=0, allow_inf_nan=False)
    note: str | None = None
    # R-11 C2: idempotency_key obligatoria, 16–128 chars, sin whitespace (ver DepositCashDto).
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=16, max_length=128
    )


class CashMovementResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    """R3/R4 — envío manual del digest HTML (+ PDF opcional)."""

    model_config = ConfigDict(populate_by_name=True)

    as_of: str | None = Field(default=None, alias="asOf")
    instrument_ids: list[str] | None = Field(default=None, alias="instrumentIds")
    notify_email: str | None = Field(default=None, alias="notifyEmail")
    notify_digest_enabled: bool = Field(default=True, alias="notifyDigestEnabled")
    attach_pdf: bool | None = Field(default=None, alias="attachPdf")


class DailyOpsDigestNotifyDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    digest_enabled: bool = Field(alias="digestEnabled")
    sent: bool
    skipped_reason: str | None = Field(default=None, alias="skippedReason")
    as_of: str | None = Field(default=None, alias="asOf")
    pdf_attached: bool = Field(default=False, alias="pdfAttached")


class DailyOpsDigestNotifyResponseDto(BaseModel):
    data: DailyOpsDigestNotifyDto


class DecisionBoardBucketCountsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    pending_confirm: int = Field(alias="pendingConfirm")
    vetoed: int
    deferred: int
    auto_waiting: int = Field(alias="autoWaiting")
    total: int


class DecisionSessionViewDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    session_id: str = Field(alias="sessionId")
    kind: str
    status: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str | None = None
    decision_id: str | None = Field(default=None, alias="decisionId")
    created_at: str = Field(alias="createdAt")
    gate: str
    # Ciclo 4.9 — echo thin; dict libre (sin contract:gen). Ausente → Hoy heurística.
    trade_plan: dict[str, Any] | None = Field(default=None, alias="tradePlan")
    wyckoff_spring_anchor: dict[str, Any] | None = Field(
        default=None, alias="wyckoffSpringAnchor"
    )


class SemiF3ViewDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str | None = Field(default=None, alias="instrumentId")
    symbol: str | None = None
    status: str = "pending_confirm"
    extra: dict[str, Any] = Field(default_factory=dict)


class DecisionBoardDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    account_id: str = Field(alias="accountId")
    generated_at: str = Field(alias="generatedAt")
    buckets: DecisionBoardBucketCountsDto
    semi_f3_queue: list[SemiF3ViewDto] = Field(alias="semiF3Queue", default_factory=list)
    decision_sessions: list[DecisionSessionViewDto] = Field(
        alias="decisionSessions", default_factory=list
    )
    equity: float | None = None
    free_margin: float | None = Field(default=None, alias="freeMargin")


class DecisionBoardResponseDto(BaseModel):
    data: DecisionBoardDto


class DecisionJournalEntryDto(BaseModel):
    """Wire alineado con ``DecisionJournalEntryV1`` (@bolsa/shared)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    artifact_type: str = Field(default="ART-DECISION-JOURNAL-ENTRY", alias="artifactType")
    schema_version: str = Field(default="1.0.0", alias="schemaVersion")
    entry_id: str = Field(alias="entryId")
    decision_id: str = Field(alias="decisionId")
    session_id: str | None = Field(default=None, alias="sessionId")
    account_id: str | None = Field(default=None, alias="accountId")
    instrument_id: str | None = Field(default=None, alias="instrumentId")
    event_type: str = Field(alias="eventType")
    actor: str
    payload: dict[str, Any] | None = None
    created_at: str = Field(alias="createdAt")


class DecisionJournalListDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    account_id: str = Field(alias="accountId")
    entries: list[DecisionJournalEntryDto]
    total: int
    limit: int
    offset: int


class DecisionJournalListResponseDto(BaseModel):
    data: DecisionJournalListDto
