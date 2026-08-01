"""F3 — GetInstrumentComposite (mock repo / sin OHLCV)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bolsa_application.get_instrument_composite import GetInstrumentComposite


class _FakeInstruments:
    def __init__(self, instrument, fundamentals) -> None:
        self._instrument = instrument
        self._fundamentals = fundamentals

    async def get_by_id(self, instrument_id: str):
        if self._instrument and self._instrument.id == instrument_id:
            return self._instrument
        return None

    async def get_fundamentals(self, instrument_id: str):
        if instrument_id == self._instrument.id:
            return self._fundamentals
        return None


@pytest.mark.asyncio
async def test_composite_without_ohlcv():
    instrument = SimpleNamespace(id="inst-1", symbol="ACME")
    fund = {
        "marketCap": 8e10,
        "trailingPe": 12.0,
        "roe": 0.18,
        "operatingMargin": 0.14,
        "debtToEquity": 0.4,
        "currentRatio": 1.5,
        "fcfYield": 0.03,
        "altmanZ": 3.0,
        "fetchedAt": "2026-07-29T12:00:00Z",
        "sourceVersion": "yahoo_quote_summary_v3",
    }
    uc = GetInstrumentComposite(_FakeInstruments(instrument, fund), ohlcv=None)
    card = await uc.execute("inst-1", horizon="swing", regime="neutral")
    assert card is not None
    assert card["ticker"] == "ACME"
    assert card["metadata"]["paperDUnlocked"] is True
    assert card["combinedScore"] is not None
    chips = await uc.execute_chips(["inst-1", "missing"])
    assert len(chips) == 1
    assert chips[0]["instrumentId"] == "inst-1"


@pytest.mark.asyncio
async def test_composite_as_of_blocks_lookahead_fund():
    instrument = SimpleNamespace(id="inst-1", symbol="ACME")
    fund = {
        "marketCap": 8e10,
        "trailingPe": 12.0,
        "roe": 0.18,
        "operatingMargin": 0.14,
        "debtToEquity": 0.4,
        "currentRatio": 1.5,
        "fcfYield": 0.03,
        "altmanZ": 3.0,
        "fetchedAt": "2026-07-29T12:00:00Z",
        "sourceVersion": "yahoo_quote_summary_v3",
    }

    class _Ohlcv:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def execute(self, instrument_id: str, **kwargs):
            self.calls.append(kwargs)
            return []

    ohlcv = _Ohlcv()
    uc = GetInstrumentComposite(_FakeInstruments(instrument, fund), ohlcv=ohlcv)
    card = await uc.execute("inst-1", as_of="2024-01-01")
    assert card is not None
    assert card["metadata"]["pointInTime"] == "blocked"
    assert card["metadata"]["asOfDate"] == "2024-01-01"
    assert card["metadata"]["taCutToAsOf"] is True
    assert ohlcv.calls and ohlcv.calls[0].get("date_to") == "2024-01-01"
    fund_leg = next(L for L in card["legs"] if L["key"] == "fundamental")
    assert fund_leg["score"] is None
    assert any("look-ahead" in w or "as-of" in w.lower() for w in card["warnings"])
