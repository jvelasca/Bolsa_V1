"""I1 — POST /portfolio/trade gate-in (buy = check_opening, sell = skip)."""

import pytest
from httpx import ASGITransport, AsyncClient
from tests.opening_gate_seed import seed_http_opening_allow

from bolsa_api.main import create_app, lifespan


async def _first_instrument_id(client: AsyncClient) -> str:
    response = await client.get("/api/instruments")
    response.raise_for_status()
    return response.json()["data"][0]["id"]


@pytest.mark.asyncio
async def test_portfolio_trade_buy_without_mandate_returns_403() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create = await client.post(
                "/api/accounts",
                json={"name": "I1 gate veto", "initialDeposit": 50_000},
            )
            assert create.status_code == 201
            account_id = create.json()["data"]["id"]
            instrument_id = await _first_instrument_id(client)
            trade = await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={
                    "instrumentId": instrument_id,
                    "type": "buy",
                    "quantity": 1,
                    "price": 10,
                    "idempotencyKey": "i1-veto-abcdefghij",
                },
            )
            assert trade.status_code == 403
            assert trade.json()["detail"] == "risk_veto"


@pytest.mark.asyncio
async def test_portfolio_trade_buy_allows_when_opening_seeded() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create = await client.post(
                "/api/accounts",
                json={"name": "I1 gate allow", "initialDeposit": 50_000},
            )
            account_id = create.json()["data"]["id"]
            instrument_id = await _first_instrument_id(client)
            await seed_http_opening_allow(app, client, account_id, instrument_id)
            trade = await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={
                    "instrumentId": instrument_id,
                    "type": "buy",
                    "quantity": 1,
                    "price": 10,
                    "idempotencyKey": "i1-allow-abcdefghij",
                },
            )
            assert trade.status_code == 200, trade.text
            assert trade.json()["data"]["transaction"]["id"]
