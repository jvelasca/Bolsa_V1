"""Parse SP500 CSV / SP100 HTML+markdown sin depender de Wikipedia en vivo."""



from __future__ import annotations



import httpx

import pytest



from bolsa_market.indices.wikipedia_constituents import (

    SP100_WIKI_MIRROR_URL,

    SP100_WIKI_URL,

    clear_remote_constituents_cache,

    fetch_sp100_members,

    fetch_sp500_members,

)





@pytest.fixture(autouse=True)

def _clear_cache() -> None:

    clear_remote_constituents_cache()





@pytest.mark.asyncio

async def test_fetch_sp500_from_csv_fixture() -> None:

    rows = ["Symbol,Security"] + [f"T{i:03d},Name {i}" for i in range(402)]

    body = "\n".join(rows)



    def handler(request: httpx.Request) -> httpx.Response:

        _ = request

        return httpx.Response(200, text=body)



    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:

        members = await fetch_sp500_members(client)

    assert len(members) == 402

    assert members[0].yahoo_symbol == "T000"





@pytest.mark.asyncio

async def test_fetch_sp100_falls_back_to_markdown_mirror() -> None:

    symbols = [f"{chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(90)]

    md_rows = "\n".join(f"| {s} | Company {s} | Information Technology |" for s in symbols)

    md = f"# S&P 100\n\n## Components\n\n| Symbol | Company | Sector |\n| --- | --- | --- |\n{md_rows}\n"



    def handler(request: httpx.Request) -> httpx.Response:

        url = str(request.url)

        if url.startswith(SP100_WIKI_URL):

            return httpx.Response(403, text="Please respect our robot policy")

        if url.startswith(SP100_WIKI_MIRROR_URL):

            return httpx.Response(200, text=md)

        return httpx.Response(404, text="no")



    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:

        members = await fetch_sp100_members(client)

    assert len(members) >= 80

    assert members[0].yahoo_symbol == "AA"


