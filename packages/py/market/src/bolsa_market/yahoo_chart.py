"""Parseo de payloads Yahoo chart → barras OHLCV (con cuarentena por integridad)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_market.ingest import OhlcvBarIngest
from bolsa_market.ohlcv_quarantine import get_ohlcv_quarantine_stats
from bolsa_market.yahoo_client import get_yahoo_finance_client, normalize_yahoo_error

YAHOO_INTERVAL_BY_TIMEFRAME: dict[TimeFrame, tuple[str, int]] = {
    # Rangos máximos validados contra Yahoo v8 chart (evitar 422).
    TimeFrame.M1: ("1m", 7),
    TimeFrame.M5: ("5m", 30),
    TimeFrame.M15: ("15m", 30),
    TimeFrame.M30: ("30m", 30),
    TimeFrame.H1: ("1h", 365),
    TimeFrame.H4: ("4h", 365),
    TimeFrame.W1: ("1wk", 365 * 5),
    TimeFrame.MO1: ("1mo", 365 * 10),
    TimeFrame.D1: ("1d", 365 * 5),
}


@dataclass(frozen=True, slots=True)
class IntradayOhlcvBar:
    """Vela intradía con timestamp ISO UTC (persistida en ohlcv_bars — ADR-007)."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: float | None = None
    source: str = "yahoo"


def parse_chart_payload(payload: dict[str, Any], yahoo_symbol: str) -> list[OhlcvBarIngest]:
    result = payload.get("chart", {}).get("result")
    if not result:
        raise RuntimeError(f"Yahoo no devolvió barras diarias para {yahoo_symbol}")

    quotes = result[0].get("indicators", {}).get("quote", [{}])[0]
    timestamps = result[0].get("timestamp", [])
    adjclose = result[0].get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])

    bars: list[OhlcvBarIngest] = []
    for i, ts in enumerate(timestamps):
        o = quotes.get("open", [None] * len(timestamps))[i]
        h = quotes.get("high", [None] * len(timestamps))[i]
        lo = quotes.get("low", [None] * len(timestamps))[i]
        c = quotes.get("close", [None] * len(timestamps))[i]
        v = quotes.get("volume", [None] * len(timestamps))[i]
        if o is None or h is None or lo is None or c is None:
            continue
        bar_date = datetime.fromtimestamp(ts, tz=UTC).date()
        adj = adjclose[i] if adjclose and i < len(adjclose) and adjclose[i] is not None else None
        try:
            bars.append(
                OhlcvBarIngest(
                    timestamp=bar_date,
                    open=Decimal(str(o)),
                    high=Decimal(str(h)),
                    low=Decimal(str(lo)),
                    close=Decimal(str(c)),
                    volume=int(v or 0),
                    adj_close=Decimal(str(adj)) if adj is not None else None,
                ),
            )
        except (ValidationError, ValueError, ArithmeticError):
            get_ohlcv_quarantine_stats().record(
                kind="daily",
                reason="ohlc_invalid",
                symbol=yahoo_symbol,
            )
            continue

    if not bars:
        raise RuntimeError(f"Yahoo no devolvió barras diarias para {yahoo_symbol}")
    return bars


def _intraday_ohlc_ok(o: float, h: float, lo: float, c: float, v: int) -> bool:
    if o <= 0 or h <= 0 or lo <= 0 or c <= 0 or v < 0:
        return False
    if h < lo:
        return False
    if h < max(o, c) or lo > min(o, c):
        return False
    return True


def parse_intraday_chart_payload(payload: dict[str, Any], yahoo_symbol: str) -> list[IntradayOhlcvBar]:
    result = payload.get("chart", {}).get("result")
    if not result:
        raise RuntimeError(f"Yahoo no devolvió barras intradía para {yahoo_symbol}")

    quotes = result[0].get("indicators", {}).get("quote", [{}])[0]
    timestamps = result[0].get("timestamp", [])

    bars: list[IntradayOhlcvBar] = []
    for i, ts in enumerate(timestamps):
        o = quotes.get("open", [None] * len(timestamps))[i]
        h = quotes.get("high", [None] * len(timestamps))[i]
        lo = quotes.get("low", [None] * len(timestamps))[i]
        c = quotes.get("close", [None] * len(timestamps))[i]
        v = quotes.get("volume", [None] * len(timestamps))[i]
        if o is None or h is None or lo is None or c is None:
            continue
        fo, fh, flo, fc = float(o), float(h), float(lo), float(c)
        vol = int(v or 0)
        if not _intraday_ohlc_ok(fo, fh, flo, fc, vol):
            get_ohlcv_quarantine_stats().record(
                kind="intraday",
                reason="ohlc_invalid",
                symbol=yahoo_symbol,
            )
            continue
        moment = datetime.fromtimestamp(ts, tz=UTC)
        bars.append(
            IntradayOhlcvBar(
                timestamp=moment.isoformat().replace("+00:00", "Z"),
                open=fo,
                high=fh,
                low=flo,
                close=fc,
                volume=vol,
            ),
        )

    if not bars:
        raise RuntimeError(f"Yahoo no devolvió barras intradía para {yahoo_symbol}")
    return bars


class YahooMarketDataProvider:
    def __init__(self, client=None) -> None:
        self._client = client or get_yahoo_finance_client()

    async def fetch_daily_bars(
        self,
        yahoo_symbol: str,
        from_date,
        to_date,
    ) -> list[OhlcvBarIngest]:
        period1 = int(datetime(from_date.year, from_date.month, from_date.day, tzinfo=UTC).timestamp())
        period2 = int(
            datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59, tzinfo=UTC).timestamp(),
        )

        try:
            payload = await self._client.fetch_chart_payload(
                yahoo_symbol,
                period1=period1,
                period2=period2,
                interval="1d",
            )
            return parse_chart_payload(payload, yahoo_symbol)
        except Exception as exc:
            raise RuntimeError(normalize_yahoo_error(exc)) from exc

    async def fetch_interval_bars(
        self,
        yahoo_symbol: str,
        timeframe: TimeFrame,
        *,
        limit: int = 500,
    ) -> list[IntradayOhlcvBar]:
        if timeframe == TimeFrame.D1:
            raise ValueError("fetch_interval_bars no aplica a 1d; usar fetch_daily_bars")

        yahoo_interval, range_days = YAHOO_INTERVAL_BY_TIMEFRAME[timeframe]
        now = datetime.now(UTC)
        period2 = int(now.timestamp())
        period1 = int((now - timedelta(days=range_days)).timestamp())

        try:
            payload = await self._client.fetch_chart_payload(
                yahoo_symbol,
                period1=period1,
                period2=period2,
                interval=yahoo_interval,
            )
            bars = parse_intraday_chart_payload(payload, yahoo_symbol)
            if limit > 0 and len(bars) > limit:
                bars = bars[-limit:]
            return bars
        except Exception as exc:
            raise RuntimeError(normalize_yahoo_error(exc)) from exc
