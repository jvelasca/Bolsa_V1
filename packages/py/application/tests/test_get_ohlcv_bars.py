"""Contrato del caso de uso GetOhlcvBars (gráfico MERCADO).

Invariantes que el gráfico asume:
* barras ascendentes y solo las últimas N;
* 1d se sirve de BD sin tocar la red;
* intradía refresca cuando el caché está viejo y sirve el caché si el
  proveedor falla (nunca rompe la petición del gráfico);
* peticiones concurrentes comparten un único fetch (single-flight);
* instrumento inexistente -> None (404 en la ruta).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from bolsa_application.get_ohlcv_bars import GetOhlcvBars
from bolsa_domain.entities.instrument import Instrument
from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_market.yahoo_chart import IntradayOhlcvBar


def _bar(ts: str, close: float = 100.0) -> OhlcvBar:
    return OhlcvBar(
        timestamp=ts,
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=1000,
    )


def _stale_iso(minutes_ago: int) -> str:
    moment = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    return moment.isoformat().replace("+00:00", "Z")


class FakeInstrumentRepository:
    def __init__(self, instrument: Instrument | None) -> None:
        self._instrument = instrument

    async def get_by_id(self, instrument_id: str) -> Instrument | None:
        if self._instrument and self._instrument.id == instrument_id:
            return self._instrument
        return None


class FakeOhlcvRepository:
    def __init__(self, bars: list[OhlcvBar] | None = None) -> None:
        self.bars = list(bars or [])
        self.upserts: list[tuple[TimeFrame, list[OhlcvBar]]] = []
        self.get_bars_calls = 0

    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
        limit: int | None = 365,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[OhlcvBar]:
        self.get_bars_calls += 1
        resolved = self.bars if limit is None else self.bars[-limit:]
        return list(resolved)

    async def count_bars(
        self, instrument_id: str, *, timeframe: TimeFrame = TimeFrame.D1
    ) -> int:
        return len(self.bars)

    async def get_latest_bar_date(
        self, instrument_id: str, *, timeframe: TimeFrame = TimeFrame.D1
    ) -> str | None:
        return self.bars[-1].timestamp if self.bars else None

    async def get_earliest_bar_date(
        self, instrument_id: str, *, timeframe: TimeFrame = TimeFrame.D1
    ) -> str | None:
        return self.bars[0].timestamp if self.bars else None

    async def upsert_daily_bars(self, instrument_id: str, bars: list[OhlcvBar]) -> int:
        return await self.upsert_bars(instrument_id, TimeFrame.D1, bars)

    async def upsert_bars(
        self, instrument_id: str, timeframe: TimeFrame, bars: list[OhlcvBar]
    ) -> int:
        self.upserts.append((timeframe, list(bars)))
        existing = {bar.timestamp: bar for bar in self.bars}
        for bar in bars:
            existing[bar.timestamp] = bar
        self.bars = sorted(existing.values(), key=lambda item: item.timestamp)
        return len(bars)


class FakeYahooProvider:
    def __init__(
        self,
        bars: list[IntradayOhlcvBar] | None = None,
        *,
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self._bars = list(bars or [])
        self._error = error
        self._delay = delay
        self.calls = 0

    async def fetch_interval_bars(
        self,
        yahoo_symbol: str,
        timeframe: TimeFrame,
        *,
        limit: int = 500,
    ) -> list[IntradayOhlcvBar]:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return list(self._bars)


def _instrument() -> Instrument:
    return Instrument(
        id="i1",
        symbol="AAPL",
        yahoo_symbol="AAPL",
        name="Apple",
        exchange="NASDAQ",
        currency="USD",
        country="US",
    )


def _use_case(
    *,
    repo: FakeOhlcvRepository,
    provider: FakeYahooProvider,
    instrument: Instrument | None = None,
) -> GetOhlcvBars:
    return GetOhlcvBars(
        FakeInstrumentRepository(instrument or _instrument()),  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        provider,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_d1_reads_db_and_never_calls_provider() -> None:
    repo = FakeOhlcvRepository([_bar("2026-10-01", 10), _bar("2026-10-02", 11)])
    provider = FakeYahooProvider()
    bars = await _use_case(repo=repo, provider=provider).execute("i1", timeframe=TimeFrame.D1)

    assert [bar.timestamp for bar in bars or []] == ["2026-10-01", "2026-10-02"]
    assert provider.calls == 0
    assert repo.upserts == []


@pytest.mark.asyncio
async def test_unknown_instrument_returns_none() -> None:
    provider = FakeYahooProvider()
    result = await _use_case(
        repo=FakeOhlcvRepository(), provider=provider, instrument=_instrument()
    ).execute("missing", timeframe=TimeFrame.D1)
    assert result is None
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_limit_returns_last_n_bars_ascending() -> None:
    bars = [_bar(f"2026-10-{day:02d}", float(day)) for day in range(1, 11)]
    repo = FakeOhlcvRepository(bars)
    result = await _use_case(repo=repo, provider=FakeYahooProvider()).execute(
        "i1", limit=3, timeframe=TimeFrame.D1
    )
    assert [bar.close for bar in result or []] == [8.0, 9.0, 10.0]


@pytest.mark.asyncio
async def test_intraday_refreshes_stale_cache() -> None:
    cached = _bar(_stale_iso(minutes_ago=120), 100)
    repo = FakeOhlcvRepository([cached])
    provider = FakeYahooProvider(
        [
            IntradayOhlcvBar(
                timestamp=_stale_iso(minutes_ago=30),
                open=101,
                high=103,
                low=100,
                close=102,
                volume=500,
            )
        ]
    )

    bars = await _use_case(repo=repo, provider=provider).execute(
        "i1", timeframe=TimeFrame.H1
    )

    assert provider.calls == 1
    assert len(repo.upserts) == 1
    assert repo.upserts[0][0] == TimeFrame.H1
    assert bars is not None
    assert len(bars) == 2
    assert bars[-1].close == 102


@pytest.mark.asyncio
async def test_intraday_serves_cache_when_provider_fails() -> None:
    cached = _bar(_stale_iso(minutes_ago=600), 99)
    repo = FakeOhlcvRepository([cached])
    provider = FakeYahooProvider(error=RuntimeError("Yahoo 429"))

    bars = await _use_case(repo=repo, provider=provider).execute(
        "i1", timeframe=TimeFrame.H1
    )

    assert provider.calls == 1
    assert [bar.close for bar in bars or []] == [99]
    assert repo.upserts == []


@pytest.mark.asyncio
async def test_fresh_intraday_cache_skips_provider() -> None:
    cached = _bar(_stale_iso(minutes_ago=1), 99)
    repo = FakeOhlcvRepository([cached])
    provider = FakeYahooProvider()

    bars = await _use_case(repo=repo, provider=provider).execute(
        "i1", timeframe=TimeFrame.H1
    )

    assert provider.calls == 0
    assert [bar.close for bar in bars or []] == [99]


@pytest.mark.asyncio
async def test_concurrent_intraday_requests_share_one_fetch() -> None:
    cached = _bar(_stale_iso(minutes_ago=600), 99)
    repo = FakeOhlcvRepository([cached])
    provider = FakeYahooProvider(
        [
            IntradayOhlcvBar(
                timestamp=_stale_iso(minutes_ago=20),
                open=100,
                high=101,
                low=99,
                close=100.5,
                volume=10,
            )
        ],
        delay=0.02,
    )
    use_case = _use_case(repo=repo, provider=provider)

    results = await asyncio.gather(
        use_case.execute("i1", timeframe=TimeFrame.H1),
        use_case.execute("i1", timeframe=TimeFrame.H1),
        use_case.execute("i1", timeframe=TimeFrame.H1),
    )

    assert provider.calls == 1
    assert all(result for result in results)
    assert all((result or [])[-1].close == 100.5 for result in results)


@pytest.mark.asyncio
async def test_intraday_historical_window_does_not_hit_provider() -> None:
    cached = _bar(_stale_iso(minutes_ago=600), 99)
    repo = FakeOhlcvRepository([cached])
    provider = FakeYahooProvider()

    await _use_case(repo=repo, provider=provider).execute(
        "i1", timeframe=TimeFrame.H1, date_to="2026-10-01"
    )

    assert provider.calls == 0
