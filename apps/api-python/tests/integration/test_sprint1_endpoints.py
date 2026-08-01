import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan


async def _first_instrument_id(client: AsyncClient) -> str:
    response = await client.get("/api/instruments")
    response.raise_for_status()
    return response.json()["data"][0]["id"]


@pytest.mark.asyncio
async def test_portfolio_response_shape() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/portfolio")

    assert response.status_code == 200
    body = response.json()["data"]
    assert {"portfolio", "positions", "totalEquity"}.issubset(body.keys())


@pytest.mark.asyncio
async def test_market_providers_shape() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/market/providers")

    assert response.status_code == 200
    providers = response.json()["data"]
    assert len(providers) == 2
    assert {providers[0]["id"], providers[1]["id"]} == {"yahoo", "xtb"}


@pytest.mark.asyncio
async def test_backtests_list_shape() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/backtests")

    assert response.status_code == 200
    assert "data" in response.json()


@pytest.mark.asyncio
async def test_live_quote_shape() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            instrument_id = await _first_instrument_id(client)
            response = await client.get(f"/api/instruments/{instrument_id}/live-quote")

    assert response.status_code == 200
    data = response.json()["data"]
    assert {"instrumentId", "symbol", "xtbAvailable"}.issubset(data.keys())
