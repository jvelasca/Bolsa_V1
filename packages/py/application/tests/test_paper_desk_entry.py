"""V1.50 — EstudioPaperDeskEntry (EntryTick + CandidateSnapshot)."""

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
    assert propose.payloads[0]["templateId"] == "moderate"
    assert result.template_id == "moderate"
    assert result.operating_policy is not None
    assert result.operating_policy["templateId"] == "moderate"


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
    assert result.reason_code == "ENTRY_UNIVERSE_EMPTY"
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


@pytest.mark.asyncio
async def test_estudio_entry_universe_unavailable() -> None:
    entry = EstudioPaperDeskEntry(
        propose=_FakePropose({}),
        estudio_list=_FakeEstudioList(fail=True),
    )
    result = await entry.run_entry_tick(
        account_id="acc-1",
        as_of=None,
        dry_run=True,
        paper_d_execute=False,
        execution_policy_id=None,
        template_id="moderate",
    )
    assert result.status == "unavailable"
    assert result.reason_code == "ENTRY_UNIVERSE_UNAVAILABLE"
    assert result.proposed_count == 0


@pytest.mark.asyncio
async def test_estudio_entry_infra_unavailable() -> None:
    class _BoomPropose:
        async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
            _ = payload
            raise RuntimeError("db timeout")

    entry = EstudioPaperDeskEntry(
        propose=_BoomPropose(),
        estudio_list=_FakeEstudioList(ids=["inst-1"]),
    )
    result = await entry.run_entry_tick(
        account_id="acc-1",
        as_of="2026-09-01",
        dry_run=True,
        paper_d_execute=False,
        execution_policy_id=None,
        template_id="moderate",
    )
    assert result.status == "unavailable"
    assert result.reason_code == "ENTRY_INFRA_UNAVAILABLE"


def _opinion(
    *,
    instrument_id: str,
    stars: int,
) -> SimpleNamespace:
    return SimpleNamespace(
        instrument_id=instrument_id,
        stance="buy",
        dictamen_stars=stars,
        as_of_bar_date=date(2026, 9, 1),
    )


def _triggered_plan(*, price: float = 47.8) -> SimpleNamespace:
    return SimpleNamespace(
        trade_plan={
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": price,
            "structuralStop": 45.2,
            "target1": 52.5,
            "target2": 58.0,
            "riskAmount": 75.0,
            "expectedRR": 1.81,
            "executionAllowed": True,
            "whyNot": [],
        },
        last_close=price,
    )


class _InnerPropose:
    def __init__(self, by_id: dict[str, object]) -> None:
        self.by_id = by_id
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        iid = str(kwargs["instrument_id"])
        result = self.by_id.get(iid)
        if isinstance(result, Exception):
            raise result
        return result


class _Opinions:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    async def query(self, **kwargs: Any) -> list[Any]:
        _ = kwargs
        return self.rows


class _Instruments:
    async def get_by_id(self, instrument_id: str) -> Any:
        return SimpleNamespace(id=instrument_id, symbol=instrument_id)


class _Policies:
    def __init__(self, policy: Any) -> None:
        self._policy = policy

    async def get_policy(self, policy_id: str) -> Any:
        if self._policy and self._policy.id == policy_id:
            return self._policy
        return None


def _paper_policy() -> SimpleNamespace:
    return SimpleNamespace(
        id="pol-1",
        enabled=True,
        mode="paper_auto",
        account_id="acc-demo",
        strategy_definition_id="st-1",
        definition={"signalKinds": ["entry_long"]},
    )


@pytest.mark.asyncio
async def test_gp_desk_04_ranking_top_n_keeps_trade_plan() -> None:
    """GP-DESK-04: maxCandidates=2 conserva A,B (alarma 5 y 4) con TradePlan."""
    inner = _InnerPropose(
        {
            "A": _triggered_plan(),
            "B": _triggered_plan(),
            "C": _triggered_plan(),
            "D": _triggered_plan(),
        }
    )
    from bolsa_application.estudio_auto_hits import ProposeEstudioAutoOpenings

    propose = ProposeEstudioAutoOpenings(
        _Opinions(
            [
                _opinion(instrument_id="A", stars=5),
                _opinion(instrument_id="B", stars=4),
                _opinion(instrument_id="C", stars=3),
                _opinion(instrument_id="D", stars=2),
            ]
        ),
        inner,
        instruments=_Instruments(),
    )
    entry = EstudioPaperDeskEntry(
        propose=propose,
        estudio_list=_FakeEstudioList(ids=["A", "B", "C", "D"]),
        max_candidates=2,
    )
    result = await entry.run_entry_tick(
        account_id="acc-1",
        as_of="2026-09-01",
        dry_run=True,
        paper_d_execute=False,
        execution_policy_id=None,
        template_id="moderate",
    )
    ids = [c.instrument_id for c in result.candidates]
    assert ids == ["A", "B"]
    assert "C" not in ids and "D" not in ids
    assert [c.rank for c in result.candidates] == [1, 2]
    assert result.candidates[0].score == 5.0
    assert result.candidates[1].score == 4.0
    for snap in result.candidates:
        assert snap.trade_plan is not None
        assert snap.trade_plan["status"] == "TRIGGERED"
        assert snap.entry == 47.8
        assert snap.structural_stop == 45.2
        assert snap.target1 == 52.5
        assert snap.target2 == 58.0
        assert snap.risk_amount == 75.0
        assert snap.decision_id
        assert snap.template_id == "moderate"
        assert snap.analysis_as_of == "2026-09-01"
        assert snap.execution_as_of is None
        assert snap.mandate == "not_evaluated"
    called = [c["instrument_id"] for c in inner.calls]
    assert called == ["A", "B"]


