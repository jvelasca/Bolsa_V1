"""F1/M4 — idempotencia + contrato estricto en POST /api/portfolio/trade.

- Doble POST con la misma idempotencyKey → una sola transacción (mismo id).
- Valores no financieros (negativos / cero / type inválido) → 422 (HTTP).
- NaN/Inf/negativos → rechazados por Pydantic en el borde (D2 contrato estricto).
"""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from bolsa_api.main import create_app, lifespan
from bolsa_api.schemas.portfolio import TradeRequestDto


async def _first_instrument_id(client: AsyncClient) -> str:
    response = await client.get("/api/instruments")
    response.raise_for_status()
    return response.json()["data"][0]["id"]


async def _make_account(client: AsyncClient) -> str:
    create = await client.post(
        "/api/accounts",
        json={
            "name": "Idempotency test account",
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
    return create.json()["data"]["id"]


@pytest.mark.asyncio
async def test_trade_idempotency_single_transaction() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            account_id = await _make_account(client)
            instrument_id = await _first_instrument_id(client)
            headers = {"X-Account-Id": account_id}
            payload = {
                "instrumentId": instrument_id,
                "type": "buy",
                "quantity": 10,
                "price": 100,
                "idempotencyKey": "order-abc-123",
            }

            first = await client.post("/api/portfolio/trade", headers=headers, json=payload)
            assert first.status_code == 200
            first_tx_id = first.json()["data"]["transaction"]["id"]

            second = await client.post("/api/portfolio/trade", headers=headers, json=payload)
            assert second.status_code == 200
            second_tx_id = second.json()["data"]["transaction"]["id"]

            # Mismo idem-key → una sola transacción (mismo id), no duplica.
            assert second_tx_id == first_tx_id

            # Sin idem-key (parámetro opcional) → nueva transacción, no colisiona.
            fresh = await client.post(
                "/api/portfolio/trade",
                headers=headers,
                json={"instrumentId": instrument_id, "type": "buy", "quantity": 1, "price": 50},
            )
            assert fresh.status_code == 200
            assert fresh.json()["data"]["transaction"]["id"] != first_tx_id


@pytest.mark.asyncio
async def test_trade_rejects_non_financial_values_422() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            account_id = await _make_account(client)
            instrument_id = await _first_instrument_id(client)
            headers = {"X-Account-Id": account_id}
            base = {"instrumentId": instrument_id, "type": "buy"}

            for bad in (
                {**base, "quantity": -1, "price": 100},           # negativo
                {**base, "quantity": 0, "price": 100},            # cero
                {**base, "quantity": 10, "price": -5},            # precio negativo
                {**base, "type": "hold", "quantity": 10, "price": 100},  # type inválido
            ):
                resp = await client.post("/api/portfolio/trade", headers=headers, json=bad)
                assert resp.status_code == 422, f"esperaba 422 para {bad}, obtuve {resp.status_code}"


def test_trade_dto_rejects_nan_inf_and_negatives() -> None:
    # NaN/Inf no son JSON-serializables (el transporte los bloquea antes de llegar),
    # pero además Pydantic los rechaza en el borde junto con negativos (contrato estricto).
    base = {"instrumentId": "inst-1", "type": "buy", "quantity": 10}
    for bad in (
        {**base, "price": float("nan")},
        {**base, "quantity": float("nan")},
        {**base, "price": float("inf")},
        {**base, "quantity": float("-inf")},
        {**base, "quantity": -1},
        {**base, "type": "hold"},
    ):
        with pytest.raises(ValidationError):
            TradeRequestDto(**bad)
    # Válido + idempotency opcional
    ok = TradeRequestDto(instrumentId="inst-1", type="sell", quantity=5, price=10, idempotencyKey="k")
    assert ok.idempotency_key == "k"
