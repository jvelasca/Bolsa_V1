"""V1.47 — Golden Paths AUTO-01..10 vía PaperDeskCycle + OperationalContext."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from bolsa_analytics.cognitive.position_revision import revisions_from_raw
from bolsa_analytics.cognitive.position_state import (
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.auto_execute_idempotency import make_position_event_idempotency_key
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    PaperPositionSellResult,
)
from bolsa_application.operational_context import build_test_operational_context
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
    PaperDeskCycleInput,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_protect import PersistPositionFromProtect
from bolsa_application.reconciliation_opening_gate import (
    reconciliation_opening_veto_reason,
)


def _plan(instrument_id: str = "MSFT") -> dict[str, object]:
    return {
        "decisionId": "dec-auto",
        "instrumentId": instrument_id,
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
    }


def _open_row(*, instrument_id: str = "MSFT", qty: float = 10.0) -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _plan(instrument_id),
        fill_price=100.0,
        fill_quantity=qty,
        filled_at="2026-08-31T15:00:00Z",
        position_id=f"pos-{instrument_id}",
    )
    assert pos is not None
    return {
        "id": f"pos-{instrument_id}",
        "account_id": "acc-1",
        "instrument_id": instrument_id,
        "status": pos.status,
        "position_state": pos.to_dict(),
    }


class _DeskStore:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row

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

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any]:
        _ = position_id
        self.row = {**self.row, "status": status, "position_state": position_state}
        return self.row


class _IdempotentSell:
    def __init__(self, fill_quantity: float | None = None) -> None:
        self.execute_count = 0
        self.replay_count = 0
        self.by_key: dict[str, PaperPositionSellResult] = {}
        self.fill_quantity = fill_quantity
        self.calls: list[dict[str, Any]] = []

    async def sell(
        self,
        *,
        account_id: str,
        instrument_id: str,
        quantity: float,
        price: float,
        full_exit: bool,
        idempotency_key: str | None = None,
        **kwargs: Any,
    ) -> PaperPositionSellResult:
        key = (idempotency_key or "").strip() or f"anon-{uuid4().hex[:8]}"
        self.calls.append(
            {
                "quantity": quantity,
                "full_exit": full_exit,
                "idempotency_key": key,
                "account_id": account_id,
                "instrument_id": instrument_id,
                **kwargs,
            }
        )
        if key in self.by_key:
            self.replay_count += 1
            return self.by_key[key]
        self.execute_count += 1
        filled = self.fill_quantity if self.fill_quantity is not None else quantity
        result = PaperPositionSellResult(
            status="trade_executed",
            fill_quantity=filled,
            fill_price=price,
            transaction_id=f"tx-{self.execute_count}",
        )
        self.by_key[key] = result
        return result


def _cycle(
    store: _DeskStore,
    sell: _IdempotentSell,
) -> PaperDeskCycle:
    auto = ExecutePositionPolicyAuto(
        protect=PersistPositionFromProtect(store),
        exit_persist=PersistPositionFromExit(store),
        sell=sell,
    )
    return PaperDeskCycle(
        entry=HonestStubPaperDeskEntry(),
        open_positions=store,
        execute_auto=auto,
    )


@pytest.mark.asyncio
async def test_auto_01_t1_reduce_via_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row(qty=10.0))
    sell = _IdempotentSell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-08-31T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 110.0}),
        )
    )
    assert result.positions[0].status == "reduced"
    assert result.positions[0].next_action == "REDUCIR"
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.remaining_quantity == pytest.approx(7.0)
    assert sell.execute_count == 1


@pytest.mark.asyncio
async def test_auto_02_trail_protect_via_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row(qty=10.0))
    sell = _IdempotentSell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-08-31T16:05:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"MSFT": 105.0}, trail_hint=True, trail_stop=102.0
            ),
        )
    )
    assert result.positions[0].status == "protected"
    assert result.positions[0].next_action == "SUBIR_STOP"
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.current_stop == pytest.approx(102.0)
    revs = revisions_from_raw(pos.to_dict().get("revisions"))
    assert any(r.origin == "trail" for r in revs)
    assert sell.execute_count == 0


@pytest.mark.asyncio
async def test_auto_03_stop_exit_via_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row(qty=10.0))
    sell = _IdempotentSell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-08-31T16:20:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 94.0}),
        )
    )
    assert result.positions[0].status == "exited"
    assert result.positions[0].next_action == "SALIR"
    assert store.row["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_auto_04_same_event_twice_one_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row(qty=10.0))
    sell = _IdempotentSell()
    uc = _cycle(store, sell)
    ctx = build_test_operational_context(marks={"MSFT": 110.0})
    inp = PaperDeskCycleInput(
        account_id="acc-1",
        as_of="2026-08-31T16:00:00Z",
        dry_run=False,
        context=ctx,
    )
    first = await uc.execute(inp)
    second = await uc.execute(inp)
    assert first.positions[0].status == "reduced"
    assert sell.execute_count == 1
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.remaining_quantity == pytest.approx(7.0)
    _ = second


@pytest.mark.asyncio
async def test_auto_05_crash_replay_no_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Order accepted → restart → same idempotency key → no second fill."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row(qty=10.0))
    sell = _IdempotentSell()
    key = make_position_event_idempotency_key(
        position_id="pos-MSFT",
        event_type="T1",
        event_as_of="2026-08-31T16:00:00Z",
        action="reduce",
    )
    accepted = await sell.sell(
        account_id="acc-1",
        instrument_id="MSFT",
        quantity=3.0,
        price=110.0,
        full_exit=False,
        idempotency_key=key,
    )
    assert accepted.status == "trade_executed"
    assert sell.execute_count == 1
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-08-31T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 110.0}),
        )
    )
    assert result.positions[0].status == "reduced"
    assert sell.execute_count == 1
    assert sell.replay_count == 1
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.remaining_quantity == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_auto_06_stale_deny(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row())
    sell = _IdempotentSell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            dry_run=False,
            context=build_test_operational_context(
                marks={"MSFT": 110.0}, permission="STALE"
            ),
        )
    )
    row = result.positions[0]
    assert row.status == "held"
    assert row.reason == "data_stale"
    assert row.next_action == "REVISAR_DATOS_NO_FRESCOS"
    assert sell.execute_count == 0


@pytest.mark.asyncio
async def test_auto_07_drift_deny_reduce_allow_protect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row())
    sell = _IdempotentSell()
    t1 = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 110.0}, drift=True),
        )
    )
    assert t1.positions[0].status == "denied"
    assert "portfolio_drift" in t1.positions[0].permission_reasons
    assert sell.execute_count == 0

    stop = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-08-31T16:20:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 94.0}, drift=True),
        )
    )
    assert stop.positions[0].status == "exited"
    assert sell.execute_count == 1


@pytest.mark.asyncio
async def test_auto_08_market_closed_t1_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row())
    sell = _IdempotentSell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            dry_run=False,
            context=build_test_operational_context(
                marks={"MSFT": 110.0}, session="CLOSED"
            ),
        )
    )
    row = result.positions[0]
    assert row.status == "held"
    assert row.reason == "queue_next_session"
    assert row.next_action == "ESPERAR_APERTURA"
    assert sell.execute_count == 0


@pytest.mark.asyncio
async def test_auto_09_partial_fill_remaining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _DeskStore(_open_row(qty=100.0))
    sell = _IdempotentSell(fill_quantity=40.0)
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-08-31T16:20:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 94.0}),
        )
    )
    assert result.positions[0].status in {"reduced", "exited"}
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.remaining_quantity == pytest.approx(60.0)
    assert store.row["status"] != "CLOSED"


@pytest.mark.asyncio
async def test_auto_10_recon_blocks_entry_allows_protective(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    assert (
        reconciliation_opening_veto_reason(portfolio_recon_status="drift")
        == "reconciliation:portfolio_drift"
    )
    store = _DeskStore(_open_row())
    sell = _IdempotentSell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-08-31T16:20:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 94.0}, drift=True),
        )
    )
    assert result.entry.status == "blocked"
    assert result.entry.reason == "portfolio_drift"
    assert result.positions[0].status == "exited"
