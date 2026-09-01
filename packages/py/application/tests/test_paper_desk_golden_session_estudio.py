"""V1.53 Golden Session — 09:00 Estudio entry → protect → T1 → trail×2 → exit → Journal."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_analytics.cognitive.position_revision import revisions_from_raw
from bolsa_analytics.cognitive.position_state import position_state_from_dict
from bolsa_application.estudio_auto_hits import ProposeEstudioAutoOpenings
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    PaperPositionSellResult,
)
from bolsa_application.execution_router import ExecutionRouter
from bolsa_application.operational_context import build_test_operational_context
from bolsa_application.paper_daily_report import build_paper_daily_report
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
    PaperDeskCycleInput,
)
from bolsa_application.paper_desk_entry import EstudioPaperDeskEntry
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect
from bolsa_application.position_event_log import events_from_blob
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord


def _opinion(*, instrument_id: str, stars: int) -> SimpleNamespace:
    return SimpleNamespace(
        instrument_id=instrument_id,
        stance="buy",
        dictamen_stars=stars,
        as_of_bar_date=date(2026, 9, 1),
    )


def _golden_plan(*, instrument_id: str = "A", decision_id: str = "tp-A") -> SimpleNamespace:
    return SimpleNamespace(
        trade_plan={
            "decisionId": decision_id,
            "instrumentId": instrument_id,
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": 10.0,
            "entry": 100.0,
            "structuralStop": 95.0,
            "target1": 110.0,
            "target2": 120.0,
            "riskAmount": 50.0,
            "expectedRR": 2.0,
            "executionAllowed": True,
            "whyNot": [],
        },
        last_close=100.0,
    )


class _FakeEstudioList:
    def __init__(self, ids: list[str]) -> None:
        self.ids = ids

    async def execute(self, list_id: str) -> Any:
        _ = list_id
        return SimpleNamespace(instrument_ids=list(self.ids))


class _InnerPropose:
    def __init__(self, by_id: dict[str, object]) -> None:
        self.by_id = by_id

    async def execute(self, **kwargs: Any) -> Any:
        iid = str(kwargs["instrument_id"])
        return self.by_id[iid]


class _Instruments:
    async def get_by_id(self, instrument_id: str) -> Any:
        return SimpleNamespace(id=instrument_id, symbol=instrument_id)


class _SessionStore:
    def __init__(self) -> None:
        self.row: dict[str, Any] | None = None
        self.inserts: list[dict[str, Any]] = []

    async def list_open(self, account_id: str) -> list[dict[str, Any]]:
        _ = account_id
        if self.row is None or self.row.get("status") == "CLOSED":
            return []
        return [self.row]

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        _ = account_id
        if self.row is None or self.row.get("instrument_id") != instrument_id:
            return None
        if self.row.get("status") == "CLOSED":
            return None
        return self.row

    async def get_by_open_transaction_id(
        self, open_transaction_id: str
    ) -> dict[str, Any] | None:
        if self.row and self.row.get("open_transaction_id") == open_transaction_id:
            return self.row
        for item in self.inserts:
            if item.get("open_transaction_id") == open_transaction_id:
                return item
        return None

    async def insert(self, **kwargs: Any) -> dict[str, Any]:
        row = {
            "id": kwargs.get("position_id") or "pos-A",
            "account_id": kwargs["account_id"],
            "instrument_id": kwargs["instrument_id"],
            "status": kwargs.get("status") or "OPEN",
            "trade_plan_id": kwargs.get("trade_plan_id"),
            "open_transaction_id": kwargs["open_transaction_id"],
            "trade_plan_snapshot": kwargs.get("trade_plan_snapshot") or {},
            "position_state": kwargs.get("position_state") or {},
        }
        self.inserts.append(row)
        self.row = row
        return row

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any]:
        assert self.row is not None
        self.row = {
            **self.row,
            "id": position_id,
            "status": status,
            "position_state": position_state,
        }
        return self.row

    async def compare_and_swap_stop(
        self,
        *,
        position_id: str,
        expected_stop: float,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        blob = self.row.get("position_state") if self.row else None
        current = float(blob.get("currentStop")) if isinstance(blob, dict) else None
        if current is None or abs(current - float(expected_stop)) > 1e-9:
            return None
        return await self.update_state(
            position_id=position_id, status=status, position_state=position_state
        )


class _SeqTrade:
    def __init__(self) -> None:
        self.n = 0

    async def execute(self, **kwargs: Any) -> Any:
        _ = kwargs
        self.n += 1
        tx = type("Tx", (), {"id": f"tx-fill-{self.n}"})()
        return type("TradeResult", (), {"transaction": tx})()


class _PaperAccount:
    id = "acc-demo"
    type = "simulated"
    initial_deposit = 10_000.0
    active_profile_id = None


class _PaperScope:
    account = _PaperAccount()


class _PaperAccounts:
    async def resolve_scope(self, account_id: str, portfolio_id: str | None = None):
        _ = account_id, portfolio_id
        return _PaperScope()

    async def get_settings_json(self, account_id: str) -> dict[str, Any]:
        _ = account_id
        return {}

    async def merge_settings_json(self, account_id: str, fragment: dict[str, Any]) -> None:
        _ = account_id, fragment


class _EmptyBook:
    positions: list[Any] = []
    total_equity = 10_000.0

    async def execute(self, account_id: str | None = None, portfolio_id: str | None = None):
        _ = account_id, portfolio_id
        return self


class _Sell:
    def __init__(self) -> None:
        self.execute_count = 0
        self.by_key: dict[str, PaperPositionSellResult] = {}

    async def sell(self, **kwargs: Any) -> PaperPositionSellResult:
        key = str(kwargs.get("idempotency_key") or "")
        if key in self.by_key:
            return self.by_key[key]
        self.execute_count += 1
        qty = float(kwargs.get("quantity") or 0)
        result = PaperPositionSellResult(
            status="trade_executed",
            fill_quantity=qty,
            fill_price=float(kwargs.get("price") or 0),
            transaction_id=f"tx-exit-{self.execute_count}",
        )
        self.by_key[key] = result
        return result


class _Policies:
    def __init__(self, policy: ExecutionPolicyRecord) -> None:
        self._policy = policy

    async def get_policy(self, policy_id: str) -> Any:
        return self._policy if policy_id == self._policy.id else None


class _Opinions:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    async def query(self, **kwargs: Any) -> list[Any]:
        _ = kwargs
        return self.rows


def _paper_policy() -> ExecutionPolicyRecord:
    return ExecutionPolicyRecord(
        id="pol-1",
        name="paper",
        definition={"signalKinds": ["entry_long"]},
        mode="paper_auto",
        account_id="acc-demo",
        strategy_definition_id=None,
        origin="test",
        enabled=True,
        user_id=None,
        created_at="2026-09-01T00:00:00Z",
        updated_at="2026-09-01T00:00:00Z",
    )


def _build_cycles(store: _SessionStore, sell: _Sell) -> tuple[PaperDeskCycle, PaperDeskCycle]:
    policy = _paper_policy()
    router = ExecutionRouter(
        policy_repo=_Policies(policy),  # type: ignore[arg-type]
        account_repo=_PaperAccounts(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=_SeqTrade(),  # type: ignore[arg-type]
        portfolio_summary=_EmptyBook(),  # type: ignore[arg-type]
        profile_store=None,
        enforce_cognitive_gate=False,
        position_from_fill=PersistPositionFromFill(store),
    )
    propose = ProposeEstudioAutoOpenings(
        _Opinions([_opinion(instrument_id="A", stars=5)]),
        _InnerPropose({"A": _golden_plan()}),
        instruments=_Instruments(),
        router=router,
        policies=_Policies(policy),
    )
    entry = EstudioPaperDeskEntry(
        propose=propose,
        estudio_list=_FakeEstudioList(["A"]),
        max_candidates=1,
    )
    execute_auto = ExecutePositionPolicyAuto(
        protect=PersistPositionFromProtect(store),
        exit_persist=PersistPositionFromExit(store),
        sell=sell,
    )
    birth_cycle = PaperDeskCycle(
        entry=entry,
        open_positions=store,
        execute_auto=execute_auto,
    )
    position_cycle = PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=store,
        execute_auto=execute_auto,
    )
    return birth_cycle, position_cycle


def _assert_identities(row: dict[str, Any], *, candidate_id: str) -> None:
    snap = row["trade_plan_snapshot"]
    assert snap["decisionId"] == "tp-A"
    assert snap["candidateDecisionId"] == candidate_id
    assert snap["decisionId"] != snap["candidateDecisionId"]
    assert row["open_transaction_id"] == snap["fillId"]
    assert snap["fillId"].startswith("tx-fill-")


@pytest.mark.asyncio
async def test_golden_session_estudio_0900_birth_to_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-SESSION-01..04: Estudio 09:00 → protect → T1 → TRAIL×2 → exit → report."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-demo")

    store = _SessionStore()
    sell = _Sell()
    birth_cycle, position_cycle = _build_cycles(store, sell)

    open_ = await birth_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T09:00:00Z",
            dry_run=False,
            execution_policy_id="pol-1",
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 100.0}),
        )
    )
    assert open_.entry.executed_count == 1
    assert open_.entry.status == "executed"
    assert len(store.inserts) == 1
    assert store.row is not None
    candidate_id = open_.entry.candidates[0].decision_id
    _assert_identities(store.row, candidate_id=candidate_id)
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "pending"

    protect = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T10:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 105.0}, trail_hint=True, trail_stop=98.0
            ),
        )
    )
    assert protect.entry.status == "skipped"
    assert protect.positions[0].status == "protected"
    assert protect.positions[0].executed_action == "APPLIED"

    t1 = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T11:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 110.0}),
        )
    )
    assert t1.positions[0].status == "reduced"
    pos = position_state_from_dict((store.row or {})["position_state"])
    assert pos is not None
    assert pos.target1_leg is not None
    assert pos.target1_leg.status == "executed"
    assert sell.execute_count == 1

    await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T12:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 112.0}, trail_hint=True, trail_stop=102.0
            ),
        )
    )
    await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T13:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 115.0}, trail_hint=True, trail_stop=108.0
            ),
        )
    )
    events = [
        e for e in events_from_blob((store.row or {})["position_state"]) if e.event_type == "TRAIL"
    ]
    assert len(events) >= 2
    revs = [
        r
        for r in revisions_from_raw((store.row or {})["position_state"].get("revisions"))
        if r.origin == "trail"
    ]
    assert len(revs) >= 2
    assert all(r.decision_id == "tp-A" for r in revs)
    assert all(r.policy_id == "moderate" for r in revs)

    closed = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 94.0}),
        )
    )
    assert closed.positions[0].status == "exited"
    assert store.row is not None
    assert store.row["status"] == "CLOSED"
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.status == "CLOSED"
    _assert_identities(store.row, candidate_id=candidate_id)

    report = build_paper_daily_report(closed)
    assert report.position_exited == 1
    assert report.entry_status in {"skipped", "blocked"}
    assert sell.execute_count == 2