@pytest.mark.asyncio
async def test_gp_desk_05_opening_gate_deny_no_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-DESK-05: TRIGGERED + gate DENY → sin ExecutionIntent."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-demo")

    class _DenyRouter:
        def __init__(self) -> None:
            self.hits: list[Any] = []

        async def execute(self, policy_id: str, hits: list[Any]) -> Any:
            _ = policy_id
            self.hits = hits
            return SimpleNamespace(
                policy_id=policy_id,
                mode="paper_auto",
                actions=[
                    SimpleNamespace(
                        instrument_id=hits[0]["instrumentId"],
                        signal_kind="entry_long",
                        status="skipped",
                        reason="portfolio_risk_limit",
                        transaction_id=None,
                    )
                ],
            )

    router = _DenyRouter()
    from bolsa_application.estudio_auto_hits import ProposeEstudioAutoOpenings

    propose = ProposeEstudioAutoOpenings(
        _Opinions([_opinion(instrument_id="A", stars=5)]),
        _InnerPropose({"A": _triggered_plan()}),
        instruments=_Instruments(),
        router=router,
        policies=_Policies(_paper_policy()),
    )
    entry = EstudioPaperDeskEntry(
        propose=propose,
        estudio_list=_FakeEstudioList(ids=["A"]),
    )
    result = await entry.run_entry_tick(
        account_id="acc-demo",
        as_of="2026-09-01",
        dry_run=False,
        paper_d_execute=True,
        execution_policy_id="pol-1",
        template_id="moderate",
    )
    assert result.executed_count == 0
    assert result.reason_code == "ENTRY_RISK_LIMIT"
    assert result.status == "blocked"
    assert result.proposed_count == 1
    assert result.candidates[0].reason_code == "ENTRY_RISK_LIMIT"
    assert result.candidates[0].vetoes
    assert router.hits[0]["tradePlan"]["status"] == "TRIGGERED"


@pytest.mark.asyncio
async def test_gp_desk_06_invalid_stop_never_buy() -> None:
    """GP-DESK-06: rank alto + stop inválido → skip, nunca BUY."""
    from bolsa_application.estudio_auto_hits import ProposeEstudioAutoOpenings

    inner = _InnerPropose(
        {
            "A": SimpleNamespace(
                trade_plan={
                    "status": "WATCH",
                    "quantity": 0,
                    "entry": 47.8,
                    "structuralStop": None,
                    "whyNot": ["no_stop"],
                    "executionAllowed": False,
                },
                last_close=47.8,
            )
        }
    )
    propose = ProposeEstudioAutoOpenings(
        _Opinions([_opinion(instrument_id="A", stars=5)]),
        inner,
        instruments=_Instruments(),
    )
    entry = EstudioPaperDeskEntry(
        propose=propose,
        estudio_list=_FakeEstudioList(ids=["A"]),
    )
    result = await entry.run_entry_tick(
        account_id="acc-1",
        as_of="2026-09-01",
        dry_run=True,
        paper_d_execute=False,
        execution_policy_id=None,
        template_id="moderate",
    )
    assert result.proposed_count == 0
    assert result.candidates == ()
    assert result.skipped[0].instrument_id == "A"
    assert result.skipped[0].reason_code == "ENTRY_INVALID_STOP"
    assert result.skipped[0].score == 5.0


@pytest.mark.asyncio
async def test_entry_template_changes_operating_policy() -> None:
    propose = _FakePropose(
        {"hitCount": 0, "skipped": [], "executeStatus": "dry_run", "notes": []}
    )
    entry = EstudioPaperDeskEntry(
        propose=propose,
        estudio_list=_FakeEstudioList(ids=["x"]),
    )
    cons = await entry.run_entry_tick(
        account_id="acc-1",
        as_of=None,
        dry_run=True,
        paper_d_execute=False,
        execution_policy_id=None,
        template_id="conservative",
    )
    agg = await entry.run_entry_tick(
        account_id="acc-1",
        as_of=None,
        dry_run=True,
        paper_d_execute=False,
        execution_policy_id=None,
        template_id="aggressive_swing",
    )
    assert cons.operating_policy is not None
    assert agg.operating_policy is not None
    assert cons.operating_policy["templateId"] == "conservative"
    assert agg.operating_policy["templateId"] == "aggressive_swing"
    assert (
        cons.operating_policy["sizing"]["maxOpenPositions"]
        != agg.operating_policy["sizing"]["maxOpenPositions"]
        or cons.operating_policy["concentration"]["maxSectorExposurePct"]
        != agg.operating_policy["concentration"]["maxSectorExposurePct"]
    )
    assert propose.payloads[0]["templateId"] == "conservative"
    assert propose.payloads[1]["templateId"] == "aggressive_swing"
