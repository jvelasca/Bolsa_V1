"""V1.59 GP-V159-04..06 — recon · journal · incident HTTP wire."""

from __future__ import annotations

import pytest
from tests.integration.v159_harness import (
    create_funded_account,
    first_instrument_id,
    heal_portfolio_cash_drift,
    integration_client,
    open_portfolio_drift_incident,
    seed_buy_trade,
    seed_portfolio_cash_drift,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

_DRIFT_AMOUNT = 500.0


async def test_gp_v159_04_ops_self_eval_recon_clean_after_trade() -> None:
    """GP-V159-04: cuenta recién sembrada → recon ok/not_wired, no drift."""
    async with integration_client() as (app, client):
        account_id = await create_funded_account(client, name_prefix="v159-04")
        instrument_id = await first_instrument_id(client)
        await seed_buy_trade(app, client, account_id, instrument_id)

        eval_resp = await client.get(
            f"/api/risk/ops-self-eval?accountId={account_id}",
        )
        assert eval_resp.status_code == 200, eval_resp.text
        recon_status = eval_resp.json()["portfolioReconciliation"]["status"]
        assert recon_status in {"ok", "not_wired", "clean"}
        assert recon_status != "drift"


async def test_gp_v159_05_decision_journal_list_read_only() -> None:
    """GP-V159-05: GET decision-journal → envelope data.entries (array)."""
    async with integration_client() as (_app, client):
        account_id = await create_funded_account(client, name_prefix="v159-05")
        journal = await client.get(f"/api/accounts/{account_id}/decision-journal")
        assert journal.status_code == 200, journal.text
        data = journal.json()["data"]
        assert data["accountId"] == account_id
        assert isinstance(data["entries"], list)
        assert data["total"] == len(data["entries"])


async def test_gp_v159_06_incident_resolve_clear_http_no_auto_heal() -> None:
    """GP-V159-06: drift → INC → resolve → clear solo si recon clean (HTTP)."""
    async with integration_client() as (app, client):
        account_id = await create_funded_account(client, name_prefix="v159-06")
        await seed_portfolio_cash_drift(app, account_id, drift_amount=_DRIFT_AMOUNT)
        await open_portfolio_drift_incident(app, account_id)

        drift_eval = await client.get(
            f"/api/risk/ops-self-eval?accountId={account_id}",
        )
        assert drift_eval.status_code == 200
        assert drift_eval.json()["portfolioReconciliation"]["status"] == "drift"

        active = await client.get(
            f"/api/accounts/{account_id}/operational-incidents/active",
        )
        assert active.status_code == 200, active.text
        incidents = active.json()["data"]["incidents"]
        assert len(incidents) == 1
        assert incidents[0]["kind"] == "portfolio_drift"
        assert incidents[0]["status"] == "open"
        incident_id = incidents[0]["incidentId"]

        resolved = await client.post(
            f"/api/accounts/{account_id}/operational-incidents/{incident_id}/resolve",
            json={
                "resolutionNote": "manual cash top-up verified",
                "resolvedBy": "operator",
            },
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["data"]["status"] == "resolved"

        clear_blocked = await client.post(
            f"/api/accounts/{account_id}/operational-incidents/{incident_id}/clear",
        )
        assert clear_blocked.status_code == 409, clear_blocked.text
        assert clear_blocked.json()["detail"] == "incident:recon_not_clean"

        await heal_portfolio_cash_drift(app, account_id, drift_amount=_DRIFT_AMOUNT)
        clean_eval = await client.get(
            f"/api/risk/ops-self-eval?accountId={account_id}",
        )
        assert clean_eval.json()["portfolioReconciliation"]["status"] == "clean"

        cleared = await client.post(
            f"/api/accounts/{account_id}/operational-incidents/{incident_id}/clear",
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["data"]["status"] == "cleared"

        empty = await client.get(
            f"/api/accounts/{account_id}/operational-incidents/active",
        )
        assert empty.json()["data"]["total"] == 0
