"""Sincronizar barras OHLCV diarias desde Yahoo Finance.

Descarga incremental si ya hay barras (overlap 7 días) o histórico completo
years_back si es la primera sync. Registra resultado en data_sync_logs.

Usado por POST /api/instruments/{id}/sync y por ImportInstrument cuando sync=True.
"""
from datetime import date, timedelta
from typing import Literal

from bolsa_application.refresh_instrument_fundamentals import RefreshInstrumentFundamentals
from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.repositories.sync_log_repository import SyncLogRepository
from bolsa_domain.value_objects.market import SyncResult
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)
from bolsa_infrastructure.database.repositories.ohlcv_repository import SqlAlchemyOhlcvRepository
from bolsa_market.ingest import OhlcvBarIngest
from bolsa_market.ohlcv_consolidation import plan_daily_consolidation
from bolsa_market.sanity import run_sanity_checks
from bolsa_market.yahoo_chart import YahooMarketDataProvider
from bolsa_market.yahoo_client import get_yahoo_finance_client, normalize_yahoo_error


def resolve_sync_date_range(
    *,
    to_date: date,
    years_back: int,
    latest_bar_date: str | None,
    overlap_days: int = 7,
) -> tuple[date, date, bool]:
    """Devuelve (from_date, to_date, incremental)."""
    if latest_bar_date:
        latest = date.fromisoformat(latest_bar_date[:10])
        from_date = latest - timedelta(days=overlap_days)
        from_date = min(from_date, to_date)
        return from_date, to_date, True

    from_date = date(to_date.year - years_back, to_date.month, to_date.day)
    return from_date, to_date, False


class SyncInstrumentDailyBars:
    """Sincroniza Instrument Daily Bars."""
    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        ohlcv_repository: OhlcvRepository,
        sync_log_repository: SyncLogRepository,
        yahoo: YahooMarketDataProvider | None = None,
    ) -> None:
        self._instruments = instrument_repository
        self._ohlcv = ohlcv_repository
        self._sync_logs = sync_log_repository
        self._yahoo = yahoo or YahooMarketDataProvider()

    async def execute(
        self,
        instrument_id: str,
        *,
        years_back: int = 5,
    ) -> SyncResult | None:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None

        to_date = date.today()
        latest_bar = await self._ohlcv.get_latest_bar_date(instrument_id)
        from_date, _, incremental = resolve_sync_date_range(
            to_date=to_date,
            years_back=years_back,
            latest_bar_date=latest_bar,
        )

        try:
            raw_bars = await self._yahoo.fetch_daily_bars(instrument.yahoo_symbol, from_date, to_date)
            if not raw_bars:
                await self._sync_logs.create_log(
                    instrument_id,
                    provider="yahoo",
                    status="partial",
                    bars_added=0,
                    error="No bars returned from Yahoo",
                )
                return SyncResult(bars_added=0, status="partial", error="No bars returned from Yahoo")

            validated = [OhlcvBarIngest.model_validate(bar.model_dump()) for bar in raw_bars]
            sanity = run_sanity_checks(validated)
            if not sanity.valid:
                message = "; ".join(sanity.errors)
                await self._sync_logs.create_log(
                    instrument_id,
                    provider="yahoo",
                    status="failed",
                    bars_added=0,
                    error=f"Sanity check: {message}",
                )
                return SyncResult(bars_added=0, status="failed", error=message)

            domain_bars = [
                OhlcvBar(
                    timestamp=bar.timestamp.isoformat(),
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=bar.volume,
                    adj_close=float(bar.adj_close) if bar.adj_close is not None else None,
                    source="yahoo",
                )
                for bar in validated
            ]

            bars_to_write = domain_bars
            inserted = len(domain_bars)
            updated = 0
            skipped = 0
            notes: tuple[str, ...] = ()

            if isinstance(self._ohlcv, SqlAlchemyOhlcvRepository):
                existing = await self._ohlcv.get_daily_bars_by_dates(
                    instrument_id,
                    [bar.timestamp for bar in domain_bars],
                )
                plan = plan_daily_consolidation(existing, domain_bars)
                bars_to_write = list(plan.to_write)
                inserted = plan.inserted
                updated = plan.updated
                skipped = plan.skipped
                notes = plan.skip_reasons

            bars_added = await self._ohlcv.upsert_daily_bars(instrument_id, bars_to_write)
            sync_status: Literal["success", "partial", "failed"] = "success"
            if skipped > 0 and bars_added == 0:
                sync_status = "partial"
            await self._sync_logs.create_log(
                instrument_id,
                provider="yahoo",
                status=sync_status,
                bars_added=bars_added,
                error="; ".join(notes) if notes else None,
            )
            if incremental and bars_added == 0 and skipped == 0:
                await self._refresh_yahoo_metadata(instrument_id, instrument.yahoo_symbol)
                return SyncResult(
                    bars_added=0,
                    status="success",
                    bars_inserted=0,
                    bars_updated=0,
                    bars_skipped=skipped,
                    consolidation_notes=notes,
                )
            await self._refresh_yahoo_metadata(instrument_id, instrument.yahoo_symbol)
            return SyncResult(
                bars_added=bars_added,
                status=sync_status,
                bars_inserted=inserted,
                bars_updated=updated,
                bars_skipped=skipped,
                consolidation_notes=notes,
            )
        except Exception as exc:
            message = normalize_yahoo_error(exc)
            await self._sync_logs.create_log(
                instrument_id,
                provider="yahoo",
                status="failed",
                bars_added=0,
                error=message,
            )
            return SyncResult(bars_added=0, status="failed", error=message)

    async def _refresh_yahoo_metadata(self, instrument_id: str, yahoo_symbol: str) -> None:
        if isinstance(self._instruments, SqlAlchemyInstrumentRepository):
            await self._ensure_isin(instrument_id, yahoo_symbol)
        await RefreshInstrumentFundamentals(self._instruments).execute(instrument_id)

    async def _ensure_isin(self, instrument_id: str, yahoo_symbol: str) -> None:
        if not isinstance(self._instruments, SqlAlchemyInstrumentRepository):
            return
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None or instrument.isin:
            return
        try:
            isin = await get_yahoo_finance_client().fetch_isin(yahoo_symbol)
        except Exception:
            return
        if isin:
            await self._instruments.update_isin(instrument_id, isin)
