"""Tabla de decisión de frescura de datos del gráfico MERCADO.

El autosanado del gráfico solo reintenta con ``stale``/``empty``; estos tests
fijan que una serie incompleta nunca quede bloqueada como ``error`` o
``gap_detected`` mientras el detalle del fallo sigue expuesto.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from bolsa_application.get_instrument_data_status import GetInstrumentDataStatus
from bolsa_domain.entities.instrument import Instrument
from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.repositories.instrument_repository import SyncLogDetail
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_market.market_calendar import expected_last_daily_bar


def _bar(day: date, close: float = 100.0) -> OhlcvBar:
    return OhlcvBar(
        timestamp=day.isoformat(),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=1000,
    )


class FakeInstrumentRepository:
    def __init__(self, *, sync: SyncLogDetail | None = None) -> None:
        self.instrument = Instrument(
            id="i1",
            symbol="AAPL",
            yahoo_symbol="AAPL",
            name="Apple",
            exchange="NASDAQ",
            currency="USD",
            country="US",
        )
        self._sync = sync

    async def get_by_id(self, instrument_id: str) -> Instrument | None:
        return self.instrument if instrument_id == "i1" else None

    async def get_last_sync_detail(self, instrument_id: str) -> SyncLogDetail | None:
        return self._sync


class FakeOhlcvRepository:
    def __init__(self, bars: list[OhlcvBar]) -> None:
        self.bars = list(bars)

    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: TimeFrame = TimeFrame.D1,
        limit: int | None = 365,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[OhlcvBar]:
        return self.bars if limit is None else self.bars[-limit:]

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
        return 0

    async def upsert_bars(
        self, instrument_id: str, timeframe: TimeFrame, bars: list[OhlcvBar]
    ) -> int:
        return 0


class NeverCalledDetail:
    async def execute(self, instrument_id: str) -> None:
        return None


def _expected() -> date:
    return expected_last_daily_bar(exchange="NASDAQ", country="US")


def _recent_bars(*, gap_days: int | None = None) -> list[OhlcvBar]:
    """31 barras diarias hasta la última sesión esperada (con hueco opcional)."""
    today = _expected()
    days = [today - timedelta(days=offset) for offset in range(30, -1, -1)]
    if gap_days is not None:
        # Deja un hueco real de ``gap_days`` días entre la zona antigua y la reciente.
        days = [
            day
            for day in days
            if not (gap_days <= (today - day).days <= gap_days * 2)
        ]
    return [_bar(day) for day in days]


def _use_case(
    bars: list[OhlcvBar], *, sync: SyncLogDetail | None = None
) -> GetInstrumentDataStatus:
    return GetInstrumentDataStatus(
        FakeInstrumentRepository(sync=sync),  # type: ignore[arg-type]
        FakeOhlcvRepository(bars),  # type: ignore[arg-type]
        NeverCalledDetail(),  # type: ignore[arg-type]
        None,
    )


@pytest.mark.asyncio
async def test_empty_when_no_bars() -> None:
    status = await _use_case([]).execute("i1")
    assert status is not None
    assert status.freshness_status == "empty"
    assert status.bar_count == 0
    assert status.last_bar_date is None


@pytest.mark.asyncio
async def test_unknown_instrument_returns_none() -> None:
    assert await _use_case([]).execute("missing") is None


@pytest.mark.asyncio
async def test_current_when_last_bar_matches_expected() -> None:
    status = await _use_case(_recent_bars()).execute("i1")
    assert status is not None
    assert status.freshness_status == "current"
    assert status.expected_last_bar_date == _expected().isoformat()


@pytest.mark.asyncio
async def test_stale_when_series_is_old() -> None:
    bars = _recent_bars()[:-3]
    status = await _use_case(bars).execute("i1")
    assert status is not None
    assert status.freshness_status == "stale"


@pytest.mark.asyncio
async def test_stale_when_series_is_old_even_if_last_sync_failed() -> None:
    """Regresión: un fallo de sync no debe congelar el autosanado del gráfico."""
    bars = _recent_bars()[:-3]
    sync = SyncLogDetail(
        status="failed",
        synced_at="2026-11-01T10:00:00+00:00",
        bars_added=0,
        error="Yahoo 429",
    )
    status = await _use_case(bars, sync=sync).execute("i1")
    assert status is not None
    assert status.freshness_status == "stale"
    # El detalle del fallo sigue disponible para la UI.
    assert status.last_sync_status == "failed"
    assert status.last_sync_error == "Yahoo 429"


@pytest.mark.asyncio
async def test_current_series_with_gap_reports_gap_detected() -> None:
    bars = _recent_bars(gap_days=10)
    status = await _use_case(bars).execute("i1")
    assert status is not None
    assert status.gap_count > 0
    assert status.freshness_status == "gap_detected"


@pytest.mark.asyncio
async def test_old_series_with_gap_prefers_stale_over_gap() -> None:
    """Con datos incompletos, el eje de acción (refrescar) manda sobre el aviso."""
    bars = _recent_bars(gap_days=10)[:-3]
    status = await _use_case(bars).execute("i1")
    assert status is not None
    assert status.gap_count > 0
    assert status.freshness_status == "stale"


@pytest.mark.asyncio
async def test_current_series_with_failed_sync_reports_error() -> None:
    sync = SyncLogDetail(
        status="failed",
        synced_at="2026-11-01T10:00:00+00:00",
        bars_added=0,
        error="Yahoo 429",
    )
    status = await _use_case(_recent_bars(), sync=sync).execute("i1")
    assert status is not None
    assert status.freshness_status == "error"


@pytest.mark.asyncio
async def test_intraday_stale_and_current_use_ttl() -> None:
    from datetime import UTC, datetime

    fresh_ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    fresh = [
        OhlcvBar(
            timestamp=fresh_ts,
            open=1,
            high=2,
            low=0.5,
            close=1.5,
            volume=10,
        )
    ]
    status = await _use_case(fresh).execute("i1", timeframe=TimeFrame.H1)
    assert status is not None
    assert status.freshness_status == "current"

    old = [
        OhlcvBar(
            timestamp="2026-01-02T10:00:00Z",
            open=1,
            high=2,
            low=0.5,
            close=1.5,
            volume=10,
        )
    ]
    status_old = await _use_case(old).execute("i1", timeframe=TimeFrame.H1)
    assert status_old is not None
    assert status_old.freshness_status == "stale"
