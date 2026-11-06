"""Dobles de catálogo que SÍ miden, para los caminos de apertura (P2 .183).

Desde que el Policy Gate trata una regla activa sin dato como ``FAILED``
(``<Regla>_unmeasured``), un doble que solo sabe devolver un sector ya no representa un
"catálogo sano": representa un catálogo que no mide liquidez. Estos dobles existen para
que los tests de caminos permitidos declaren explícitamente que el dato ESTÁ.

``MeasuredInstruments`` es autónomo; ``MeasuredInstrumentsMixin`` añade solo las dos
lecturas nuevas a un doble que ya implementa ``get_by_id`` (el caso de la mayoría de los
tests de ``ExecuteTrade`` y sus satélites).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_MARKET_CAP_USD = 3e12
DEFAULT_ADV_USD = 1e9
DEFAULT_SECTOR = "technology"


@dataclass(frozen=True, slots=True)
class FakeTradeContext:
    sector: str | None
    adv_usd: float | None
    observed_at: str | None = None


class MeasuredInstrumentsMixin:
    """Añade ``list_trade_context_by_ids`` y ``get_fundamentals`` a un doble existente."""

    market_cap_usd: float | None = DEFAULT_MARKET_CAP_USD
    adv_usd: float | None = DEFAULT_ADV_USD
    sector: str | None = DEFAULT_SECTOR

    async def list_trade_context_by_ids(self, ids: list[str]) -> dict[str, FakeTradeContext]:
        return {i: FakeTradeContext(sector=self.sector, adv_usd=self.adv_usd) for i in ids}

    async def get_fundamentals(self, instrument_id: str) -> dict[str, Any] | None:
        if self.market_cap_usd is None:
            return None
        return {"marketCap": self.market_cap_usd}


class MeasuredInstruments(MeasuredInstrumentsMixin):
    """Doble completo: sector por ``get_by_id`` + métricas de política."""

    def __init__(
        self,
        *,
        market_cap_usd: float | None = DEFAULT_MARKET_CAP_USD,
        adv_usd: float | None = DEFAULT_ADV_USD,
        sector: str | None = DEFAULT_SECTOR,
    ) -> None:
        self.market_cap_usd = market_cap_usd
        self.adv_usd = adv_usd
        self.sector = sector

    async def get_by_id(self, instrument_id: str) -> Any:
        return type("Instrument", (), {"id": instrument_id, "sector": self.sector})()


__all__ = [
    "FakeTradeContext",
    "MeasuredInstruments",
    "MeasuredInstrumentsMixin",
]
