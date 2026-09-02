"""V1.68 GP-V168-05 — Hoy / Paper Desk seed harness (HTTP paridad Playwright)."""

from __future__ import annotations

import pytest
from tests.integration.v159_harness import create_funded_account, integration_client

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_gp_v168_05_hoy_paper_desk_daily_report() -> None:
    """GP-V168-05: cuenta aislada + GET daily-report → autoDesk presente."""
    async with integration_client() as (_app, client):
        account_id = await create_funded_account(client, name_prefix="v168")
        report = await client.get(
            f"/api/paper-desk/daily-report?accountId={account_id}",
            headers={"X-Account-Id": account_id},
        )
        assert report.status_code == 200, report.text
        body = report.json()["data"]
        assert body["accountId"] == account_id
        auto_desk = body.get("autoDesk")
        assert auto_desk is not None
        assert auto_desk.get("schemaVersion") == "paper_daily_report_v1"
        assert "entry" in auto_desk
        assert auto_desk.get("dryRun") is True

        cycle = await client.post(
            f"/api/paper-desk/cycle?accountId={account_id}",
            json={"dryRun": True, "templateId": "moderate"},
        )
        assert cycle.status_code == 200, cycle.text
        assert "autoDesk" in cycle.json()["data"]
