"""Macro snapshot Yahoo — sin red (provider fake)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date

from bolsa_market.macro_snapshot import (
    clear_macro_snapshot_cache,
    fetch_macro_snapshot_dict,
)


@dataclass
class _Bar:
    close: float


class _FakeProvider:
    async def fetch_daily_bars(self, yahoo_symbol: str, from_date: date, to_date: date):
        if yahoo_symbol == "^VIX":
            # Serie ascendente → percentil alto al final
            return [_Bar(12 + i * 0.05) for i in range(260)]
        if yahoo_symbol == "^TNX":
            return [_Bar(4.2)]
        if yahoo_symbol == "^FVX":
            return [_Bar(3.8)]
        return []


def test_fetch_macro_snapshot_dict_builds_vix_and_curve():
    clear_macro_snapshot_cache()
    snap = asyncio.run(
        fetch_macro_snapshot_dict(provider=_FakeProvider(), use_cache=False)  # type: ignore[arg-type]
    )
    assert snap is not None
    assert snap["vix"] is not None
    assert snap["vix"] > 20
    assert snap["vixPercentile"] is not None
    assert snap["vixPercentile"] >= 90
    assert snap["yieldCurve10y2yBps"] == round((4.2 - 3.8) * 100, 1)
    assert snap["sourceVersion"] == "yahoo_macro_v1"


def test_fetch_macro_returns_none_without_data():
    clear_macro_snapshot_cache()

    class _Empty:
        async def fetch_daily_bars(self, yahoo_symbol, from_date, to_date):
            raise RuntimeError("offline")

    snap = asyncio.run(fetch_macro_snapshot_dict(provider=_Empty(), use_cache=False))  # type: ignore[arg-type]
    assert snap is None
