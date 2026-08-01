from dataclasses import dataclass
from typing import Protocol

from bolsa_domain.entities.instrument import Instrument


@dataclass(frozen=True, slots=True)
class SyncLogSnapshot:
    status: str
    synced_at: str
    error: str | None


@dataclass(frozen=True, slots=True)
class SyncLogDetail:
    status: str
    synced_at: str
    bars_added: int
    error: str | None


@dataclass(frozen=True, slots=True)
class InstrumentWithMeta:
    id: str
    symbol: str
    yahoo_symbol: str
    name: str
    exchange: str
    country: str
    currency: str
    sector: str | None
    isin: str | None
    is_active: bool
    bar_count: int
    last_sync: SyncLogSnapshot | None
    last_close: float | None
    change_pct: float | None
    last_bar_date: str | None = None
    freshness_status: str = "empty"
    expected_last_bar_date: str | None = None


class InstrumentRepository(Protocol):
    async def list_with_meta(
        self,
        *,
        exchange: str | None = None,
        active_only: bool = True,
    ) -> list[InstrumentWithMeta]: ...

    async def get_quotes_by_ids(self, instrument_ids: list[str]) -> list[InstrumentWithMeta]: ...

    async def get_by_id(self, instrument_id: str) -> Instrument | None: ...

    async def get_last_sync_detail(self, instrument_id: str) -> SyncLogDetail | None: ...

    async def get_fundamentals(self, instrument_id: str) -> dict | None: ...
