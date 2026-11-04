"""Use-case: barras OHLCV."""

import asyncio

from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.ohlcv_time import is_cache_stale
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_market.yahoo_chart import YahooMarketDataProvider

# Single-flight por (instrumento, timeframe): varias peticiones concurrentes
# (gráfico, panel de alertas, indicadores) no deben lanzar fetch duplicados
# contra Yahoo para el mismo dato.
_REFRESH_LOCKS: dict[
    tuple[str, TimeFrame], tuple[asyncio.AbstractEventLoop, asyncio.Lock]
] = {}


def _refresh_lock(instrument_id: str, timeframe: TimeFrame) -> asyncio.Lock:
    key = (instrument_id, timeframe)
    loop = asyncio.get_running_loop()
    entry = _REFRESH_LOCKS.get(key)
    # Un Lock queda ligado al loop en el que se usa; los tests crean loops
    # nuevos por caso, así que se recrea si cambia el loop en curso.
    if entry is None or entry[0] is not loop:
        entry = (loop, asyncio.Lock())
        _REFRESH_LOCKS[key] = entry
    return entry[1]


class GetOhlcvBars:
    """Obtiene Ohlcv Bars."""
    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        ohlcv_repository: OhlcvRepository,
        yahoo: YahooMarketDataProvider | None = None,
    ) -> None:
        self._instruments = instrument_repository
        self._ohlcv = ohlcv_repository
        self._yahoo = yahoo or YahooMarketDataProvider()

    async def _fetch_and_cache(
        self,
        instrument_id: str,
        yahoo_symbol: str,
        timeframe: TimeFrame,
        *,
        limit: int,
    ) -> list[OhlcvBar]:
        try:
            if timeframe == TimeFrame.D1:
                return []

            raw_bars = await self._yahoo.fetch_interval_bars(
                yahoo_symbol,
                timeframe,
                limit=limit,
            )
        except RuntimeError:
            return []

        if not raw_bars:
            return []

        domain_bars = [
            OhlcvBar(
                timestamp=bar.timestamp,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                adj_close=bar.adj_close,
                source="yahoo",
            )
            for bar in raw_bars
        ]
        await self._ohlcv.upsert_bars(instrument_id, timeframe, domain_bars)
        return await self._ohlcv.get_bars(instrument_id, limit=limit, timeframe=timeframe)

    async def execute(
        self,
        instrument_id: str,
        *,
        limit: int = 365,
        timeframe: TimeFrame = TimeFrame.D1,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[OhlcvBar] | None:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None

        if timeframe == TimeFrame.D1:
            return await self._ohlcv.get_bars(
                instrument_id,
                limit=limit,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
            )

        # Intraday: as-of historical cut not supported via Yahoo interval fetch yet.
        # When date_to is set, only return cached bars ≤ date_to (no live refresh).
        if date_to or date_from:
            return await self._ohlcv.get_bars(
                instrument_id,
                limit=limit,
                timeframe=timeframe,
                date_from=date_from,
                date_to=date_to,
            )

        cached = await self._ohlcv.get_bars(instrument_id, limit=limit, timeframe=timeframe)
        latest = cached[-1].timestamp if cached else None
        if cached and not is_cache_stale(timeframe, latest):
            return cached

        async with _refresh_lock(instrument_id, timeframe):
            # Otra petición pudo refrescar mientras esperábamos el lock.
            cached = await self._ohlcv.get_bars(
                instrument_id, limit=limit, timeframe=timeframe
            )
            latest = cached[-1].timestamp if cached else None
            if cached and not is_cache_stale(timeframe, latest):
                return cached

            refreshed = await self._fetch_and_cache(
                instrument_id,
                instrument.yahoo_symbol,
                timeframe,
                limit=limit,
            )
            if refreshed:
                return refreshed
            return cached
