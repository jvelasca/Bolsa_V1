import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan


async def _first_instrument_id(client: AsyncClient) -> str:
    response = await client.get("/api/instruments")
    response.raise_for_status()
    return response.json()["data"][0]["id"]


@pytest.mark.asyncio
async def test_tax_report_after_round_trip_trade() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create = await client.post(
                "/api/accounts",
                json={
                    "name": "Tax test account",
                    "initialDeposit": 100_000,
                    "settings": {
                        "commission": {
                            "presetId": "none",
                            "label": "Sin comisiones",
                            "stockCommissionPct": 0,
                            "stockCommissionMin": 0,
                            "stockCommissionMax": None,
                            "vatOnCommissionPct": 0,
                            "fxConversionPct": 0,
                            "custodyAnnualPct": None,
                        },
                        "tax": {
                            "jurisdiction": "ES",
                            "costBasisMethod": "fifo",
                            "stampDutyBuyPct": 0,
                            "dividendWithholdingPct": 19,
                            "capitalGainsTaxPct": None,
                            "fiscalYearStartMonth": 1,
                        },
                        "notes": None,
                    },
                },
            )
            assert create.status_code == 201
            account_id = create.json()["data"]["id"]
            instrument_id = await _first_instrument_id(client)

            buy = await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={"instrumentId": instrument_id, "type": "buy", "quantity": 10, "price": 100},
            )
            assert buy.status_code == 200

            sell = await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={"instrumentId": instrument_id, "type": "sell", "quantity": 5, "price": 120},
            )
            assert sell.status_code == 200

            from datetime import datetime

            year = datetime.now().year
            report = await client.get(f"/api/accounts/{account_id}/tax-report?year={year}")
            assert report.status_code == 200
            data = report.json()["data"]
            assert data["method"] == "fifo"
            assert len(data["realizedLines"]) == 1
            assert data["realizedLines"][0]["realizedGain"] == 100.0
