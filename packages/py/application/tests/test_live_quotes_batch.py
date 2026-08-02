"""Live quotes batch must not fan out detail/500-bar loads."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bolsa_domain.repositories.instrument_repository import InstrumentWithMeta, SyncLogSnapshot
from bolsa_market.providers import XtbBridgeQuote

from bolsa_application.market import GetInstrumentLiveQuotes


def _meta(instrument_id: str, *, close: float = 10.0) -> InstrumentWithMeta:
    return InstrumentWithMeta(
        id=instrument_id,
        symbol=instrument_id.upper(),
        yahoo_symbol=f"{instrument_id.upper()}.MC",
        name=instrument_id,
        exchange="BME",
        country="ES",
        currency="EUR",
        sector=None,
        isin=None,
        is_active=True,
        bar_count=100,
        last_sync=SyncLogSnapshot(status="ok", synced_at="2026-01-01T00:00:00+00:00", error=None),
        last_close=close,
        change_pct=1.0,
        last_bar_date="2026-01-01",
        freshness_status="current",
        expected_last_bar_date="2026-01-01",
    )


@dataclass
class _FakeRepo:
    calls: list[list[str]]

    async def get_quotes_by_ids(self, instrument_ids: list[str]) -> list[InstrumentWithMeta]:
        self.calls.append(list(instrument_ids))
        return [_meta("a", close=10.0), _meta("b", close=20.0)]

    async def get_by_id(self, instrument_id: str):
        raise AssertionError("batch path must not call get_by_id")

    async def get_with_meta_by_id(self, instrument_id: str):
        raise AssertionError("batch path must not call get_with_meta_by_id")


@dataclass
class _FakeBridge:
    health_calls: int = 0
    quote_calls: list[str] | None = None

    def __post_init__(self) -> None:
        self.quote_calls = []

    async def check_health(self):
        self.health_calls += 1
        return type("H", (), {"status": "ok", "mode": "mock", "message": "ok"})()

    async def fetch_quotes(self, symbols, *, references=None, concurrency=8):
        assert self.quote_calls is not None
        self.quote_calls.extend(symbols)
        return {
            symbol: XtbBridgeQuote(
                symbol=symbol,
                bid=1.0,
                ask=1.1,
                last=1.05,
                timestamp="2026-01-01T12:00:00Z",
            )
            for symbol in symbols
        }


def test_live_quotes_batch_uses_meta_once_and_one_health(monkeypatch) -> None:
    repo = _FakeRepo(calls=[])
    bridge = _FakeBridge()

    monkeypatch.setattr(
        "bolsa_application.market.XtbBridgeClient",
        lambda _url: bridge,
    )

    use_case = GetInstrumentLiveQuotes(repo, "http://localhost:3002")  # type: ignore[arg-type]
    quotes = asyncio.run(use_case.execute(["a", "b", "a"]))

    assert len(repo.calls) == 1
    assert bridge.health_calls == 1
    assert len(quotes) == 2
    assert quotes[0].reference is not None
    assert quotes[0].reference.price == 10.0
    assert quotes[0].xtb is not None
    assert quotes[0].xtb_available is True
    assert quotes[0].spread_pct is not None
