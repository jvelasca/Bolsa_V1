"""R-12 A4. HTTP retry after timeout = second POST same idempotency_key.

Simula el caso cliente: el servidor ya completó el primer POST; el cliente
reintenta con la misma clave y el mismo payload. Resultado: un solo movimiento
de dinero, no dos.

SIGKILL / PostgreSQL restart mid-tx NO están en este fichero (gate opcional;
fuera de alcance). El 409 de payload distinto ya está cubierto en
`test_idempotency_reused_409.py`. Trades: `test_trade_idempotency.py`.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from bolsa_api.main import create_app, lifespan  # type: ignore[import-untyped]

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

# 201 (creación) o 200 (replay) son ambos válidos si el id no cambia.
_OK = (200, 201)


async def _make_account(client: AsyncClient) -> str:
    create = await client.post(
        "/api/accounts",
        json={
            "name": "HTTP retry idempotency account",
            "initialDeposit": 100_000,
            "settings": NO_FEE_SETTINGS,
        },
    )
    assert create.status_code == 201
    account_id = create.json()["data"]["id"]
    assert isinstance(account_id, str)
    return account_id


async def _cash(client: AsyncClient, account_id: str) -> float:
    summary = await client.get(f"/api/accounts/{account_id}/summary")
    assert summary.status_code == 200
    return float(summary.json()["data"]["cash"])


@pytest.mark.asyncio
async def test_http_retry_deposit_same_key_does_not_double_credit() -> None:
    """POST /deposits ×2 (misma key + payload) → un ingreso, mismo movement id."""
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            account_id = await _make_account(client)
            cash_before = await _cash(client, account_id)
            payload = {"amount": 1000, "idempotencyKey": "retry-dep-abcdefgh"}

            first = await client.post(f"/api/accounts/{account_id}/deposits", json=payload)
            assert first.status_code in _OK
            first_id = first.json()["data"]["id"]

            second = await client.post(f"/api/accounts/{account_id}/deposits", json=payload)
            assert second.status_code in _OK
            assert second.json()["data"]["id"] == first_id

            cash_after = await _cash(client, account_id)
            assert cash_after == cash_before + 1000


@pytest.mark.asyncio
async def test_http_retry_withdrawal_same_key_does_not_double_debit() -> None:
    """POST /withdrawals ×2 (misma key + payload) → un retiro, mismo movement id."""
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            account_id = await _make_account(client)
            cash_before = await _cash(client, account_id)
            payload = {"amount": 500, "idempotencyKey": "retry-wd-abcdefghij"}

            first = await client.post(
                f"/api/accounts/{account_id}/withdrawals", json=payload
            )
            assert first.status_code in _OK
            first_id = first.json()["data"]["id"]

            second = await client.post(
                f"/api/accounts/{account_id}/withdrawals", json=payload
            )
            assert second.status_code in _OK
            assert second.json()["data"]["id"] == first_id

            cash_after = await _cash(client, account_id)
            assert cash_after == cash_before - 500


@pytest.mark.asyncio
async def test_http_retry_deposit_and_withdraw_ledger_counts_once() -> None:
    """Depósito + retiro, cada uno reintentado: ledger cuenta 1+1; cash neto una vez.

    Trades ya cubiertos en `test_trade_idempotency_single_transaction`.
    """
    app = create_app()
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            account_id = await _make_account(client)
            cash_before = await _cash(client, account_id)
            dep_key = "retry-combo-dep-abcd"
            wd_key = "retry-combo-wd-abcd"

            dep_payload = {"amount": 1000, "idempotencyKey": dep_key}
            wd_payload = {"amount": 400, "idempotencyKey": wd_key}

            dep1 = await client.post(
                f"/api/accounts/{account_id}/deposits", json=dep_payload
            )
            dep2 = await client.post(
                f"/api/accounts/{account_id}/deposits", json=dep_payload
            )
            assert dep1.status_code in _OK and dep2.status_code in _OK
            assert dep2.json()["data"]["id"] == dep1.json()["data"]["id"]

            wd1 = await client.post(
                f"/api/accounts/{account_id}/withdrawals", json=wd_payload
            )
            wd2 = await client.post(
                f"/api/accounts/{account_id}/withdrawals", json=wd_payload
            )
            assert wd1.status_code in _OK and wd2.status_code in _OK
            assert wd2.json()["data"]["id"] == wd1.json()["data"]["id"]

            ledger = await client.get(f"/api/accounts/{account_id}/ledger")
            assert ledger.status_code == 200
            entries = ledger.json()["data"]
            dep_rows = [e for e in entries if e.get("referenceId") == dep_key]
            wd_rows = [e for e in entries if e.get("referenceId") == wd_key]
            assert len(dep_rows) == 1
            assert len(wd_rows) == 1

            cash_after = await _cash(client, account_id)
            assert cash_after == cash_before + 1000 - 400
