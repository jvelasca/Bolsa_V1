from pydantic import BaseModel, ConfigDict, Field


class PriceAlertDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    condition: str
    price_source: str = Field(alias="priceSource")
    target_price: float = Field(alias="targetPrice")
    is_active: bool = Field(alias="isActive")
    triggered_at: str | None = Field(alias="triggeredAt", default=None)
    triggered_price: float | None = Field(alias="triggeredPrice", default=None)
    note: str | None = None
    created_at: str = Field(alias="createdAt")


class PriceAlertsResponseDto(BaseModel):
    data: list[PriceAlertDto]


class PriceAlertResponseDto(BaseModel):
    data: PriceAlertDto


class CreatePriceAlertRequestDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId")
    condition: str
    target_price: float = Field(alias="targetPrice")
    price_source: str = Field(alias="priceSource", default="daily_close")
    note: str | None = None


class EvaluateAlertsResponseDto(BaseModel):
    data: list[PriceAlertDto]
