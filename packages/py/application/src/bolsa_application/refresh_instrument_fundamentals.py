"""P14 — Refresh de fundamentales Yahoo antes de scans con gate fundamental."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bolsa_analytics.signals.fundamental_gate import fundamentals_need_refresh
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)
from bolsa_market.instrument_fundamentals import parse_fundamentals_from_profile_snapshot
from bolsa_market.instrument_profile import build_profile_snapshot
from bolsa_market.yahoo_client import get_yahoo_finance_client


@dataclass(frozen=True, slots=True)
class FundamentalsRefreshResult:
    refreshed_count: int
    skipped_count: int
    failed_count: int


class RefreshInstrumentFundamentals:
    """Descarga quoteSummary Yahoo y persiste profile_snapshot.fundamentals."""

    def __init__(self, instrument_repository: InstrumentRepository) -> None:
        self._instruments = instrument_repository

    async def execute(self, instrument_id: str) -> dict | None:
        if not isinstance(self._instruments, SqlAlchemyInstrumentRepository):
            return await self._instruments.get_fundamentals(instrument_id)

        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None

        try:
            client = get_yahoo_finance_client()
            modules = await client.fetch_quote_summary(instrument.yahoo_symbol)
            if not modules:
                return await self._instruments.get_fundamentals(instrument_id)

            profile = modules.get("summaryProfile") or {}
            sector = profile.get("sector")
            if isinstance(sector, str) and sector.strip():
                await self._instruments.update_sector(instrument_id, sector.strip())

            dividend_history = await client.fetch_dividend_history(instrument.yahoo_symbol)
            snapshot = build_profile_snapshot(
                yahoo_modules=modules,
                dividend_history=dividend_history,
            )
            await self._instruments.update_profile_snapshot(instrument_id, snapshot)
            return parse_fundamentals_from_profile_snapshot(snapshot)
        except Exception:
            return await self._instruments.get_fundamentals(instrument_id)


class RefreshFundamentalsBatch:
    """Refresh concurrente (throttled) para universo de scan."""

    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        *,
        concurrency: int = 4,
    ) -> None:
        self._instruments = instrument_repository
        self._single = RefreshInstrumentFundamentals(instrument_repository)
        self._concurrency = max(1, concurrency)

    async def execute(
        self,
        instrument_ids: list[str],
        *,
        max_age_days: int = 30,
        only_stale: bool = True,
    ) -> FundamentalsRefreshResult:
        unique_ids = list(dict.fromkeys(instrument_ids))
        if not unique_ids:
            return FundamentalsRefreshResult(0, 0, 0)

        if not isinstance(self._instruments, SqlAlchemyInstrumentRepository):
            return FundamentalsRefreshResult(0, len(unique_ids), 0)

        to_refresh: list[str] = []
        skipped = 0
        for instrument_id in unique_ids:
            if only_stale:
                current = await self._instruments.get_fundamentals(instrument_id)
                if not fundamentals_need_refresh(current, max_age_days):
                    skipped += 1
                    continue
            to_refresh.append(instrument_id)

        if not to_refresh:
            return FundamentalsRefreshResult(0, skipped, 0)

        semaphore = asyncio.Semaphore(self._concurrency)
        refreshed = 0
        failed = 0

        async def refresh_one(instrument_id: str) -> None:
            nonlocal refreshed, failed
            async with semaphore:
                before = await self._instruments.get_fundamentals(instrument_id)
                after = await self._single.execute(instrument_id)
                if after is not None and (
                    before is None
                    or after.get("fetchedAt") != before.get("fetchedAt")
                    or not fundamentals_need_refresh(after, max_age_days)
                ):
                    refreshed += 1
                else:
                    failed += 1

        await asyncio.gather(*(refresh_one(instrument_id) for instrument_id in to_refresh))
        return FundamentalsRefreshResult(refreshed, skipped, failed)
