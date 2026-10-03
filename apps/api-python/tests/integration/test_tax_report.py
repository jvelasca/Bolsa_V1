"""Tax-report tras una operación redonda real (buy + SELL con plusvalía).

Nota de operativa (V1.32) — **por qué la venta va por Confirm y no por
`/portfolio/trade`**:

    1. La compra es una apertura humana por HTTP (`POST /portfolio/trade`), que el
       OpeningGate permite (el test la habilita con `seed_http_opening_allow`).
    2. La venta de una **posición abierta** por HTTP está VETADA a propósito:
       `ExecuteGatedPortfolioTrade` lanza `ExitVetoedError("position_exit_requires_confirm")`
       y la API responde 403. Ese 403 es **política**, no un bug: la salida humana de una
       posición abierta debe recorrer el Confirm SEMI (ExitPermission / firma humana).
    3. Por eso el SELL que produce la plusvalía que lee `/tax-report` se ejecuta por el
       camino real: `POST /ai/intents/confirm` con `action="reduce"` y `execute=true`.
       El Confirm infiere el lado (`sell`) de la dirección de la posición persistida
       (`effective_package_for_side`) y firma la pata de salida con `plannedQty`.

`/tax-report` construye FIFO sobre el ledger; con comisión "none" la ganancia realizada
debe ser exactamente (120 − 100) × 5 = 100.0.
"""

from uuid import uuid4

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

            # El HTTP sell de la posición abierta es política, no camino: se veta (403).
            vetoed_sell = await client.post(
                "/api/portfolio/trade",
                headers={"X-Account-Id": account_id},
                json={
                    "instrumentId": instrument_id,
                    "type": "sell",
                    "quantity": 5,
                    "price": 120,
                    "idempotencyKey": "tax-sell-vetoed-abcdefghij",
                },
            )
            assert vetoed_sell.status_code == 403, vetoed_sell.text
            assert "position_exit_requires_confirm" in vetoed_sell.json()["detail"]

            # --- Pata de SALIDA real: Confirm SEMI (reduce) → SELL en el ledger.
            # `decisionId` ÚNICO por corrida: el submit-intent durable se indexa por
            # decisionId, así que reutilizarlo haría que una segunda ejecución recuperara
            # el intent previo ("crash_after_fill_unconfirmed") en vez de operar.
            decision_id = f"tax-exit-{uuid4().hex[:12]}"
            exit_resp = await client.post(
                "/api/ai/intents/confirm",
                json={
                    "recommendation": {
                        "decisionId": decision_id,
                        "instrumentId": instrument_id,
                        "action": "reduce",
                        "suggestedQuantity": 5.0,
                        "suggestedPrice": 120.0,
                        "decisionPackage": {
                            "operativaIntent": "reduce",
                            "exitSource": "event",
                            "plannedQty": 5.0,
                            "exitPlan": {
                                "status": "TRIGGERED",
                                "suggestedAction": "reduce",
                                "primaryReason": "TARGET_1",
                                "suggestedQty": 5.0,
                            },
                        },
                    },
                    "accountId": account_id,
                    "execute": True,
                },
            )
            assert exit_resp.status_code == 200, exit_resp.text
            exit_trade = exit_resp.json()["data"].get("trade") or {}
            assert exit_trade.get("status") == "executed", exit_resp.text

            from datetime import datetime

            year = datetime.now().year
            report = await client.get(f"/api/accounts/{account_id}/tax-report?year={year}")
            assert report.status_code == 200
            data = report.json()["data"]
            assert data["method"] == "fifo"
            assert len(data["realizedLines"]) == 1
            assert data["realizedLines"][0]["realizedGain"] == 100.0
