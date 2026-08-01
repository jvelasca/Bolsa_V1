import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan

STANDARD_ES_SETTINGS = {
    "commission": {
        "presetId": "standard_es",
        "label": "Broker estándar ES",
        "stockCommissionPct": 0.1,
        "stockCommissionMin": 1,
        "stockCommissionMax": 29,
        "vatOnCommissionPct": 21,
        "fxConversionPct": 0.5,
        "custodyAnnualPct": 0.2,
    },
    "tax": {
        "jurisdiction": "ES",
        "costBasisMethod": "fifo",
        "stampDutyBuyPct": 0.2,
        "dividendWithholdingPct": 19,
        "capitalGainsTaxPct": None,
        "fiscalYearStartMonth": 1,
    },
    "notes": None,
}

LIFECYCLE_SETTINGS = {
    **STANDARD_ES_SETTINGS,
    "commission": {
        **STANDARD_ES_SETTINGS["commission"],
        "custodyAnnualPct": None,
    },
}


async def _first_instrument_id(client: AsyncClient) -> str:
    response = await client.get("/api/instruments")
    response.raise_for_status()
    return response.json()["data"][0]["id"]


@pytest.mark.asyncio
async def test_create_account_with_investor_profile_payload() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create = await client.post(
                "/api/accounts",
                json={
                    "name": "Perfil custom account",
                    "currency": "EUR",
                    "initialDeposit": 25_000,
                    "investorProfile": {
                        "name": "Conservador test",
                        "horizon": "long_term",
                        "riskTolerance": "low",
                        "experience": "novice",
                        "objectives": ["preservation"],
                    },
                },
            )
            assert create.status_code == 201
            account = create.json()["data"]
            profile_id = account["activeProfileId"]
            assert profile_id

            profile = await client.get(f"/api/investor-profiles/{profile_id}")
            assert profile.status_code == 200
            data = profile.json()["data"]
            assert data["name"] == "Conservador test"
            assert data["declared"]["riskTolerance"] == "low"
            assert data["selectedPolicyTemplateId"] == "conservative"


@pytest.mark.asyncio
async def test_create_account_with_settings_and_trade_fees() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create = await client.post(
                "/api/accounts",
                json={
                    "name": "Test fees account",
                    "currency": "EUR",
                    "initialDeposit": 50_000,
                    "portfolioName": "Cartera test",
                    "settings": STANDARD_ES_SETTINGS,
                },
            )
            assert create.status_code == 201
            account = create.json()["data"]
            account_id = account["id"]
            assert account["settings"]["commission"]["presetId"] == "standard_es"
            assert account.get("activeProfileId")  # perfil moderate por defecto

            patch = await client.patch(
                f"/api/accounts/{account_id}/settings",
                json={"settings": STANDARD_ES_SETTINGS},
            )
            assert patch.status_code == 200

            instrument_id = await _first_instrument_id(client)
            trade = await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={
                    "instrumentId": instrument_id,
                    "type": "buy",
                    "quantity": 10,
                    "price": 100,
                },
            )
            assert trade.status_code == 200

            ledger = await client.get(f"/api/accounts/{account_id}/ledger")
            assert ledger.status_code == 200
            entries = ledger.json()["data"]
            types = {entry["type"] for entry in entries}
            assert "buy" in types
            assert "fee" in types


@pytest.mark.asyncio
async def test_account_cash_deposits_and_lifecycle() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create = await client.post(
                "/api/accounts",
                json={
                    "name": "Lifecycle test",
                    "currency": "EUR",
                    "initialDeposit": 10_000,
                    "settings": LIFECYCLE_SETTINGS,
                },
            )
            assert create.status_code == 201
            account_id = create.json()["data"]["id"]

            before = await client.get(f"/api/accounts/{account_id}/summary")
            cash_before = before.json()["data"]["cash"]

            deposit = await client.post(
                f"/api/accounts/{account_id}/deposits",
                json={"amount": 1000, "note": "Aportación"},
            )
            assert deposit.status_code == 201
            assert deposit.json()["data"]["kind"] == "external_deposit"

            summary = await client.get(f"/api/accounts/{account_id}/summary")
            assert summary.json()["data"]["cash"] == cash_before + 1000

            patch = await client.patch(
                f"/api/accounts/{account_id}",
                json={"name": "Lifecycle renombrada", "description": "Demo"},
            )
            assert patch.status_code == 200
            assert patch.json()["data"]["name"] == "Lifecycle renombrada"

            close = await client.post(f"/api/accounts/{account_id}/close")
            assert close.status_code == 200
            assert close.json()["data"]["status"] == "closed"

            # Soft-close: sigue listable en BD hasta purga
            closed_list = await client.get("/api/database/closed-accounts")
            assert closed_list.status_code == 200
            closed_ids = {a["id"] for a in closed_list.json()["data"]["accounts"]}
            assert account_id in closed_ids

            delete = await client.delete(f"/api/accounts/{account_id}")
            assert delete.status_code == 204

            gone = await client.get(f"/api/accounts/{account_id}")
            assert gone.status_code == 404

            closed_after = await client.get("/api/database/closed-accounts")
            assert account_id not in {
                a["id"] for a in closed_after.json()["data"]["accounts"]
            }


@pytest.mark.asyncio
async def test_purge_closed_simulated_accounts_batch() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create = await client.post(
                "/api/accounts",
                json={
                    "name": "Purge batch demo",
                    "currency": "EUR",
                    "initialDeposit": 1_000,
                    "settings": LIFECYCLE_SETTINGS,
                },
            )
            assert create.status_code == 201
            account_id = create.json()["data"]["id"]

            close = await client.post(f"/api/accounts/{account_id}/close")
            assert close.status_code == 200

            purge = await client.post(
                "/api/database/closed-accounts/purge",
                json={"limit": 50},
            )
            assert purge.status_code == 200
            body = purge.json()["data"]
            assert account_id in body["purgedIds"]

            gone = await client.get(f"/api/accounts/{account_id}")
            assert gone.status_code == 404


@pytest.mark.asyncio
async def test_set_default_account() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create = await client.post(
                "/api/accounts",
                json={"name": "Para principal", "currency": "EUR", "initialDeposit": 5000},
            )
            assert create.status_code == 201
            account_id = create.json()["data"]["id"]

            make_default = await client.post(f"/api/accounts/{account_id}/make-default")
            assert make_default.status_code == 200
            assert make_default.json()["data"]["isDefault"] is True

            listed = await client.get("/api/accounts")
            defaults = [a for a in listed.json()["data"] if a["isDefault"]]
            assert len(defaults) == 1
            assert defaults[0]["id"] == account_id
