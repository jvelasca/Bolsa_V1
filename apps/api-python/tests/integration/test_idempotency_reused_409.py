"""R-9.2 — IdempotencyKeyReused mapeado a HTTP 409.

La reutilización de una `idempotencyKey` con un payload distinto al persistido NO
se rejuega en silencio: el use-case lanza `IdempotencyKeyReused` y el exception
handler app-wide de `main.py` lo convierte a 409 Conflict. Idempotencia normal
(misma key + mismo payload) sigue rejugando con 200/201.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan
from tests.opening_gate_seed import seed_http_opening_allow

NO_FEE_SETTINGS = {
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
}


async def _make_account(client: AsyncClient) -> str:
    create = await client.post(
        "/api/accounts",
        json={"name": "Idempotency 409 account", "initialDeposit": 100_000, "settings": NO_FEE_SETTINGS},
    )
    assert create.status_code == 201
    return create.json()["data"]["id"]


async def _first_instrument_id(client: AsyncClient) -> str:
    response = await client.get("/api/instruments")
    response.raise_for_status()
    return response.json()["data"][0]["id"]


@pytest.mark.asyncio
async def test_trade_reused_key_different_price_returns_409() -> None:
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
                "idempotencyKey": "tk-409-abcdefghijkl",
            }

            first = await client.post("/api/portfolio/trade", headers=headers, json=payload)
            assert first.status_code == 200

            changed = await client.post(
                "/api/portfolio/trade",
                headers=headers,
                json={**payload, "price": 200},
            )
            assert changed.status_code == 409
            assert changed.json()["detail"]


@pytest.mark.asyncio
async def test_trade_reused_key_same_payload_still_replays_200() -> None:
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
                "idempotencyKey": "tk-replay-abcdefghijkl",
            }

            first = await client.post("/api/portfolio/trade", headers=headers, json=payload)
            assert first.status_code == 200
            replay = await client.post("/api/portfolio/trade", headers=headers, json=payload)
            assert replay.status_code == 200
            assert replay.json()["data"]["transaction"]["id"] == first.json()["data"]["transaction"]["id"]


@pytest.mark.asyncio
async def test_deposit_reused_key_different_amount_returns_409() -> None:
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            account_id = await _make_account(client)

            first = await client.post(
                f"/api/accounts/{account_id}/deposits",
                json={"amount": 1000, "idempotencyKey": "dep-409-abcdefghijkl"},
            )
            assert first.status_code == 201

            changed = await client.post(
                f"/api/accounts/{account_id}/deposits",
                json={"amount": 5, "idempotencyKey": "dep-409-abcdefghijkl"},
            )
            assert changed.status_code == 409
            assert changed.json()["detail"]


@pytest.mark.asyncio
async def test_deposit_and_withdraw_without_key_return_422() -> None:
    """R-10 F1: la idempotencyKey es OBLIGATORIA en deposit/withdraw (contrato estricto).

    Un POST sin la clave se rechaza en el borde con 422 (validación Pydantic), de modo
    que un retry HTTP sin clave no puede crear una 2ª operación."""
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            account_id = await _make_account(client)

            deposit = await client.post(
                f"/api/accounts/{account_id}/deposits",
                json={"amount": 1000},
            )
            assert deposit.status_code == 422

            withdraw = await client.post(
                f"/api/accounts/{account_id}/withdrawals",
                json={"amount": 1000},
            )
            assert withdraw.status_code == 422


@pytest.mark.asyncio
async def test_deposit_and_withdraw_empty_or_whitespace_key_return_422() -> None:
    """R-11 C2: idempotencyKey vacía (`""`) o whitespace puro (`"   "`) → 422.

    str_strip_whitespace recorta antes de validar: una cadena de solo espacios queda
    vacía y `min_length=16` la rechaza, igual que una clave ausente."""
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            account_id = await _make_account(client)

            for bad_key in ("", "   "):
                for endpoint in ("deposits", "withdrawals"):
                    resp = await client.post(
                        f"/api/accounts/{account_id}/{endpoint}",
                        json={"amount": 1000, "idempotencyKey": bad_key},
                    )
                    assert resp.status_code == 422, (
                        f"esperaba 422 para {endpoint} key={bad_key!r}, obtuve {resp.status_code}"
                    )
            # Clave válida 16–128 con espacios exteriores se recorta y pasa → 201.
            ok = await client.post(
                f"/api/accounts/{account_id}/deposits",
                json={"amount": 1000, "idempotencyKey": "  dep-ok-abcdefghijkl  "},
            )
            assert ok.status_code == 201


@pytest.mark.asyncio
async def test_trade_empty_or_short_idempotency_key_return_422() -> None:
    """R-11 C2: clave de trade vacía/whitespace o fuera de 16–128 chars → 422 clean."""
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            account_id = await _make_account(client)
            instrument_id = await _first_instrument_id(client)
            headers = {"X-Account-Id": account_id}
            base = {"instrumentId": instrument_id, "type": "buy", "quantity": 1, "price": 50}
            for bad_key in (None, "", "   ", "short", "x" * 15, "x" * 129):
                payload: dict[str, object] = dict(base)
                if bad_key is not None:
                    payload["idempotencyKey"] = bad_key
                resp = await client.post("/api/portfolio/trade", headers=headers, json=payload)
                assert resp.status_code == 422, (
                    f"esperaba 422 para key={bad_key!r}, obtuve {resp.status_code}"
                )
