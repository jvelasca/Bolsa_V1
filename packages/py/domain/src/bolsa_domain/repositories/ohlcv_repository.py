"""Contrato/Puerto de repositorio para barras OHLCV (Protocol)."""
from typing import Protocol

from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.value_objects.timeframe import TimeFrame


class OhlcvRepository(Protocol):
    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
        limit: int | None = 365,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[OhlcvBar]: ...

    async def count_bars(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> int: ...

    async def get_latest_bar_date(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> str | None: ...

    async def get_earliest_bar_date(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> str | None: ...

    async def upsert_daily_bars(self, instrument_id: str, bars: list[OhlcvBar]) -> int: ...

    async def upsert_bars(
        self,
        instrument_id: str,
        timeframe: TimeFrame,
        bars: list[OhlcvBar],
    ) -> int: ...
