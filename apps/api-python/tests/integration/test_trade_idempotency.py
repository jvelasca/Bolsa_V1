"""F1/M4 — idempotencia + contrato estricto en POST /api/portfolio/trade.

- Doble POST con la misma idempotencyKey → una sola transacción (mismo id).
- Valores no financieros (negativos / cero / type inválido) → 422 (HTTP).
- NaN/Inf/negativos → rechazados por Pydantic en el borde (D2 contrato estricto).
"""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from tests.opening_gate_seed import seed_http_opening_allow

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
            await seed_http_opening_allow(app, client, account_id, instrument_id)
            headers = {"X-Account-Id": account_id}
            payload = {
                "instrumentId": instrument_id,
                "type": "buy",
                "quantity": 10,
                "price": 100,
                "idempotencyKey": "order-abc-1234567890",
            }

            first = await client.post("/api/portfolio/trade", headers=headers, json=payload)
            assert first.status_code == 200
            first_tx_id = first.json()["data"]["transaction"]["id"]

            second = await client.post("/api/portfolio/trade", headers=headers, json=payload)
            assert second.status_code == 200
            second_tx_id = second.json()["data"]["transaction"]["id"]

            # Mismo idem-key → una sola transacción (mismo id), no duplica.
            assert second_tx_id == first_tx_id

            # R-10 F1: sin idem-key el contrato lo rechaza → 422 (clave obligatoria).
            fresh = await client.post(
                "/api/portfolio/trade",
                headers=headers,
                json={"instrumentId": instrument_id, "type": "buy", "quantity": 1, "price": 50},
            )
            assert fresh.status_code == 422


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
    default_key = "trade-key-1234567890"  # 19 chars, válida (16–128)
    base = {"instrumentId": "inst-1", "type": "buy", "quantity": 10, "idempotencyKey": default_key}
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
    # Válido + idempotency obligatoria (R-10 F1) y 16–128 chars (R-11 C2).
    ok = TradeRequestDto(
        instrumentId="inst-1", type="sell", quantity=5, price=10, idempotencyKey=default_key
    )
    assert ok.idempotency_key == default_key


@pytest.mark.parametrize(
    "bad_key",
    [None, "", "   ", "short", "x" * 15, "x" * 129],
    ids=["missing", "empty", "whitespace", "too_short", "15chars", "129chars"],
)
def test_trade_dto_rejects_invalid_idempotency_key(bad_key: object) -> None:
    # R-11 C2: sin clave / "" / whitespace / longitud <16 o >128 → 422 limpio.
    payload: dict[str, object] = {
        "instrumentId": "inst-1",
        "type": "buy",
        "quantity": 10,
        "price": 100,
    }
    if bad_key is not None:
        payload["idempotencyKey"] = bad_key
    with pytest.raises(ValidationError):
        TradeRequestDto(**payload)


def test_trade_dto_strips_whitespace_around_valid_key() -> None:
    # R-11 C2: clave válida con espacios exteriores se recorta; pasa tras strip.
    dto = TradeRequestDto(
        instrumentId="inst-1",
        type="buy",
        quantity=10,
        price=100,
        idempotencyKey="  key-16-abcdefghijklmnop  ",
    )
    assert dto.idempotency_key == "key-16-abcdefghijklmnop"
