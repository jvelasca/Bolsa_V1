"""Use-case: series de indicadores por instrumento."""

from dataclasses import dataclass

from bolsa_analytics.indicators import (
    IndicatorPoint,
    IndicatorSignals,
    build_indicator_series,
    latest_indicator_signals,
)
from bolsa_application.get_ohlcv_bars import GetOhlcvBars
from bolsa_domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True, slots=True)
class IndicatorSeriesResult:
    """Resultado de Indicator Series."""
    data: list[IndicatorPoint]
    signals: IndicatorSignals


class GetInstrumentIndicators:
    """Obtiene Instrument Indicators."""
    def __init__(self, get_ohlcv_bars: GetOhlcvBars) -> None:
        self._get_ohlcv = get_ohlcv_bars

    async def execute(
        self,
        instrument_id: str,
        *,
        limit: int = 365,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> IndicatorSeriesResult | None:
        bars = await self._get_ohlcv.execute(instrument_id, limit=limit, timeframe=timeframe)
        if bars is None:
            return None
        if not bars:
            return IndicatorSeriesResult(data=[], signals=latest_indicator_signals([]))

        points = build_indicator_series(
            [bar.timestamp for bar in bars],
            [bar.close for bar in bars],
        )
        return IndicatorSeriesResult(data=points, signals=latest_indicator_signals(points))
