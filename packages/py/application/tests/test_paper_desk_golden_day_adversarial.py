"""V1.58 GP-GOLDEN-DAY-ADV-01 — chained adversarial PAPER day + GP-V158-STOP-CLOSED."""

from __future__ import annotations

from typing import Any

import pytest
from paper_desk_golden_fixtures import (
    AdversarialSell,
    SessionStore,
    assert_birth_invariants,
    assert_identities,
    assert_journal_chain,
    build_cycles,
    golden_plan,
)

from bolsa_analytics.cognitive.operational_invariants import (
    closed_remaining_zero,
    executed_leg_has_fill,
    qty_non_negative,
)
from bolsa_analytics.cognitive.position_state import (
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    PaperPositionSellResult,
)
from bolsa_application.operational_context import (
    build_test_operational_context,
    resolve_position_operating_state,
)
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
    PaperDeskCycleInput,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFill,
    PersistPositionFromFillInput,
)
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect


def _plan_a() -> dict[str, object]:
    return {
        "decisionId": "tp-A",
        "instrumentId": "A",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
        "quantity": 10.0,
        "riskAmount": 50.0,
        "initialRiskR": 5.0,
    }


def _open_row_a(*, qty: float = 10.0) -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _plan_a(),
        fill_price=100.0,
        fill_quantity=qty,
        filled_at="2026-09-01T09:00:00Z",
        position_id="pos-A",
    )
    assert pos is not None
    snap = golden_plan().trade_plan
    return {
        "id": "pos-A",
        "account_id": "acc-demo",
        "instrument_id": "A",
        "status": pos.status,
        "trade_plan_id": "tp-A",
        "open_transaction_id": "tx-fill-1",
        "trade_plan_snapshot": {
            **snap,
            "fillId": "tx-fill-1",
            "candidateDecisionId": "tp-A",
        },
        "position_state": pos.to_dict(),
    }


class _DeskStore:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row
        self.inserts = [row]

    async def list_open(self, account_id: str) -> list[dict[str, Any]]:
        _ = account_id
        if self.row.get("status") == "CLOSED":
            return []
        return [self.row]

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        _ = account_id
        if self.row.get("instrument_id") != instrument_id:
            return None
        if self.row.get("status") == "CLOSED":
            return None
        return self.row

    async def get_by_open_transaction_id(
        self, open_transaction_id: str
    ) -> dict[str, Any] | None:
        if self.row.get("open_transaction_id") == open_transaction_id:
            return self.row
        return None

    async def insert(self, **kwargs: Any) -> dict[str, Any]:
        row = dict(kwargs)
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
        blob = self.row.get("position_state")
        current = float(blob.get("currentStop")) if isinstance(blob, dict) else None
        if current is None or abs(current - float(expected_stop)) > 1e-9:
            return None
        return await self.update_state(
            position_id=position_id, status=status, position_state=position_state
        )


class _IdempotentSell:
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


def _desk_cycle(store: _DeskStore, sell: _IdempotentSell) -> PaperDeskCycle:
    execute_auto = ExecutePositionPolicyAuto(
        protect=PersistPositionFromProtect(store),
        exit_persist=PersistPositionFromExit(store),
        sell=sell,
    )
    return PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=store,
        execute_auto=execute_auto,
    )


def _assert_inv_at_close(pos: object) -> None:
    assert qty_non_negative(pos.quantity) is True
    assert closed_remaining_zero(status=pos.status, remaining=pos.remaining_quantity)
    t1 = pos.target1_leg
    t2 = pos.target2_leg
    assert t1 is not None
    assert t2 is not None
    assert executed_leg_has_fill(t1.status, t1.fill_id)
    assert executed_leg_has_fill(t2.status, t2.fill_id)
    assert t1.fill_id != t2.fill_id
    assert t1.fill_id != "tx-fill-1"
    assert t2.fill_id != "tx-fill-1"


