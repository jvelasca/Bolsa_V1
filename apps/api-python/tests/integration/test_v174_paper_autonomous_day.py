"""V1.74 GP-V174-06..08 — Paper Autonomous Day HTTP wire (dryRun multi-tick)."""

from __future__ import annotations

import pytest
from tests.integration.v159_harness import create_funded_account, integration_client

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_gp_v174_06_multi_tick_paper_desk_day_sections() -> None:
    """GP-V174-06: multi-tick dryRun cycle + daily-report sections DECISIONES/OPERATIVA."""
    async with integration_client() as (_app, client):
        account_id = await create_funded_account(client, name_prefix="v174-06")
        headers = {"X-Account-Id": account_id}

        for _ in range(2):
            cycle = await client.post(
                f"/api/paper-desk/cycle?accountId={account_id}",
                json={"dryRun": True, "templateId": "moderate", "asOf": "2026-09-02"},
                headers=headers,
            )
            assert cycle.status_code == 200, cycle.text
            auto_desk = cycle.json()["data"]["autoDesk"]
            assert auto_desk["schemaVersion"] == "paper_daily_report_v1"
            assert auto_desk.get("dryRun") is True
            sections = auto_desk.get("sections")
            assert sections is not None
            assert "decisiones" in sections
            assert "operativa" in sections
            assert "resultado" in sections

        report = await client.get(
            f"/api/paper-desk/daily-report?accountId={account_id}&asOf=2026-09-02",
            headers=headers,
        )
        assert report.status_code == 200, report.text
        body = report.json()["data"]
        assert body["accountId"] == account_id
        assert body.get("autoDesk") is not None
        assert body["autoDesk"].get("sections") is not None


async def test_gp_v174_07_decision_journal_read_only() -> None:
    """GP-V174-07: GET decision-journal envelope after paper-desk ticks."""
    async with integration_client() as (_app, client):
        account_id = await create_funded_account(client, name_prefix="v174-07")
        headers = {"X-Account-Id": account_id}

        cycle = await client.post(
            f"/api/paper-desk/cycle?accountId={account_id}",
            json={"dryRun": True, "asOf": "2026-09-02"},
            headers=headers,
        )
        assert cycle.status_code == 200, cycle.text

        journal = await client.get(
            f"/api/accounts/{account_id}/decision-journal",
            headers=headers,
        )
        assert journal.status_code == 200, journal.text
        data = journal.json()["data"]
        assert data["accountId"] == account_id
        assert isinstance(data["entries"], list)
        assert data["total"] == len(data["entries"])


async def test_gp_v174_08_ops_self_eval_recon_after_day_ticks() -> None:
    """GP-V174-08: ops-self-eval recon ok/not_wired after dryRun day ticks."""
    async with integration_client() as (_app, client):
        account_id = await create_funded_account(client, name_prefix="v174-08")
        headers = {"X-Account-Id": account_id}

        await client.post(
            f"/api/paper-desk/cycle?accountId={account_id}",
            json={"dryRun": True, "asOf": "2026-09-02"},
            headers=headers,
        )

        eval_resp = await client.get(
            f"/api/risk/ops-self-eval?accountId={account_id}",
            headers=headers,
        )
        assert eval_resp.status_code == 200, eval_resp.text
        recon_status = eval_resp.json()["portfolioReconciliation"]["status"]
        assert recon_status in {"ok", "not_wired", "clean"}
        assert recon_status != "drift"
