"""DTOs — demos cerradas / purga en Configuración → BD."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClosedSimulatedAccountDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    name: str
    currency: str
    updated_at: str = Field(alias="updatedAt")
    ledger_entry_count: int = Field(alias="ledgerEntryCount")
    portfolio_count: int = Field(alias="portfolioCount")
    position_count: int = Field(alias="positionCount")
    transaction_count: int = Field(alias="transactionCount")
    pending_order_count: int = Field(alias="pendingOrderCount")


class ClosedSimulatedAccountsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    accounts: list[ClosedSimulatedAccountDto]
    total_ledger_entries: int = Field(alias="totalLedgerEntries")


class ClosedSimulatedAccountsResponseDto(BaseModel):
    data: ClosedSimulatedAccountsDto


class PurgeClosedAccountsRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    limit: int = Field(default=50, ge=1, le=200)


class PurgeClosedAccountSkippedDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    account_id: str = Field(alias="accountId")
    name: str
    reasons: list[str]


class PurgeClosedAccountsResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    purged_ids: list[str] = Field(alias="purgedIds")
    skipped: list[PurgeClosedAccountSkippedDto]
    scanned: int


class PurgeClosedAccountsResponseDto(BaseModel):
    data: PurgeClosedAccountsResultDto
