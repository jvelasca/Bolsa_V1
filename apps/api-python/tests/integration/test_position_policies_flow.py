import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan


async def _first_instrument_id(client: AsyncClient) -> str:
    response = await client.get("/api/instruments")
    response.raise_for_status()
    return response.json()["data"][0]["id"]


@pytest.mark.asyncio
async def test_position_policy_buy_and_evaluate_exits_flow() -> None:
    """Simula: cuenta → compra → position policy → evaluate-exits (P6/P7)."""
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_account = await client.post(
                "/api/accounts",
                json={
                    "name": "Position policy sim",
                    "currency": "EUR",
                    "initialDeposit": 100_000,
                },
            )
            assert create_account.status_code == 201
            account_id = create_account.json()["data"]["id"]

            instrument_id = await _first_instrument_id(client)

            trade = await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={
                    "instrumentId": instrument_id,
                    "type": "buy",
                    "quantity": 5,
                    "price": 50,
                },
            )
            assert trade.status_code == 200

            portfolio = await client.get(
                "/api/portfolio",
                headers={"X-Account-Id": account_id},
            )
            assert portfolio.status_code == 200
            positions = portfolio.json()["data"]["positions"]
            assert any(p["instrumentId"] == instrument_id and p["quantity"] > 0 for p in positions)

            strategy = await client.post(
                "/api/strategies/from-preset",
                json={
                    "name": "SMA exit sim",
                    "presetKey": "sma_crossover",
                    "timeframe": "1d",
                },
            )
            assert strategy.status_code == 201
            strategy_id = strategy.json()["data"]["id"]

            policy = await client.post(
                "/api/position-policies",
                json={
                    "accountId": account_id,
                    "instrumentId": instrument_id,
                    "mode": "exit_strategy",
                    "exitStrategyDefinitionId": strategy_id,
                },
            )
            assert policy.status_code == 201
            policy_id = policy.json()["data"]["id"]
            assert policy.json()["data"]["mode"] == "exit_strategy"

            listed = await client.get(
                f"/api/position-policies?accountId={account_id}",
            )
            assert listed.status_code == 200
            assert any(item["id"] == policy_id for item in listed.json()["data"])

            evaluate = await client.post(
                f"/api/position-policies/evaluate-exits?accountId={account_id}&timeframe=1d",
            )
            assert evaluate.status_code == 200
            body = evaluate.json()["data"]
            assert body["accountId"] == account_id
            assert body["evaluatedCount"] >= 1

            result = next(
                item for item in body["results"] if item["instrumentId"] == instrument_id
            )
            assert result["policyId"] == policy_id
            assert result["status"] in {
                "no_bars",
                "no_signal",
                "exit_signal",
                "manual",
            }
            assert result["quantity"] == 5

            cleanup = await client.delete(f"/api/position-policies/{policy_id}")
            assert cleanup.status_code == 204


@pytest.mark.asyncio
async def test_evaluate_exits_without_policy_reports_no_policy() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_account = await client.post(
                "/api/accounts",
                json={"name": "Sin policy", "currency": "EUR", "initialDeposit": 50_000},
            )
            account_id = create_account.json()["data"]["id"]
            instrument_id = await _first_instrument_id(client)

            await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={"instrumentId": instrument_id, "type": "buy", "quantity": 1, "price": 10},
            )

            evaluate = await client.post(
                f"/api/position-policies/evaluate-exits?accountId={account_id}",
            )
            assert evaluate.status_code == 200
            result = next(
                item
                for item in evaluate.json()["data"]["results"]
                if item["instrumentId"] == instrument_id
            )
            assert result["status"] == "no_policy"
