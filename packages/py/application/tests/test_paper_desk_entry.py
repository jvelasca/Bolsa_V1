"""V1.49 — EstudioPaperDeskEntry (EntryTick real)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_application.daily_ops_report import (
    ESTUDIO_STATUS_EMPTY,
    ESTUDIO_STATUS_OK,
    ESTUDIO_STATUS_UNAVAILABLE,
)
from bolsa_application.operational_context import build_test_operational_context
from bolsa_application.paper_desk_cycle import PaperDeskCycle, PaperDeskCycleInput
from bolsa_application.paper_desk_entry import (
    EstudioPaperDeskEntry,
    map_estudio_propose_to_entry_tick,
    resolve_estudio_universe,
)


class _FakeEstudioList:
    def __init__(self, *, ids: list[str] | None = None, fail: bool = False) -> None:
        self.ids = ids
        self.fail = fail
        self.calls: list[str] = []

    async def execute(self, list_id: str) -> Any:
        self.calls.append(list_id)
        if self.fail:
            raise RuntimeError("list down")
        if self.ids is None:
            return None
        return SimpleNamespace(instrument_ids=list(self.ids))


class _FakePropose:
    def __init__(self, out: dict[str, Any]) -> None:
        self.out = out
        self.payloads: list[dict[str, Any]] = []

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payloads.append(payload)
        return self.out


@pytest.mark.asyncio
async def test_resolve_estudio_universe_ok() -> None:
    res = await resolve_estudio_universe(_FakeEstudioList(ids=["a", "b"]))
    assert res.status == ESTUDIO_STATUS_OK
    assert res.instrument_ids == ["a", "b"]


@pytest.mark.asyncio
async def test_resolve_estudio_universe_empty() -> None:
    res = await resolve_estudio_universe(_FakeEstudioList(ids=[]))
    assert res.status == ESTUDIO_STATUS_EMPTY


@pytest.mark.asyncio
async def test_resolve_estudio_universe_unavailable() -> None:
    assert (await resolve_estudio_universe(None)).status == ESTUDIO_STATUS_UNAVAILABLE
    assert (
        await resolve_estudio_universe(_FakeEstudioList(fail=True))
    ).status == ESTUDIO_STATUS_UNAVAILABLE


def test_map_propose_dry_run() -> None:
    result = map_estudio_propose_to_entry_tick(
        {
            "hitCount": 2,
            "skipped": [{"instrumentId": "x"}],
            "executeStatus": "dry_run",
            "notes": ["dry"],
        },
        dry_run=True,
    )
    assert result.status == "dry_run"
    assert result.proposed_count == 2
    assert result.skipped_count == 1


def test_map_propose_executed() -> None:
    result = map_estudio_propose_to_entry_tick(
        {
            "hitCount": 1,
            "skipped": [],
            "executeStatus": "executed",
            "execution": {
                "actions": [
                    {"status": "trade_executed"},
                    {"status": "skipped"},
                ]
            },
            "notes": [],
        },
        dry_run=False,
    )
    assert result.status == "executed"
    assert result.executed_count == 1


@pytest.mark.asyncio
async def test_estudio_entry_dry_run_proposes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    propose = _FakePropose(
        {
            "hitCount": 3,
            "skipped": [],
            "executeStatus": "dry_run",
            "notes": ["Modo dry-run (execute=false)."],
        }
    )
    entry = EstudioPaperDeskEntry(
        propose=propose,
        estudio_list=_FakeEstudioList(ids=["inst-1", "inst-2"]),
    )
    result = await entry.run_entry_tick(
        account_id="acc-1",
        as_of="2026-09-01",
        dry_run=True,
        paper_d_execute=False,
        execution_policy_id=None,
        template_id="moderate",
    )
    assert result.status == "dry_run"
    assert result.proposed_count == 3
    assert propose.payloads[0]["instrumentIds"] == ["inst-1", "inst-2"]
    assert propose.payloads[0]["execute"] is False
    assert propose.payloads[0]["asOfBarDate"] == date(2026, 9, 1)


@pytest.mark.asyncio
async def test_estudio_entry_empty_universe() -> None:
    entry = EstudioPaperDeskEntry(
        propose=_FakePropose({}),
        estudio_list=_FakeEstudioList(ids=[]),
    )
    result = await entry.run_entry_tick(
        account_id="acc-1",
        as_of=None,
        dry_run=True,
        paper_d_execute=False,
        execution_policy_id=None,
        template_id=None,
    )
    assert result.proposed_count == 0
    assert "empty" in result.notes[0].lower()


@pytest.mark.asyncio
async def test_gp_desk_03_cycle_dry_run_entry_proposes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-DESK-03: ciclo dry_run con EntryTick Estudio propone hits."""
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    propose = _FakePropose(
        {
            "hitCount": 2,
            "skipped": [{"instrumentId": "skip-1"}],
            "executeStatus": "dry_run",
            "notes": ["estudio_auto_propose_v1"],
        }
    )
    entry = EstudioPaperDeskEntry(
        propose=propose,
        estudio_list=_FakeEstudioList(ids=["inst-a"]),
    )

    class _EmptyOpen:
        async def list_open(self, account_id: str) -> list[Any]:
            _ = account_id
            return []

    uc = PaperDeskCycle(entry=entry, open_positions=_EmptyOpen(), execute_auto=None)
    result = await uc.execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01",
            dry_run=True,
            context=build_test_operational_context(marks={}),
        )
    )
    assert result.entry.proposed_count == 2
    assert result.entry.status == "dry_run"
    assert result.blocked is False
