"""DTOs HTTP de cartera / posiciones."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PortfolioDto(BaseModel):
    id: str
    name: str
    currency: str
    cash: float


class OperationalExitPlanDto(BaseModel):
    """P3 — advisory ExitPlan (no es CTA; ≠ Lab evaluate-exits)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: str
    suggested_action: str = Field(alias="suggestedAction")
    primary_reason: str | None = Field(alias="primaryReason")


class OperationalPositionDto(BaseModel):
    """P1 — snapshot de autoridad post-fill (no es el holding ledger)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: str
    direction: str
    current_stop: float | None = Field(alias="currentStop")
    target1: float | None = None
    target2: float | None = None
    trade_plan_id: str = Field(alias="tradePlanId")
    unrealized_r: float | None = Field(default=None, alias="unrealizedR")
    planned_entry: float | None = Field(default=None, alias="plannedEntry")
    actual_entry: float | None = Field(default=None, alias="actualEntry")
    initial_stop: float | None = Field(default=None, alias="initialStop")
    exit_plan: OperationalExitPlanDto | None = Field(default=None, alias="exitPlan")


class PositionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    name: str
    quantity: float
    avg_cost: float = Field(alias="avgCost")
    last_price: float | None = Field(alias="lastPrice")
    market_value: float | None = Field(alias="marketValue")
    unrealized_pnl: float | None = Field(alias="unrealizedPnl")
    unrealized_pnl_pct: float | None = Field(alias="unrealizedPnlPct")
    sector: str | None = None
    operational: OperationalPositionDto | None = None


class PortfolioSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    portfolio: PortfolioDto
    positions: list[PositionDto]
    total_market_value: float = Field(alias="totalMarketValue")
    total_cost: float = Field(alias="totalCost")
    total_unrealized_pnl: float = Field(alias="totalUnrealizedPnl")
    total_equity: float = Field(alias="totalEquity")


class PortfolioSummaryResponseDto(BaseModel):
    data: PortfolioSummaryDto


class TransactionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    type: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    quantity: float
    price: float
    total: float
    executed_at: str = Field(alias="executedAt")


class TransactionsResponseDto(BaseModel):
    data: list[TransactionDto]


class TradeRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    # R-11 C2: idempotency_key obligatoria, 16–128 chars, sin whitespace exterior
    # (str_strip_whitespace convierte `""`/`"   "` en vacío → min_length → 422).
    instrument_id: str = Field(alias="instrumentId")
    type: Literal["buy", "sell"]
    quantity: float = Field(gt=0, allow_inf_nan=False)
    price: float = Field(gt=0, allow_inf_nan=False)
    idempotency_key: str = Field(
        alias="idempotencyKey", min_length=16, max_length=128
    )


class TradeResponseDto(BaseModel):
    data: dict[str, Any]
