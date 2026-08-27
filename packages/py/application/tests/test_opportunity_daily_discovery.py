"""Tests — Opportunity Daily Discovery (V1.19)."""

from __future__ import annotations

import pytest

from bolsa_application.opportunity_daily_discovery import (
    DEFAULT_OPPORTUNITY_PROPOSE_CAP,
    DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
    OPPORTUNITY_DISCOVERY_PAYLOAD_KEY,
    ProposeOpportunityHits,
    account_wants_daily_scan,
    build_opportunity_scan_payload,
    is_opportunity_discovery_payload,
    resolve_universe_list_id,
    select_hits_for_propose,
)


def test_payload_marks_discovery_and_default_ibex() -> None:
    payload = build_opportunity_scan_payload(account_id="acc-1")
    assert payload[OPPORTUNITY_DISCOVERY_PAYLOAD_KEY] is True
    assert payload["universe"]["listId"] == DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID
    assert payload["opportunityAccountId"] == "acc-1"
    assert payload["opportunityProposeCap"] == DEFAULT_OPPORTUNITY_PROPOSE_CAP
    assert is_opportunity_discovery_payload(payload)
    assert not is_opportunity_discovery_payload({"universe": {"listId": "x"}})


def test_propose_cap_hard_limit() -> None:
    payload = build_opportunity_scan_payload(propose_cap=99)
    assert payload["opportunityProposeCap"] == DEFAULT_OPPORTUNITY_PROPOSE_CAP
    hits = [
        {"instrumentId": f"i{i}", "symbol": f"S{i}", "globalScore": float(i)}
        for i in range(30)
    ]
    selected = select_hits_for_propose(hits, cap=99)
    assert len(selected) == DEFAULT_OPPORTUNITY_PROPOSE_CAP
    assert selected[0]["globalScore"] == 29.0


def test_account_opt_in_default_off() -> None:
    assert account_wants_daily_scan(None) is False
    assert account_wants_daily_scan({}) is False
    assert account_wants_daily_scan({"opportunityDailyScanEnabled": True}) is True
    assert (
        resolve_universe_list_id({"opportunityUniverseListId": "my-list"}) == "my-list"
    )
    assert resolve_universe_list_id(None) == DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID


@pytest.mark.asyncio
async def test_propose_hits_never_marks_execute() -> None:
    calls: list[str] = []

    class _FakePropose:
        async def execute(self, **kwargs):  # noqa: ANN003
            calls.append(kwargs["instrument_id"])
            return {"ok": True}

    hits = [
        {"instrumentId": "a", "symbol": "A", "globalScore": 10},
        {"instrumentId": "b", "symbol": "B", "globalScore": 20},
        {"instrumentId": "c", "symbol": "C", "globalScore": 5},
    ]
    result = await ProposeOpportunityHits(_FakePropose()).execute(
        hits, account_id="acc", cap=2
    )
    assert result["executed"] is False
    assert result["auto"] is False
    assert result["proposed"] == 2
    assert calls == ["b", "a"]


def test_worker_start_respects_env_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from bolsa_infrastructure.config import Settings

    monkeypatch.setenv("OPPORTUNITY_DAILY_SCAN_ENABLED", "false")
    settings = Settings()
    assert settings.opportunity_daily_scan_enabled is False

    monkeypatch.setenv("OPPORTUNITY_DAILY_SCAN_ENABLED", "true")
    settings_on = Settings()
    assert settings_on.opportunity_daily_scan_enabled is True
    assert settings_on.opportunity_daily_universe_list_id == "ibex35"
