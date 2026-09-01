"""Shared fixtures for V1.53+ Golden Session tests."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

from bolsa_application.estudio_auto_hits import ProposeEstudioAutoOpenings
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    PaperPositionSellResult,
)
from bolsa_application.execution_router import ExecutionRouter
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
)
from bolsa_application.paper_desk_entry import EstudioPaperDeskEntry
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord


def opinion(*, instrument_id: str, stars: int) -> SimpleNamespace:
    return SimpleNamespace(
        instrument_id=instrument_id,
        stance="buy",
        dictamen_stars=stars,
        as_of_bar_date=date(2026, 9, 1),
    )


def golden_plan(
    *,
    instrument_id: str = "A",
    decision_id: str = "tp-A",
    quantity: float = 10.0,
    entry: float = 100.0,
    structural_stop: float = 95.0,
    target1: float = 110.0,
    target2: float = 120.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        trade_plan={
            "decisionId": decision_id,
            "instrumentId": instrument_id,
            "direction": "long",
            "status": "TRIGGERED",
            "quantity": quantity,
            "entry": entry,
            "structuralStop": structural_stop,
            "target1": target1,
            "target2": target2,
            "riskAmount": 50.0,
            "expectedRR": 2.0,
            "executionAllowed": True,
            "whyNot": [],
        },
        last_close=entry,
    )


class FakeEstudioList:
    def __init__(self, ids: list[str]) -> None:
        self.ids = ids

    async def execute(self, list_id: str) -> Any:
        _ = list_id
        return SimpleNamespace(instrument_ids=list(self.ids))


class InnerPropose:
    def __init__(self, by_id: dict[str, object]) -> None:
        self.by_id = by_id

    async def execute(self, **kwargs: Any) -> Any:
        iid = str(kwargs["instrument_id"])
        return self.by_id[iid]


class Instruments:
    async def get_by_id(self, instrument_id: str) -> Any:
        return SimpleNamespace(id=instrument_id, symbol=instrument_id)


class SessionStore:
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


class SeqTrade:
    def __init__(self) -> None:
        self.n = 0

    async def execute(self, **kwargs: Any) -> Any:
        _ = kwargs
        self.n += 1
        tx = type("Tx", (), {"id": f"tx-fill-{self.n}"})()
        return type("TradeResult", (), {"transaction": tx})()


class PaperAccount:
    id = "acc-demo"
    type = "simulated"
    initial_deposit = 10_000.0
    active_profile_id = None


class PaperScope:
    account = PaperAccount()


class PaperAccounts:
    async def resolve_scope(self, account_id: str, portfolio_id: str | None = None):
        _ = account_id, portfolio_id
        return PaperScope()

    async def get_settings_json(self, account_id: str) -> dict[str, Any]:
        _ = account_id
        return {}

    async def merge_settings_json(self, account_id: str, fragment: dict[str, Any]) -> None:
        _ = account_id, fragment


class EmptyBook:
    positions: list[Any] = []
    total_equity = 10_000.0

    async def execute(self, account_id: str | None = None, portfolio_id: str | None = None):
        _ = account_id, portfolio_id
        return self


class Sell:
    def __init__(self) -> None:
        self.execute_count = 0
        self.by_key: dict[str, PaperPositionSellResult] = {}
        self.last_qty: float | None = None

    async def sell(self, **kwargs: Any) -> PaperPositionSellResult:
        key = str(kwargs.get("idempotency_key") or "")
        if key in self.by_key:
            return self.by_key[key]
        self.execute_count += 1
        qty = float(kwargs.get("quantity") or 0)
        self.last_qty = qty
        result = PaperPositionSellResult(
            status="trade_executed",
            fill_quantity=qty,
            fill_price=float(kwargs.get("price") or 0),
            transaction_id=f"tx-exit-{self.execute_count}",
        )
        self.by_key[key] = result
        return result


class AdversarialSell(Sell):
    """Sell stub with transient network skips — no fill id, retryable."""

    def __init__(self) -> None:
        super().__init__()
        self._fail_remaining = 0
        self.network_skip_count = 0

    def fail_next(self, n: int) -> None:
        self._fail_remaining = max(0, int(n))

    async def sell(self, **kwargs: Any) -> PaperPositionSellResult:
        key = str(kwargs.get("idempotency_key") or "")
        if key in self.by_key:
            return self.by_key[key]
        if self._fail_remaining > 0:
            self._fail_remaining -= 1
            self.network_skip_count += 1
            return PaperPositionSellResult(
                status="skipped",
                reason="network_failure",
            )
        return await super().sell(**kwargs)


class Policies:
    def __init__(self, policy: ExecutionPolicyRecord) -> None:
        self._policy = policy

    async def get_policy(self, policy_id: str) -> Any:
        return self._policy if policy_id == self._policy.id else None


class Opinions:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    async def query(self, **kwargs: Any) -> list[Any]:
        _ = kwargs
        return self.rows


def paper_policy() -> ExecutionPolicyRecord:
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


def build_cycles(
    store: SessionStore,
    sell: Sell,
    *,
    quantity: float = 10.0,
    entry: float = 100.0,
) -> tuple[PaperDeskCycle, PaperDeskCycle]:
    policy = paper_policy()
    router = ExecutionRouter(
        policy_repo=Policies(policy),  # type: ignore[arg-type]
        account_repo=PaperAccounts(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=SeqTrade(),  # type: ignore[arg-type]
        portfolio_summary=EmptyBook(),  # type: ignore[arg-type]
        profile_store=None,
        enforce_cognitive_gate=False,
        position_from_fill=PersistPositionFromFill(store),
    )
    propose = ProposeEstudioAutoOpenings(
        Opinions([opinion(instrument_id="A", stars=5)]),
        InnerPropose({"A": golden_plan(quantity=quantity, entry=entry)}),
        instruments=Instruments(),
        router=router,
        policies=Policies(policy),
    )
    entry_tick = EstudioPaperDeskEntry(
        propose=propose,
        estudio_list=FakeEstudioList(["A"]),
        max_candidates=1,
    )
    execute_auto = ExecutePositionPolicyAuto(
        protect=PersistPositionFromProtect(store),
        exit_persist=PersistPositionFromExit(store),
        sell=sell,
    )
    birth_cycle = PaperDeskCycle(
        entry=entry_tick,
        open_positions=store,
        execute_auto=execute_auto,
    )
    position_cycle = PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=store,
        execute_auto=execute_auto,
    )
    return birth_cycle, position_cycle


def assert_identities(row: dict[str, Any], *, candidate_id: str) -> None:
    snap = row["trade_plan_snapshot"]
    assert snap["decisionId"] == "tp-A"
    assert snap["candidateDecisionId"] == candidate_id
    assert snap["decisionId"] != snap["candidateDecisionId"]
    assert row["open_transaction_id"] == snap["fillId"]
    assert snap["fillId"].startswith("tx-fill-")
    assert row["trade_plan_id"] == "tp-A"


def assert_birth_invariants(row: dict[str, Any], *, quantity: float = 10.0, entry: float = 100.0) -> None:
    from bolsa_analytics.cognitive.position_state import position_state_from_dict

    pos = position_state_from_dict(row["position_state"])
    assert pos is not None
    assert pos.quantity == quantity
    assert pos.remaining_quantity == quantity
    assert pos.actual_entry == entry
    assert pos.trade_plan_id == "tp-A"
    assert pos.initial_stop == 95.0
    assert pos.current_stop == 95.0
    assert pos.target1 == 110.0
    assert pos.target2 == 120.0


def assert_journal_chain(row: dict[str, Any], *, exit_fill_id: str) -> None:
    snap = row["trade_plan_snapshot"]
    pos_blob = row["position_state"]
    assert snap["decisionId"] == row["trade_plan_id"]
    assert row["open_transaction_id"] == snap["fillId"]
    assert row["id"] == pos_blob.get("positionId")
    assert exit_fill_id.startswith("tx-exit-")
    assert exit_fill_id != snap["fillId"]
