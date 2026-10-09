"""Tax-report tras una operación redonda real (buy + SELL con plusvalía).

Nota de operativa — **la venta va por HTTP porque la posición nació manual**:

    1. La compra es una apertura humana por HTTP (`POST /portfolio/trade`), que el
       OpeningGate permite (el test la habilita con `seed_http_opening_allow`). El sync
       post-fill sintetiza el snapshot `manual-{tx}` ⇒ la posición nace `HUMAN_MANUAL`.
    2. Una posición `HUMAN_MANUAL` **cierra por HTTP** (V2.88.85 / H1,
       `row_is_human_manual`): quien abrió en MANUAL puede cerrar. El fence de venta
       (`ExitVetoedError` → 403 `position_exit_requires_confirm`) sigue vigente **solo**
       para posiciones SEMI/AUTO (origen != manual), cubierto por
       `packages/py/application/tests/test_execute_gated_portfolio_trade.py`.
    3. La operación redonda se completa por el MISMO canal manual (buy + sell por
       `POST /portfolio/trade`); el SELL alimenta el ledger que lee `/tax-report`.

`/tax-report` construye FIFO sobre el ledger; con comisión "none" la ganancia realizada
debe ser exactamente (120 − 100) × 5 = 100.0.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from tests.opening_gate_seed import seed_http_opening_allow

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
            await seed_http_opening_allow(app, client, account_id, instrument_id)

            # --- Pata de APERTURA: buy humana por HTTP (permitida por el OpeningGate).
            buy = await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={
                    "instrumentId": instrument_id,
                    "type": "buy",
                    "quantity": 10,
                    "price": 100,
                    "idempotencyKey": "tax-buy-1-abcdefghij",
                },
            )
            assert buy.status_code == 200

            # --- Pata de SALIDA real: sell humana por HTTP. La posición nació
            # HUMAN_MANUAL, así que el fence de venta (V2.88.85) NO aplica: cierra por HTTP.
            sell = await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={
                    "instrumentId": instrument_id,
                    "type": "sell",
                    "quantity": 5,
                    "price": 120,
                    "idempotencyKey": "tax-sell-1-abcdefghij",
                },
            )
            assert sell.status_code == 200, sell.text

            from datetime import datetime

            year = datetime.now().year
            report = await client.get(f"/api/accounts/{account_id}/tax-report?year={year}")
            assert report.status_code == 200
            data = report.json()["data"]
            assert data["method"] == "fifo"
            assert len(data["realizedLines"]) == 1
            assert data["realizedLines"][0]["realizedGain"] == 100.0
