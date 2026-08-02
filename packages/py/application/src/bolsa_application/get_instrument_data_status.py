"""Estado de frescura y calidad de datos OHLCV de un instrumento."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from bolsa_domain.ohlcv_time import is_cache_stale
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_market.ingest import OhlcvBarIngest
from bolsa_market.market_calendar import expected_last_daily_bar
from bolsa_market.providers import XtbBridgeClient
from bolsa_market.sanity import run_sanity_checks
from bolsa_market.xtb_symbols import to_xtb_symbol

from bolsa_application.get_instrument_detail import GetInstrumentDetail

FreshnessStatus = Literal["current", "stale", "empty", "error", "gap_detected", "syncing"]


@dataclass(frozen=True, slots=True)
class InstrumentDataStatus:
    timeframe: str
    last_bar_date: str | None
    expected_last_bar_date: str
    freshness_status: FreshnessStatus
    bar_count: int
    last_sync_status: str | None
    last_sync_at: str | None
    last_sync_error: str | None
    sanity_warnings: tuple[str, ...]
    gap_count: int
    xtb_vs_close_deviation_pct: float | None
    last_xtb_quote_at: str | None


class GetInstrumentDataStatus:
    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        ohlcv_repository: OhlcvRepository,
        detail_use_case: GetInstrumentDetail,
        xtb_bridge_url: str | None,
    ) -> None:
        self._instruments = instrument_repository
        self._ohlcv = ohlcv_repository
        self._detail = detail_use_case
        self._xtb_bridge_url = xtb_bridge_url

    async def execute(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
    ) -> InstrumentDataStatus | None:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None

        bar_count = await self._ohlcv.count_bars(instrument_id, timeframe=timeframe)
        last_bar_date = await self._ohlcv.get_latest_bar_date(instrument_id, timeframe=timeframe)
        expected = expected_last_daily_bar(
            exchange=instrument.exchange,
            country=instrument.country,
        )
        expected_iso = expected.isoformat()

        last_sync = await self._instruments.get_last_sync_detail(instrument_id)
        last_sync_status = last_sync.status if last_sync else None
        last_sync_at = last_sync.synced_at if last_sync else None
        last_sync_error = last_sync.error if last_sync else None

        sanity_warnings: tuple[str, ...] = ()
        gap_count = 0
        if bar_count > 0 and timeframe == TimeFrame.D1:
            bars = await self._ohlcv.get_bars(instrument_id, timeframe=timeframe, limit=120)
            ingest = [
                OhlcvBarIngest(
                    timestamp=date.fromisoformat(bar.timestamp[:10]),
                    open=Decimal(str(bar.open)),
                    high=Decimal(str(bar.high)),
                    low=Decimal(str(bar.low)),
                    close=Decimal(str(bar.close)),
                    volume=bar.volume,
                    adj_close=Decimal(str(bar.adj_close)) if bar.adj_close is not None else None,
                )
                for bar in bars
            ]
            report = run_sanity_checks(ingest)
            sanity_warnings = report.warnings
            gap_count = sum(1 for w in sanity_warnings if w.startswith("gap de"))

        xtb_vs_close_deviation_pct: float | None = None
        last_xtb_quote_at: str | None = None
        detail = await self._detail.execute(instrument_id)
        if (
            self._xtb_bridge_url
            and self._xtb_bridge_url.strip()
            and detail
            and detail.price_summary
            and detail.price_summary.last_close != 0
        ):
            client = XtbBridgeClient(self._xtb_bridge_url.strip())
            try:
                health = await client.check_health()
                if health.status == "ok":
                    quote = await client.fetch_quote(
                        to_xtb_symbol(instrument.symbol, yahoo_symbol=instrument.yahoo_symbol),
                    )
                    last_xtb_quote_at = quote.timestamp
                    xtb_vs_close_deviation_pct = (
                        (quote.last - detail.price_summary.last_close)
                        / detail.price_summary.last_close
                    ) * 100
            except Exception:
                pass

        freshness_status = self._resolve_freshness(
            timeframe=timeframe,
            bar_count=bar_count,
            last_bar_date=last_bar_date,
            expected_iso=expected_iso,
            gap_count=gap_count,
            last_sync_status=last_sync_status,
        )

        return InstrumentDataStatus(
            timeframe=timeframe.value,
            last_bar_date=last_bar_date,
            expected_last_bar_date=expected_iso,
            freshness_status=freshness_status,
            bar_count=bar_count,
            last_sync_status=last_sync_status,
            last_sync_at=last_sync_at,
            last_sync_error=last_sync_error,
            sanity_warnings=sanity_warnings,
            gap_count=gap_count,
            xtb_vs_close_deviation_pct=xtb_vs_close_deviation_pct,
            last_xtb_quote_at=last_xtb_quote_at,
        )

    @staticmethod
    def _resolve_freshness(
        *,
        timeframe: TimeFrame,
        bar_count: int,
        last_bar_date: str | None,
        expected_iso: str,
        gap_count: int,
        last_sync_status: str | None,
    ) -> FreshnessStatus:
        if bar_count == 0:
            return "empty"

        if timeframe != TimeFrame.D1:
            if is_cache_stale(timeframe, last_bar_date):
                return "stale"
            return "current"

        if gap_count > 0:
            return "gap_detected"
        last = last_bar_date[:10] if last_bar_date else None
        if last is None:
            return "empty"
        if last < expected_iso:
            if last_sync_status == "failed":
                return "error"
            return "stale"
        if last_sync_status == "failed":
            return "error"
        return "current"
