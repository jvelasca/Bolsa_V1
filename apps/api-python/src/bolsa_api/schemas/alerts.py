"""DTOs HTTP de alertas de precio (API v1).

Aliases camelCase para el cliente web. Persistencia vía use-cases en
``bolsa_application.alerts``.
"""

from pydantic import BaseModel, ConfigDict, Field


class PriceAlertDto(BaseModel):
    """Alerta de precio persistida (activa o disparada)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

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
    """Lista de alertas."""

    data: list[PriceAlertDto]


class PriceAlertResponseDto(BaseModel):
    """Una alerta envuelta en ``data``."""

    data: PriceAlertDto


class CreatePriceAlertRequestDto(BaseModel):
    """Alta de alerta de precio."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    instrument_id: str = Field(alias="instrumentId")
    condition: str
    target_price: float = Field(alias="targetPrice")
    price_source: str = Field(alias="priceSource", default="daily_close")
    note: str | None = None


class EvaluateAlertsResponseDto(BaseModel):
    """Resultado de evaluar alertas activas contra el mercado."""

    data: list[PriceAlertDto]
