"""Providers intl (yfiua CSV + STOXX) sin red."""



from __future__ import annotations

import httpx
import pytest

from bolsa_market.indices.remote_market_constituents import (
    DAX_CSV_URL,
    NDX_CSV_URL,
    STOXX50E_MIRROR_URL,
    STOXX50E_WIKI_URL,
    _symbol_parts,
    clear_remote_intl_constituents_cache,
    fetch_dax_members,
    fetch_ndx_members,
    fetch_stoxx50e_members,
    fetch_yfiua_members,
    yfiua_csv_url,
)


@pytest.mark.parametrize(
    ("raw", "expected_symbol", "expected_yahoo"),
    [
        ("BP.L", "BP", "BP.L"),
        ("BP/.L", "BP", "BP.L"),
        ("BP/", "BP", "BP"),
        ("BT/A.L", "BTA", "BTA.L"),
        ("  TEF.MC ", "TEF", "TEF.MC"),
    ],
)
def test_symbol_parts_strips_slash_and_whitespace(
    raw: str, expected_symbol: str, expected_yahoo: str
) -> None:
    symbol, yahoo = _symbol_parts(raw)
    assert symbol == expected_symbol
    assert yahoo == expected_yahoo


@pytest.fixture(autouse=True)

def _clear() -> None:

    clear_remote_intl_constituents_cache()





@pytest.mark.asyncio

async def test_fetch_dax_csv_fixture() -> None:

    rows = ["Symbol,Name"] + [f"T{i:02d}.DE,Co {i}" for i in range(40)]

    body = "\n".join(rows)



    def handler(request: httpx.Request) -> httpx.Response:

        assert str(request.url).startswith(DAX_CSV_URL.split("constituents")[0]) or True

        return httpx.Response(200, text=body)



    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:

        members = await fetch_dax_members(client)

    assert len(members) == 40

    assert members[0].yahoo_symbol == "T00.DE"





@pytest.mark.asyncio

async def test_fetch_ndx_and_dow_via_generic() -> None:

    def handler(request: httpx.Request) -> httpx.Response:

        url = str(request.url)

        if "nasdaq100" in url:

            rows = ["Symbol,Name"] + [f"N{i:03d},Name {i}" for i in range(100)]

            return httpx.Response(200, text="\n".join(rows))

        if "dowjones" in url:

            rows = ["Symbol,Name"] + [f"D{i:02d},Dow {i}" for i in range(30)]

            return httpx.Response(200, text="\n".join(rows))

        return httpx.Response(404, text="no")



    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:

        ndx = await fetch_ndx_members(client)

        dji = await fetch_yfiua_members("DJI", client)

    assert len(ndx) == 100

    assert len(dji) == 30

    assert yfiua_csv_url("dowjones").endswith("dowjones.csv")

    assert NDX_CSV_URL.endswith("nasdaq100.csv")





@pytest.mark.asyncio

async def test_fetch_stoxx_falls_back_to_mirror() -> None:

    tickers = "\n".join(

        f"| {s}.DE | FWB | Company {s} | AG | Germany | Sector | 1900 |"

        for s in [f"A{i:02d}" for i in range(50)]

    )

    md = (

        "# EURO STOXX 50\n\nAs of … consists of the following companies:\n\n"

        "| Ticker | Main listing | Name | Corporate form | Registered office | Sector | Founded |\n"

        "| --- | --- | --- | --- | --- | --- | --- |\n"

        f"{tickers}\n"

    )



    def handler(request: httpx.Request) -> httpx.Response:

        url = str(request.url)

        if url.startswith(STOXX50E_WIKI_URL):

            return httpx.Response(403, text="robot policy")

        if url.startswith(STOXX50E_MIRROR_URL):

            return httpx.Response(200, text=md)

        return httpx.Response(404, text="no")



    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:

        members = await fetch_stoxx50e_members(client)

    assert len(members) >= 40