@pytest.mark.asyncio
async def test_gp_golden_day_adv_01_chained_adversarial_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-GOLDEN-DAY-ADV-01: BUY → dup fill → T1 → crash replay → TRAIL → T2 net fail → retry → dup evt → EXIT → recon."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-demo")

    store = SessionStore()
    sell = AdversarialSell()
    birth_cycle, position_cycle = build_cycles(store, sell)

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
    row = store.row
    assert row is not None
    candidate_id = open_.entry.candidates[0].decision_id
    assert_identities(row, candidate_id=candidate_id)
    assert_birth_invariants(row)
    open_tx = row["open_transaction_id"]

    # 09:01 — duplicate opening fill (idempotent persist)
    dup = await PersistPositionFromFill(store).persist(
        PersistPositionFromFillInput(
            account_id="acc-demo",
            trade_plan=row["trade_plan_snapshot"],
            fill_price=100.0,
            fill_quantity=10.0,
            filled_at="2026-09-01T09:00:00Z",
            open_transaction_id=open_tx,
            ledger_position_id=row["id"],
        )
    )
    assert dup is row
    assert len(store.inserts) == 1

    # 11:00 — T1
    t1 = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T11:00:00Z",
            dry_run=False,
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 110.0}),
        )
    )
    assert t1.positions[0].status == "reduced"
    t1_sells = sell.execute_count
    assert t1_sells == 1
    pos_t1 = position_state_from_dict((store.row or {})["position_state"])
    assert pos_t1 is not None
    assert pos_t1.remaining_quantity == pytest.approx(7.0)
    assert pos_t1.target1_leg is not None
    assert pos_t1.target1_leg.status == "executed"

    # 11:05 — crash: new cycle on same store, replay T1 tick
    _, crash_cycle = build_cycles(store, sell)
    crash_t1 = await crash_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T11:05:00Z",
            dry_run=False,
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 110.0}),
        )
    )
    assert sell.execute_count == t1_sells
    assert crash_t1.positions[0].status in {"reduced", "held", "sell_skipped"}

    # 12:00 — TRAIL
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

    # 13:00 — T2 + one network skip
    sell.fail_next(1)
    t2_fail = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T13:00:00Z",
            dry_run=False,
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 120.0}),
        )
    )
    assert sell.network_skip_count == 1
    assert sell.execute_count == t1_sells
    assert t2_fail.positions[0].status == "sell_skipped"
    pos_pre_retry = position_state_from_dict((store.row or {})["position_state"])
    assert pos_pre_retry is not None
    assert pos_pre_retry.target2_leg is not None
    assert pos_pre_retry.target2_leg.status != "failed"

    # 13:05 — T2 retry → fill
    t2_ok = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T13:05:00Z",
            dry_run=False,
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 120.0}),
        )
    )
    assert t2_ok.positions[0].status == "reduced"
    assert sell.execute_count == t1_sells + 1
    pos_t2 = position_state_from_dict((store.row or {})["position_state"])
    assert pos_t2 is not None
    assert pos_t2.target2_leg is not None
    assert pos_t2.target2_leg.status == "executed"
    assert pos_t2.remaining_quantity == pytest.approx(4.9)

    # 13:10 — duplicate event (same tick twice)
    dup_evt = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T13:10:00Z",
            dry_run=False,
            template_id="moderate",
            context=build_test_operational_context(marks={"A": 120.0}),
        )
    )
    assert sell.execute_count == t1_sells + 1
    assert dup_evt.positions[0].status in {"reduced", "held", "sell_skipped"}

    # 16:00 — EXIT (structural stop)
    closed = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"A": 94.0}),
        )
    )
    assert closed.positions[0].status == "exited"
    assert sell.execute_count == t1_sells + 2

    pos = position_state_from_dict((store.row or {})["position_state"])
    assert pos is not None
    assert pos.status == "CLOSED"
    assert pos.remaining_quantity == 0

    # 16:05 — recon clean (inverse GP-SESSION-10 drift; closed → no open rows)
    recon = await position_cycle.execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T16:05:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 94.0}, recon_status="clean"
            ),
        )
    )
    assert len(recon.positions) == 0
    op = resolve_position_operating_state(
        position_status=pos.status,
        remaining_quantity=pos.remaining_quantity,
        quantity=pos.quantity,
        has_trail_revision=False,
        has_protect_revision=False,
        recon_status="clean",
    )
    assert op == "CLOSED"

    assert store.row is not None
    assert store.row["status"] == "CLOSED"
    assert pos.status == "CLOSED"
    assert pos.remaining_quantity == 0
    assert pos.quantity == 10.0
    assert len(store.inserts) == 1
    assert store.row["open_transaction_id"] == open_tx
    assert_journal_chain(store.row, exit_fill_id="tx-exit-3")
    _assert_inv_at_close(pos)
    tx_ids = {r.transaction_id for r in sell.by_key.values()}
    assert "tx-exit-1" in tx_ids
    assert "tx-exit-2" in tx_ids
    assert "tx-exit-3" in tx_ids


@pytest.mark.asyncio
async def test_gp_v158_stop_closed_structural_stop_sells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-V158-STOP-CLOSED: STRUCTURAL_STOP + session CLOSED → sell (PAPER last close)."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row_a())
    sell = _IdempotentSell()
    result = await _desk_cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 94.0}, session="CLOSED"
            ),
        )
    )
    assert result.positions[0].status == "exited"
    assert sell.execute_count == 1
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.status == "CLOSED"
    assert pos.remaining_quantity == 0


@pytest.mark.asyncio
async def test_gp_v158_stop_closed_t1_still_queues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GP-V158-STOP-CLOSED contrast: T1 + CLOSED → queue_next_session, 0 sells."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row_a())
    sell = _IdempotentSell()
    result = await _desk_cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-demo",
            as_of="2026-09-01T11:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"A": 110.0}, session="CLOSED"
            ),
        )
    )
    row = result.positions[0]
    assert row.status == "held"
    assert row.reason == "queue_next_session"
    assert row.next_action == "ESPERAR_APERTURA"
    assert sell.execute_count == 0
