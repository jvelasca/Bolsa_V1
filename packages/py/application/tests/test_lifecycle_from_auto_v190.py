"""V1.90 — AUTO → lifecycle sidecar mapping + execute hook."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.operating_policy import resolve_operating_policy
from bolsa_analytics.cognitive.position_event import build_position_event
from bolsa_analytics.cognitive.position_policy_decision import PositionPolicyDecision
from bolsa_analytics.cognitive.position_state import (
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    ExecutePositionPolicyAutoInput,
    PaperPositionSellResult,
)
from bolsa_application.lifecycle_event_store import (
    AppendLifecycleEvent,
    GetLifecycleSnapshot,
    InMemoryLifecycleEventStore,
)
from bolsa_application.lifecycle_from_auto import (
    build_lifecycle_auto_mapping,
    map_auto_verdict_to_kind,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect
from bolsa_domain.lifecycle import LifecycleEventInput


def test_map_auto_verdict_kinds() -> None:
    assert map_auto_verdict_to_kind(verdict="TRAIL") == "TRAIL_APPLIED"
    assert map_auto_verdict_to_kind(verdict="PROTECT") == "TRAIL_APPLIED"
    assert (
        map_auto_verdict_to_kind(verdict="REDUCE", reason_code="TARGET_1")
        == "T1_EXECUTED"
    )
    assert (
        map_auto_verdict_to_kind(verdict="REDUCE", reason_code="TARGET_2")
        == "T2_EXECUTED"
    )
    assert map_auto_verdict_to_kind(verdict="EXIT") == "POSITION_CLOSED"
    assert map_auto_verdict_to_kind(verdict="HOLD") is None


def test_build_mapping_requires_timestamp() -> None:
    assert (
        build_lifecycle_auto_mapping(
            verdict="EXIT",
            reason_code="STRUCTURAL_STOP",
            account_id="acc",
            instrument_id="inst",
            position_id="pos",
            event_id="evt",
            quantity=10,
            price=100,
            filled_at=None,
        )
        is None
    )


def _plan() -> dict[str, object]:
    return {
        "decisionId": "dec-auto-lc",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
    }


def _open_row(*, qty: float = 10.0) -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _plan(),
        fill_price=100.0,
        fill_quantity=qty,
        filled_at="2026-08-31T15:00:00Z",
        position_id="pos-auto-lc",
    )
    assert pos is not None
    return {
        "id": "pos-auto-lc",
        "account_id": "acc-1",
        "instrument_id": "MSFT",
        "status": pos.status,
        "position_state": pos.to_dict(),
    }


class _Store:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row
        self.updates: list[dict[str, Any]] = []

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        _ = account_id, instrument_id
        if self.row is None or self.row.get("status") == "CLOSED":
            return None
        return self.row

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any]:
        self.updates.append({"status": status, "position_state": position_state})
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
        blob = (self.row or {}).get("position_state") if self.row else None
        current = None
        if isinstance(blob, dict):
            try:
                current = float(blob.get("currentStop"))
            except (TypeError, ValueError):
                current = None
        if current is None or abs(current - float(expected_stop)) > 1e-9:
            return None
        return await self.update_state(
            position_id=position_id, status=status, position_state=position_state
        )


class _FakeSell:
    def __init__(self) -> None:
        self.n = 0

    async def sell(self, **kwargs: Any) -> PaperPositionSellResult:
        self.n += 1
        return PaperPositionSellResult(
            status="trade_executed",
            fill_quantity=float(kwargs["quantity"]),
            fill_price=float(kwargs["price"]),
            transaction_id=f"tx-auto-{self.n}",
        )


async def _seed_open(store: InMemoryLifecycleEventStore, *, pos: str = "pos-auto-lc") -> None:
    append = AppendLifecycleEvent(store)
    result = await append.execute(
        LifecycleEventInput(
            kind="POSITION_OPENED",
            at="2026-08-31T15:00:00.000Z",
            event_id="tx-open-seed",
            position_id=pos,
            account_id="acc-1",
            instrument_id="MSFT",
            decision_id="dec-auto-lc",
            trade_plan_id="tp-auto",
            symbol="MSFT",
            fill_id="tx-open-seed",
            quantity=10,
            price=100,
            venue="PAPER",
            fees=0,
        )
    )
    assert result.ok


@pytest.mark.asyncio
async def test_auto_reduce_t1_writes_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    lc_store = InMemoryLifecycleEventStore()
    await _seed_open(lc_store)
    append = AppendLifecycleEvent(lc_store)

    store = _Store(_open_row())
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=110.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    fake = PositionPolicyDecision(
        verdict="REDUCE",
        reason_code="TARGET_1",
        event=build_position_event("TARGET_1", "2026-08-31T16:00:00Z"),
        quantity=5.0,
        new_stop=None,
        target=110.0,
        risk_impact="reduce",
        policy_id="moderate",
        as_of="2026-08-31T16:00:00Z",
        authorization="policy",
        defer_reason=None,
    )
    monkeypatch.setattr(
        "bolsa_application.execute_position_policy_auto.decide_position_policy",
        lambda *_a, **_k: fake,
    )
    uc = ExecutePositionPolicyAuto(
        protect=PersistPositionFromProtect(store),
        exit_persist=PersistPositionFromExit(store),
        sell=_FakeSell(),
        lifecycle_append=append,
    )
    result = await uc.execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=110.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            session="open",
            as_of="2026-08-31T16:00:00Z",
        )
    )
    assert result.status == "reduced"
    snap = await GetLifecycleSnapshot(append.store).execute("pos-auto-lc")
    kinds = [e["kind"] for e in snap["events"]]
    assert "T1_EXECUTED" in kinds
    assert snap["stage"] in ("t1_executed", "t1_ready", "open") or "T1_EXECUTED" in kinds


@pytest.mark.asyncio
async def test_auto_reduce_t2_writes_t2_executed(monkeypatch: pytest.MonkeyPatch) -> None:
    lc_store = InMemoryLifecycleEventStore()
    await _seed_open(lc_store)
    # Need T1 before T2 in FSM
    append = AppendLifecycleEvent(lc_store)
    t1 = await append.execute(
        LifecycleEventInput(
            kind="T1_EXECUTED",
            at="2026-08-31T15:30:00.000Z",
            event_id="tx-t1-seed",
            position_id="pos-auto-lc",
            account_id="acc-1",
            instrument_id="MSFT",
            decision_id="dec-auto-lc",
            trade_plan_id="tp-auto",
            symbol="MSFT",
            fill_id="tx-t1-seed",
            quantity=5,
            price=110,
            venue="PAPER",
            fees=0,
        )
    )
    assert t1.ok

    store = _Store(_open_row(qty=5.0))
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    # Mark T1 already achieved so remaining is 5
    pos_dict = pos.to_dict()
    pos_dict["target1Achieved"] = True
    pos = position_state_from_dict(pos_dict)
    assert pos is not None

    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=120.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    fake = PositionPolicyDecision(
        verdict="REDUCE",
        reason_code="TARGET_2",
        event=build_position_event("TARGET_2", "2026-08-31T17:00:00Z"),
        quantity=3.0,
        new_stop=None,
        target=120.0,
        risk_impact="reduce",
        policy_id="moderate",
        as_of="2026-08-31T17:00:00Z",
        authorization="policy",
        defer_reason=None,
    )
    monkeypatch.setattr(
        "bolsa_application.execute_position_policy_auto.decide_position_policy",
        lambda *_a, **_k: fake,
    )
    uc = ExecutePositionPolicyAuto(
        protect=PersistPositionFromProtect(store),
        exit_persist=PersistPositionFromExit(store),
        sell=_FakeSell(),
        lifecycle_append=append,
    )
    result = await uc.execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=120.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            session="open",
            as_of="2026-08-31T17:00:00Z",
        )
    )
    assert result.status in ("reduced", "exited")
    snap = await GetLifecycleSnapshot(append.store).execute("pos-auto-lc")
    kinds = [e["kind"] for e in snap["events"]]
    assert "T2_EXECUTED" in kinds


@pytest.mark.asyncio
async def test_auto_exit_writes_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    lc_store = InMemoryLifecycleEventStore()
    await _seed_open(lc_store)
    append = AppendLifecycleEvent(lc_store)

    store = _Store(_open_row())
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    policy = resolve_operating_policy("moderate")
    exit_plan = build_exit_plan_from_position(
        pos, mark_price=94.0, exit_policy=policy.exit
    )
    assert exit_plan is not None
    fake = PositionPolicyDecision(
        verdict="EXIT",
        reason_code="STRUCTURAL_STOP",
        event=build_position_event("STRUCTURAL_STOP", "2026-08-31T18:00:00Z"),
        quantity=10.0,
        new_stop=None,
        target=None,
        risk_impact="exit",
        policy_id="moderate",
        as_of="2026-08-31T18:00:00Z",
        authorization="policy",
        defer_reason=None,
    )
    monkeypatch.setattr(
        "bolsa_application.execute_position_policy_auto.decide_position_policy",
        lambda *_a, **_k: fake,
    )
    uc = ExecutePositionPolicyAuto(
        protect=PersistPositionFromProtect(store),
        exit_persist=PersistPositionFromExit(store),
        sell=_FakeSell(),
        lifecycle_append=append,
    )
    result = await uc.execute(
        ExecutePositionPolicyAutoInput(
            account_id="acc-1",
            instrument_id="MSFT",
            position=pos,
            exit_plan=exit_plan,
            operating_policy=policy,
            mark_price=94.0,
            paper_d_execute=True,
            data_stale=False,
            market_closed=False,
            portfolio_drift=False,
            session="open",
            as_of="2026-08-31T18:00:00Z",
            immediate_risk=True,
            stop_touched=True,
        )
    )
    assert result.status == "exited"
    snap = await GetLifecycleSnapshot(append.store).execute("pos-auto-lc")
    assert snap["stage"] == "closed"
    assert snap["events"][-1]["kind"] == "POSITION_CLOSED"
