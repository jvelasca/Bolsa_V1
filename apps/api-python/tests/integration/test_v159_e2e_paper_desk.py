"""V1.59 GP-V159-01..03 + GP-V159-07 — paper desk + portfolio operational wire."""

from __future__ import annotations

import pytest
from tests.integration.v159_harness import (
    create_funded_account,
    first_instrument_id,
    integration_client,
    seed_buy_trade,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_gp_v159_01_trade_portfolio_operational() -> None:
    """GP-V159-01: buy HTTP → portfolio con posición y operational si hay PositionState."""
    async with integration_client() as (app, client):
        account_id = await create_funded_account(client, name_prefix="v159-01")
        instrument_id = await first_instrument_id(client)
        await seed_buy_trade(app, client, account_id, instrument_id)

        portfolio = await client.get(
            "/api/portfolio",
            headers={"X-Account-Id": account_id},
        )
        assert portfolio.status_code == 200, portfolio.text
        positions = portfolio.json()["data"]["positions"]
        match = next(p for p in positions if p["instrumentId"] == instrument_id)
        assert match["quantity"] > 0
        operational = match.get("operational")
        if operational is not None:
            assert operational.get("status")
            assert operational.get("direction")


async def test_gp_v159_02_paper_desk_cycle_dry_run() -> None:
    """GP-V159-02: POST /paper-desk/cycle dryRun=true → cycle + autoDesk."""
    async with integration_client() as (_app, client):
        account_id = await create_funded_account(client, name_prefix="v159-02")
        before = await client.get(
            "/api/portfolio",
            headers={"X-Account-Id": account_id},
        )
        assert before.status_code == 200
        cash_before = before.json()["data"]["portfolio"]["cash"]

        cycle = await client.post(
            f"/api/paper-desk/cycle?accountId={account_id}",
            json={"dryRun": True, "templateId": "moderate"},
        )
        assert cycle.status_code == 200, cycle.text
        body = cycle.json()["data"]
        assert "cycle" in body
        assert "autoDesk" in body
        assert body["cycle"]["accountId"] == account_id

        after = await client.get(
            "/api/portfolio",
            headers={"X-Account-Id": account_id},
        )
        assert after.status_code == 200
        assert after.json()["data"]["portfolio"]["cash"] == cash_before


async def test_gp_v159_03_paper_desk_cycle_blocked_without_paper_d_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-V159-03: dryRun=false con PAPER_D_EXECUTE off → 403 paper_auto_env_blocked."""
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    async with integration_client() as (_app, client):
        account_id = await create_funded_account(client, name_prefix="v159-03")
        blocked = await client.post(
            f"/api/paper-desk/cycle?accountId={account_id}",
            json={"dryRun": False, "templateId": "moderate"},
        )
        assert blocked.status_code == 403, blocked.text
        detail = blocked.json()["detail"]
        if isinstance(detail, dict):
            assert detail.get("code") == "paper_auto_env_blocked"
        else:
            assert "paper_auto_env_blocked" in str(detail)


async def test_gp_v159_07_execute_auto_dry_run() -> None:
    """GP-V159-07: execute-auto dryRun=true sobre posición abierta."""
    async with integration_client() as (app, client):
        account_id = await create_funded_account(client, name_prefix="v159-07")
        instrument_id = await first_instrument_id(client)
        await seed_buy_trade(app, client, account_id, instrument_id)

        dry = await client.post(
            "/api/position-automation/execute-auto"
            f"?accountId={account_id}&instrumentId={instrument_id}",
            json={"dryRun": True, "templateId": "moderate"},
        )
        assert dry.status_code == 200, dry.text
        payload = dry.json()
        assert payload["dryRun"] is True
        assert payload["status"] in {"held", "allowed", "denied"}

        blocked = await client.post(
            "/api/position-automation/execute-auto"
            f"?accountId={account_id}&instrumentId={instrument_id}",
            json={"dryRun": False, "templateId": "moderate"},
        )
        assert blocked.status_code == 403, blocked.text
