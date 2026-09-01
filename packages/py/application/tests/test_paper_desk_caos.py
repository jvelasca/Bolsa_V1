"""V1.48 CAOS — event identity, crash, recon unavailable, concurrent TRAIL."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from bolsa_analytics.cognitive.position_revision import revisions_from_raw
from bolsa_analytics.cognitive.position_state import (
    build_position_state_from_fill,
    position_state_from_dict,
)
from bolsa_application.execute_position_policy_auto import (
    ExecutePositionPolicyAuto,
    PaperPositionSellResult,
)
from bolsa_application.operational_context import (
    ExecutionSnapshot,
    FakeMarketDataPort,
    MarketSnapshot,
    OperationalContextBuilder,
    build_test_operational_context,
)
from bolsa_application.paper_desk_cycle import (
    HonestStubPaperDeskEntry,
    PaperDeskCycle,
    PaperDeskCycleInput,
)
from bolsa_application.persist_position_from_exit import PersistPositionFromExit
from bolsa_application.persist_position_from_protect import (
    PersistPositionFromProtect,
    PersistPositionFromProtectInput,
)
from bolsa_application.position_event_log import events_from_blob


def _plan() -> dict[str, object]:
    return {
        "decisionId": "dec-caos",
        "instrumentId": "MSFT",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 110.0,
        "target2": 120.0,
    }


def _open_row(*, qty: float = 10.0, stop: float = 95.0) -> dict[str, Any]:
    pos = build_position_state_from_fill(
        {**_plan(), "structuralStop": stop},
        fill_price=100.0,
        fill_quantity=qty,
        filled_at="2026-09-01T08:00:00Z",
        position_id="pos-MSFT",
    )
    assert pos is not None
    return {
        "id": "pos-MSFT",
        "account_id": "acc-1",
        "instrument_id": "MSFT",
        "status": pos.status,
        "position_state": pos.to_dict(),
    }


class _CasStore:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row
        self._lock = asyncio.Lock()
        self.cas_attempts = 0
        self.cas_wins = 0

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
        return dict(self.row)

    async def update_state(
        self,
        *,
        position_id: str,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._lock:
            self.row = {**self.row, "id": position_id, "status": status, "position_state": position_state}
            return self.row

    async def compare_and_swap_stop(
        self,
        *,
        position_id: str,
        expected_stop: float,
        status: str,
        position_state: dict[str, Any],
    ) -> dict[str, Any] | None:
        async with self._lock:
            self.cas_attempts += 1
            blob = self.row.get("position_state")
            current = float(blob.get("currentStop")) if isinstance(blob, dict) else None
            if current is None or abs(current - float(expected_stop)) > 1e-9:
                return None
            self.cas_wins += 1
            self.row = {
                **self.row,
                "id": position_id,
                "status": status,
                "position_state": position_state,
            }
            return self.row


class _IdempotentSell:
    def __init__(self) -> None:
        self.execute_count = 0
        self.by_key: dict[str, PaperPositionSellResult] = {}

    async def sell(self, **kwargs: Any) -> PaperPositionSellResult:
        key = str(kwargs.get("idempotency_key") or "")
        if key in self.by_key:
            return self.by_key[key]
        self.execute_count += 1
        result = PaperPositionSellResult(
            status="trade_executed",
            fill_quantity=float(kwargs.get("quantity") or 0),
            fill_price=float(kwargs.get("price") or 0),
            transaction_id=f"tx-{self.execute_count}",
        )
        self.by_key[key] = result
        return result


def _cycle(store: _CasStore, sell: _IdempotentSell) -> PaperDeskCycle:
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
async def test_caos_01_same_cycle_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row())
    sell = _IdempotentSell()
    uc = _cycle(store, sell)
    inp = PaperDeskCycleInput(
        account_id="acc-1",
        as_of="2026-09-01T16:00:00Z",
        dry_run=False,
        context=build_test_operational_context(marks={"MSFT": 110.0}),
    )
    await uc.execute(inp)
    await uc.execute(inp)
    assert sell.execute_count == 1


@pytest.mark.asyncio
async def test_caos_02_same_trail_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row(stop=95.0))
    uc = PersistPositionFromProtect(store)
    inp = PersistPositionFromProtectInput(
        account_id="acc-1",
        instrument_id="MSFT",
        suggested_stop=102.0,
        origin="trail",
        applied_at="2026-09-01T10:00:00Z",
    )
    await uc.persist(inp)
    await uc.persist(inp)
    revs = revisions_from_raw(store.row["position_state"].get("revisions"))
    trail = [r for r in revs if r.origin == "trail"]
    assert len(trail) == 1
    events = events_from_blob(store.row["position_state"])
    assert len([e for e in events if e.event_type == "TRAIL"]) == 1


@pytest.mark.asyncio
async def test_caos_03_trail_then_trail_same_day(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row(stop=95.0))
    uc = PersistPositionFromProtect(store)
    await uc.persist(
        PersistPositionFromProtectInput(
            account_id="acc-1",
            instrument_id="MSFT",
            suggested_stop=102.0,
            origin="trail",
            applied_at="2026-09-01T10:00:00Z",
        )
    )
    await uc.persist(
        PersistPositionFromProtectInput(
            account_id="acc-1",
            instrument_id="MSFT",
            suggested_stop=105.0,
            origin="trail",
            applied_at="2026-09-01T11:00:00Z",
        )
    )
    revs = revisions_from_raw(store.row["position_state"].get("revisions"))
    trail = [r for r in revs if r.origin == "trail"]
    assert len(trail) == 2
    events = [e for e in events_from_blob(store.row["position_state"]) if e.event_type == "TRAIL"]
    assert len(events) == 2
    assert events[0].event_id != events[1].event_id
    assert events[0].sequence == 1
    assert events[1].sequence == 2


@pytest.mark.asyncio
async def test_caos_04_crash_after_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row())
    sell = _IdempotentSell()
    claimed = await PersistPositionFromProtect(store).claim_sell_event(
        account_id="acc-1",
        instrument_id="MSFT",
        event_type="T1",
        action="reduce",
        as_of="2026-09-01T16:00:00Z",
        quantity=3.0,
    )
    assert claimed is not None
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 110.0}),
        )
    )
    assert result.positions[0].status == "reduced"
    assert sell.execute_count == 1
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.remaining_quantity == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_caos_05_crash_after_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row())
    sell = _IdempotentSell()
    claimed = await PersistPositionFromProtect(store).claim_sell_event(
        account_id="acc-1",
        instrument_id="MSFT",
        event_type="T1",
        action="reduce",
        as_of="2026-09-01T16:00:00Z",
        quantity=3.0,
    )
    assert claimed is not None
    await sell.sell(
        account_id="acc-1",
        instrument_id="MSFT",
        quantity=3.0,
        price=110.0,
        full_exit=False,
        idempotency_key=claimed.event_id,
    )
    assert sell.execute_count == 1
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 110.0}),
        )
    )
    assert result.positions[0].status == "reduced"
    assert sell.execute_count == 1


@pytest.mark.asyncio
async def test_caos_06_partial_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row(qty=100.0))

    class _Partial(_IdempotentSell):
        async def sell(self, **kwargs: Any) -> PaperPositionSellResult:
            key = str(kwargs.get("idempotency_key") or "")
            if key in self.by_key:
                return self.by_key[key]
            self.execute_count += 1
            result = PaperPositionSellResult(
                status="trade_executed",
                fill_quantity=40.0,
                fill_price=float(kwargs.get("price") or 0),
                transaction_id=f"tx-{self.execute_count}",
            )
            self.by_key[key] = result
            return result

    sell = _Partial()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T16:20:00Z",
            dry_run=False,
            context=build_test_operational_context(marks={"MSFT": 94.0}),
        )
    )
    assert result.positions[0].status in {"reduced", "exited"}
    pos = position_state_from_dict(store.row["position_state"])
    assert pos is not None
    assert pos.remaining_quantity == pytest.approx(60.0)


@pytest.mark.asyncio
async def test_caos_07_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row())
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
    assert result.positions[0].status == "held"
    assert result.positions[0].next_action == "REVISAR_DATOS_NO_FRESCOS"
    assert sell.execute_count == 0


@pytest.mark.asyncio
async def test_caos_08_recon_unavailable_not_drift() -> None:
    class _Boom:
        async def portfolio_recon_status(self, account_id: str) -> str:
            _ = account_id
            raise RuntimeError("down")

    ctx = await OperationalContextBuilder(
        FakeMarketDataPort(
            {
                "MSFT": MarketSnapshot(
                    instrument_id="MSFT", last_price=110.0, permission="FRESH"
                )
            }
        ),
        _Boom(),
    ).build("acc-1", ["MSFT"])
    assert ctx.portfolio.recon_status == "unavailable"
    assert ctx.portfolio.drift is False


@pytest.mark.asyncio
async def test_caos_08_entry_blocked_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row())
    sell = _IdempotentSell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T16:20:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"MSFT": 94.0}, recon_status="unavailable"
            ),
        )
    )
    assert result.entry.status == "blocked"
    assert result.entry.reason == "recon_unavailable"
    assert "recon_unavailable" in result.notes
    assert result.positions[0].status == "exited"


@pytest.mark.asyncio
async def test_caos_09_market_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row())
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
    assert result.positions[0].next_action == "ESPERAR_APERTURA"
    assert sell.execute_count == 0


@pytest.mark.asyncio
async def test_caos_10_two_workers_same_trail() -> None:
    store = _CasStore(_open_row(stop=95.0))
    uc = PersistPositionFromProtect(store)
    inp = PersistPositionFromProtectInput(
        account_id="acc-1",
        instrument_id="MSFT",
        suggested_stop=102.0,
        origin="trail",
        applied_at="2026-09-01T10:00:00Z",
    )
    await asyncio.gather(uc.persist(inp), uc.persist(inp))
    revs = revisions_from_raw(store.row["position_state"].get("revisions"))
    trail = [r for r in revs if r.origin == "trail"]
    assert len(trail) == 1
    assert store.cas_wins >= 1
    events = [e for e in events_from_blob(store.row["position_state"]) if e.event_type == "TRAIL"]
    assert len(events) == 1


@pytest.mark.asyncio
async def test_intent_unresolved_skips_second_sell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row())
    sell = _IdempotentSell()
    claimed = await PersistPositionFromProtect(store).claim_sell_event(
        account_id="acc-1",
        instrument_id="MSFT",
        event_type="T1",
        action="reduce",
        as_of="2026-09-01T16:00:00Z",
        quantity=3.0,
    )
    assert claimed is not None
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(
                marks={"MSFT": 110.0},
                execution=ExecutionSnapshot(
                    existing_intent_keys=frozenset({claimed.event_id}),
                    unresolved_executions=(claimed.event_id,),
                ),
            ),
        )
    )
    assert result.positions[0].status == "sell_skipped"
    assert result.positions[0].reason == "intent_unresolved"
    assert sell.execute_count == 0


@pytest.mark.asyncio
async def test_caos_crash_before_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Crash tras decidir y antes de reclamar evento: el ciclo recupera una sola vez."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row())
    sell = _IdempotentSell()
    assert events_from_blob(store.row["position_state"]) == []
    uc = _cycle(store, sell)
    inp = PaperDeskCycleInput(
        account_id="acc-1",
        as_of="2026-09-01T16:00:00Z",
        dry_run=False,
        context=build_test_operational_context(marks={"MSFT": 110.0}),
    )
    await uc.execute(inp)
    assert sell.execute_count == 1
    events = events_from_blob(store.row["position_state"])
    assert len(events) == 1
    await uc.execute(inp)
    assert sell.execute_count == 1
    assert len(events_from_blob(store.row["position_state"])) == 1


@pytest.mark.asyncio
async def test_caos_missing_mark_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _CasStore(_open_row())
    sell = _IdempotentSell()
    result = await _cycle(store, sell).execute(
        PaperDeskCycleInput(
            account_id="acc-1",
            as_of="2026-09-01T16:00:00Z",
            dry_run=False,
            context=build_test_operational_context(missing=("MSFT",)),
        )
    )
    assert result.positions[0].status == "denied"
    assert result.positions[0].reason == "data_unavailable"
    assert sell.execute_count == 0


@pytest.mark.asyncio
async def test_caos_kill_switch_denies_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    """H2: AUTO + kill switch DENY incluso protector; no sell ni trail."""
    from bolsa_application.risk_runtime import set_runtime_kill_switch_memory

    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    set_runtime_kill_switch_memory(True)
    try:
        store = _CasStore(_open_row())
        sell = _IdempotentSell()
        result = await _cycle(store, sell).execute(
            PaperDeskCycleInput(
                account_id="acc-1",
                as_of="2026-09-01T16:20:00Z",
                dry_run=False,
                context=build_test_operational_context(marks={"MSFT": 94.0}),
            )
        )
        assert result.positions[0].status == "denied"
        assert "kill_switch" in (result.positions[0].reason or "")
        assert sell.execute_count == 0

        store_t = _CasStore(_open_row(stop=95.0))
        sell_t = _IdempotentSell()
        trail = await _cycle(store_t, sell_t).execute(
            PaperDeskCycleInput(
                account_id="acc-1",
                as_of="2026-09-01T10:00:00Z",
                dry_run=False,
                context=build_test_operational_context(
                    marks={"MSFT": 112.0},
                    trail_hint=True,
                    trail_stop=102.0,
                ),
            )
        )
        assert trail.positions[0].status == "denied"
        assert "kill_switch" in (trail.positions[0].reason or "")
        revs = revisions_from_raw(store_t.row["position_state"].get("revisions"))
        assert not any(r.origin == "trail" for r in revs)
        assert sell_t.execute_count == 0
    finally:
        set_runtime_kill_switch_memory(False)
