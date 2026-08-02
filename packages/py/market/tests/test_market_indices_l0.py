"""Tests L0 — índices: aliases, constitutivos IBEX, discovery offline."""

from __future__ import annotations

import pytest

from bolsa_market.indices import (
    CuratedConstituentProvider,
    canonical_index_code,
    discover_market_indices,
    expand_index_query_aliases,
    index_constituents_ready,
)


def test_catalog_list_id_stable() -> None:
    from bolsa_market.indices import catalog_list_id_for_index

    assert catalog_list_id_for_index("IBEX35") == "ibex35"
    assert catalog_list_id_for_index("SPX") == "idx-spx"


def test_aliases_resolve_popular_queries() -> None:
    assert canonical_index_code("IBEX35") == "IBEX35"
    assert canonical_index_code("sp500") == "SPX"
    assert canonical_index_code("S&P 500") == "SPX"
    assert canonical_index_code("dax") == "DAX"
    assert canonical_index_code("SP100") == "OEX"
    assert canonical_index_code("dow") == "DJI"
    assert canonical_index_code("ftse 100") == "FTSE100"
    assert canonical_index_code("hang seng") == "HSI"


def test_expand_aliases_includes_yahoo_symbol() -> None:
    expanded = expand_index_query_aliases("sp500")
    assert any("^GSPC" in x or x.upper() == "SPX" for x in expanded)


def test_curated_provider_ibex_ready_spx_via_remote_flag() -> None:
    assert index_constituents_ready("IBEX35") is True
    assert index_constituents_ready("SPX") is True
    assert index_constituents_ready("OEX") is True
    assert index_constituents_ready("DAX") is True
    assert index_constituents_ready("NDX") is True
    assert index_constituents_ready("STOXX50E") is True
    assert index_constituents_ready("DJI") is True
    assert index_constituents_ready("FTSE100") is True
    assert index_constituents_ready("FTSEMIB") is True
    assert index_constituents_ready("HSI") is True


@pytest.mark.asyncio
async def test_curated_provider_resolves_ibex() -> None:
    provider = CuratedConstituentProvider()
    ibex = await provider.resolve("IBEX35")
    assert ibex is not None
    assert ibex.index_code == "IBEX35"
    assert ibex.yahoo_index_symbol == "^IBEX"
    assert len(ibex.members) == 35
    assert ibex.provider == "curated_v1"
    assert await provider.resolve("^IBEX") is not None
    assert await provider.resolve("SPX") is None


@pytest.mark.asyncio
async def test_discover_offline_alias_and_known() -> None:
    hits = await discover_market_indices("IBEX", search_fn=None, limit=10)
    assert hits
    assert hits[0].yahoo_symbol == "^IBEX"
    assert hits[0].constituent_ready is True

    hits_sp = await discover_market_indices("SP500", search_fn=None, limit=10)
    assert hits_sp
    assert hits_sp[0].yahoo_symbol == "^GSPC"
    assert hits_sp[0].constituent_ready is True


@pytest.mark.asyncio
async def test_discover_filters_yahoo_index_only() -> None:
    async def fake_search(q: str, *, quotes_count: int = 10) -> list[dict]:
        _ = q, quotes_count
        return [
            {
                "symbol": "AAPL",
                "quoteType": "EQUITY",
                "shortname": "Apple",
                "score": 999,
            },
            {
                "symbol": "^GSPC",
                "quoteType": "INDEX",
                "shortname": "S&P 500",
                "score": 50,
            },
        ]

    hits = await discover_market_indices("whatever-xyz", search_fn=fake_search, limit=10)
    symbols = {h.yahoo_symbol for h in hits}
    assert "AAPL" not in symbols
    assert "^GSPC" in symbols
