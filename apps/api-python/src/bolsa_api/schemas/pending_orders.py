from pydantic import BaseModel, ConfigDict, Field


class PendingOrderDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    id: str
    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    side: str
    order_type: str = Field(alias="orderType")
    quantity: float
    limit_price: float = Field(alias="limitPrice")
    expiry_at: str | None = Field(alias="expiryAt")
    created_at: str = Field(alias="createdAt")


class PendingOrdersResponseDto(BaseModel):
    data: list[PendingOrderDto]


class CreatePendingOrderDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    instrument_id: str = Field(alias="instrumentId")
    symbol: str
    side: str
    order_type: str = Field(alias="orderType", default="stop_limit")
    quantity: float = Field(gt=0)
    limit_price: float = Field(alias="limitPrice", gt=0)
    expiry_at: str | None = Field(alias="expiryAt", default=None)
