"""Contrato/Puerto de repositorio para instrumentos y su log de sincronización (Protocol)."""
from dataclasses import dataclass
from typing import Any, Protocol

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


@dataclass(frozen=True, slots=True)
class InstrumentTradeContext:
    """Contexto de trading resoluble desde el catálogo (V2.40.1 · AUTO 2.0).

    Es lo que el hot path AUTO necesita para resolver los gates de cartera sin inventar
    nada:

    * ``sector`` — ``instruments.sector`` (``None`` si el catálogo no lo tiene).
    * ``adv_usd`` — ADV notional diario derivado de ``profile_snapshot.fundamentals``
      (``averageVolume × price``); ``None`` si no hay fundamentales.
    * ``observed_at`` — instante (``fetchedAt``) del bloque de fundamentales, que permite
      evaluar la frescura del dato en vez de asumir que sigue vigente.

    Cualquier ausencia se representa con ``None`` explícito: la capa de decisión la
    convierte en ``UNKNOWN``/``STALE`` y veta, nunca en "exento".
    """

    sector: str | None = None
    adv_usd: float | None = None
    observed_at: str | None = None


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

    async def get_fundamentals(self, instrument_id: str) -> dict[str, Any] | None: ...

    async def list_trade_context_by_ids(
        self, instrument_ids: list[str]
    ) -> dict[str, InstrumentTradeContext]: ...
