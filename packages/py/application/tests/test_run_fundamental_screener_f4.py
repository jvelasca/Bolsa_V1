"""F4 — RunFundamentalScreener con repos fake."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bolsa_analytics.signals.fundamental_gate import build_fundamental_gate
from bolsa_application.run_fundamental_screener import RunFundamentalScreener


class _FakeListDetail:
    def __init__(self, list_id: str, instrument_ids: list[str]) -> None:
        self.id = list_id
        self.instrument_ids = instrument_ids


class _FakeLists:
    def __init__(self, members: list[str]) -> None:
        self.members = members
        self.created: dict | None = None

    async def get_by_id(self, list_id: str):
        if list_id == "uni-1":
            return _FakeListDetail(list_id, self.members)
        return None

    async def create(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(id="snap-fa-1")

    async def update(self, list_id: str, **kwargs):
        return SimpleNamespace(id=list_id)


class _FakeInstruments:
    def __init__(self, by_id: dict[str, dict]) -> None:
        self._by_id = by_id

    async def get_by_id(self, instrument_id: str):
        if instrument_id not in self._by_id:
            return None
        return SimpleNamespace(id=instrument_id, symbol=self._by_id[instrument_id]["symbol"], name="X")

    async def get_fundamentals(self, instrument_id: str):
        row = self._by_id.get(instrument_id)
        return None if row is None else row["fund"]


def _fund(pe: float, roe: float = 0.15):
    return {
        "marketCap": 1e10,
        "trailingPe": pe,
        "sector": "Technology",
        "roe": roe,
        "operatingMargin": 0.12,
        "debtToEquity": 0.5,
        "currentRatio": 1.4,
        "fcfYield": 0.03,
        "altmanZ": 2.5,
        "piotroski": 7,
        "fetchedAt": "2026-07-29T12:00:00Z",
        "sourceVersion": "yahoo_quote_summary_v3",
    }


@pytest.mark.asyncio
async def test_screener_filters_and_persists(monkeypatch):
    # Evitar validate_scan_universe_size estricta si el universo es pequeño
    monkeypatch.setattr(
        "bolsa_application.scan_universe.validate_scan_universe_size",
        lambda *_a, **_k: None,
    )
    instruments = _FakeInstruments(
        {
            "a": {"symbol": "PASS", "fund": _fund(10)},
            "b": {"symbol": "FAIL", "fund": _fund(45)},
        }
    )
    lists = _FakeLists(["a", "b"])
    gate = build_fundamental_gate(max_trailing_pe=20, min_roe=0.1, min_piotroski=6)
    assert gate is not None
    uc = RunFundamentalScreener(instruments, lists, refresher=None)
    result = await uc.execute(
        {
            "universe": {"listId": "uni-1"},
            "fundamentalGate": gate,
            "refreshStale": False,
            "maxResults": 50,
            "persist": {"name": "FA test week"},
        }
    )
    assert result["hitCount"] == 1
    assert result["hits"][0]["symbol"] == "PASS"
    assert result["skippedCount"] >= 1
    assert result["persistedListId"] == "snap-fa-1"
    assert lists.created is not None
    assert lists.created["kind"] == "snapshot"
