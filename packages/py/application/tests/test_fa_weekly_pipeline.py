"""FA weekly pipeline — Screener → whitelist → Paper D."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from bolsa_analytics.signals.fundamental_gate import build_fundamental_gate

from bolsa_application.fa_weekly_pipeline import (
    FA_WEEKLY_PIPELINE_VERSION,
    RunFaWeeklyPipeline,
    build_cron_payload_from_settings,
    default_fa_weekly_gate,
    is_fa_weekly_window,
)


class _FakeScreener:
    def __init__(self, result: dict) -> None:
        self.calls: list[dict] = []
        self._result = result

    async def execute(self, payload: dict) -> dict:
        self.calls.append(payload)
        return self._result


class _FakePropose:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, payload: dict) -> dict:
        self.calls.append(payload)
        return {
            "proposeVersion": "paper_d_propose_v2",
            "planId": "pd_test",
            "weekKey": "2026-W31",
            "scannedCount": 1,
            "eligibleCount": 1,
            "candidates": [],
            "rankingReady": True,
            "executeAllowedByEnv": False,
            "executeRequested": False,
            "executeStatus": "dry_run",
            "execution": None,
            "notes": [],
        }


def test_is_fa_weekly_window_friday_madrid():
    madrid = ZoneInfo("Europe/Madrid")
    friday_ok = datetime(2026, 7, 31, 18, 30, tzinfo=madrid)  # Friday
    friday_early = datetime(2026, 7, 31, 17, 0, tzinfo=madrid)
    thursday = datetime(2026, 7, 30, 19, 0, tzinfo=madrid)
    assert is_fa_weekly_window(friday_ok, weekday=4, hour=18)
    assert not is_fa_weekly_window(friday_early, weekday=4, hour=18)
    assert not is_fa_weekly_window(thursday, weekday=4, hour=18)


def test_default_gate_and_cron_payload():
    gate = default_fa_weekly_gate()
    assert gate["conditions"]
    settings = SimpleNamespace(
        fa_weekly_universe_list_id="uni-1",
        fa_weekly_whitelist_list_id="wl-sticky",
        fa_weekly_execution_policy_id="pol-1",
        fa_weekly_execute=False,
        fa_weekly_min_score_display_100=60,
        fa_weekly_max_candidates=10,
        fa_weekly_max_results=50,
        fa_weekly_gate_json=None,
        fa_weekly_max_trailing_pe=20.0,
        fa_weekly_min_roe=0.12,
        fa_weekly_min_piotroski=7.0,
        fa_weekly_use_sector_bands=True,
    )
    payload = build_cron_payload_from_settings(settings)
    assert payload is not None
    assert payload["universe"]["listId"] == "uni-1"
    assert payload["persist"]["listId"] == "wl-sticky"
    assert payload["minScoreDisplay100"] == 60
    assert payload["execute"] is False
    assert build_cron_payload_from_settings(SimpleNamespace(fa_weekly_universe_list_id=None)) is None


@pytest.mark.asyncio
async def test_pipeline_runs_propose_on_whitelist():
    gate = build_fundamental_gate(max_trailing_pe=25, min_roe=0.1, min_piotroski=6)
    screener = _FakeScreener(
        {
            "screenerVersion": "fund_screener_v1",
            "screenerId": "scr1",
            "scannedCount": 2,
            "hitCount": 1,
            "skippedCount": 1,
            "fundamentalsRefreshedCount": 0,
            "listId": "uni-1",
            "persistedListId": "snap-1",
            "weekKey": "2026-W31",
            "hits": [{"instrumentId": "a", "symbol": "PASS"}],
            "skipped": [],
        }
    )
    propose = _FakePropose()
    uc = RunFaWeeklyPipeline(screener, propose)
    result = await uc.execute(
        {
            "universe": {"listId": "uni-1"},
            "fundamentalGate": gate,
            "persist": {},
            "minScoreDisplay100": 55,
            "execute": False,
        }
    )
    assert result["pipelineVersion"] == FA_WEEKLY_PIPELINE_VERSION
    assert result["status"] == "completed"
    assert result["whitelistListId"] == "snap-1"
    assert result["propose"]["executeStatus"] == "dry_run"
    assert propose.calls[0]["universe"]["listId"] == "snap-1"
    assert screener.calls[0]["persist"] == {}


@pytest.mark.asyncio
async def test_pipeline_no_hits_skips_propose():
    gate = build_fundamental_gate(max_trailing_pe=25, min_roe=0.1)
    screener = _FakeScreener(
        {
            "screenerVersion": "fund_screener_v1",
            "screenerId": "scr2",
            "scannedCount": 1,
            "hitCount": 0,
            "skippedCount": 1,
            "fundamentalsRefreshedCount": 0,
            "listId": "uni-1",
            "persistedListId": None,
            "weekKey": "2026-W31",
            "hits": [],
            "skipped": [],
        }
    )
    propose = _FakePropose()
    uc = RunFaWeeklyPipeline(screener, propose)
    result = await uc.execute(
        {
            "universe": {"listId": "uni-1"},
            "fundamentalGate": gate,
            "persist": {},
        }
    )
    assert result["status"] == "completed_no_hits"
    assert result["propose"] is None
    assert propose.calls == []
