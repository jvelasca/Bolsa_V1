from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OhlcvBarIngest(BaseModel):
    """Vela OHLCV validada en ingesta — strict, inmutable."""

    model_config = ConfigDict(strict=True, frozen=True)

    timestamp: date
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    adj_close: Decimal | None = Field(default=None, gt=0)

    @field_validator("timestamp")
    @classmethod
    def timestamp_not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("timestamp no puede ser futuro")
        return value

    @model_validator(mode="after")
    def ohlc_consistency(self) -> OhlcvBarIngest:
        if self.high < self.low:
            raise ValueError("high debe ser >= low")
        if self.high < max(self.open, self.close):
            raise ValueError("high debe cubrir open y close")
        if self.low > min(self.open, self.close):
            raise ValueError("low debe cubrir open y close")
        return self


class OhlcvBatchIngest(BaseModel):
    """Lote de velas para sync — validación por barra + metadatos."""

    model_config = ConfigDict(strict=True)

    symbol: str = Field(min_length=1, max_length=20)
    source: str = Field(pattern=r"^(yahoo|xtb)$")
    bars: list[OhlcvBarIngest] = Field(min_length=1)

    @model_validator(mode="after")
    def bars_chronological(self) -> OhlcvBatchIngest:
        timestamps = [bar.timestamp for bar in self.bars]
        if timestamps != sorted(timestamps):
            raise ValueError("las barras deben estar ordenadas por timestamp ascendente")
        return self
