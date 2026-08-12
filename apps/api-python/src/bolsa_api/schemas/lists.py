"""DTOs HTTP de listas / universos (watchlists)."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from bolsa_api.schemas.instruments import InstrumentWithMetaDto


class InstrumentListSummaryDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    name: str
    source: str
    item_count: int = Field(alias="itemCount")
    updated_at: str = Field(alias="updatedAt")
    kind: str | None = None
    universe_code: str | None = Field(alias="universeCode", default=None)
    last_synced_at: str | None = Field(alias="lastSyncedAt", default=None)
    content_hash: str | None = Field(alias="contentHash", default=None)


class InstrumentListDetailDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    name: str
    source: str
    instrument_ids: list[str] = Field(alias="instrumentIds")
    updated_at: str = Field(alias="updatedAt")
    kind: str | None = None
    universe_code: str | None = Field(alias="universeCode", default=None)
    last_synced_at: str | None = Field(alias="lastSyncedAt", default=None)
    content_hash: str | None = Field(alias="contentHash", default=None)
    membership_changelog: dict[str, Any] | None = Field(alias="membershipChangelog", default=None)


class InstrumentListsResponseDto(BaseModel):
    data: list[InstrumentListSummaryDto]


class InstrumentListMembershipsResponseDto(BaseModel):
    """listId → instrumentIds[] (una respuesta para el sync de membresía del shell)."""

    data: dict[str, list[str]]


class InstrumentListResponseDto(BaseModel):
    data: InstrumentListDetailDto


class ListQuotesResponseDto(BaseModel):
    data: list[InstrumentWithMetaDto]


class CreateListRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    name: str
    instrument_ids: list[str] | None = Field(alias="instrumentIds", default=None)
    source: str | None = None
    kind: str | None = None


class UpdateListRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    name: str | None = None
    instrument_ids: list[str] | None = Field(alias="instrumentIds", default=None)
