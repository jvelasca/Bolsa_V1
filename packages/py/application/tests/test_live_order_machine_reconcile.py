"""H7 — reconcile de la máquina ``live_orders`` vs broker-truth (drift only)."""

from __future__ import annotations

import pytest

from bolsa_analytics.cognitive.live_order import (
    LiveOrder,
    build_live_order,
    transition_live_order,
)
from bolsa_application.live_order_machine_reconcile import (
    LiveOrderDrift,
    reconcile_live_order_machine,
)
from bolsa_application.live_order_store import InMemoryLiveOrderStore


class _FakeQuery:
    """Parecido a un query port: devuelve un BrokerOrderQueryResult de control."""

    def __init__(self, result) -> None:
        self.result = result

    async def query_broker_order(self, *, venue_order_id: str):
        _ = venue_order_id
        return self.result


class _FakeProvider:
    """Dict venue_order_id → outcome; 'boom' lanza (simula timeout/erro de query)."""

    def __init__(self, outcomes: dict[str, str]) -> None:
        self.outcomes = outcomes

    async def __call__(self, venue: str, account_id: str, venue_order_id: str):
        o = self.outcomes.get(venue_order_id)
        _ = venue, account_id, venue_order_id
        if o == "boom":
            raise RuntimeError("xtb_timeout")
        from bolsa_application.live_order_query import BrokerOrderQueryResult

        filled = None
        remaining = None
        if o in ("partial", "filled"):
            filled = 50.0 if o == "partial" else 100.0
            remaining = 50.0 if o == "partial" else 0.0
        return _FakeQuery(
            BrokerOrderQueryResult(
                outcome=o,  # type: ignore[arg-type]
                venue_order_id=venue_order_id,
                filled_quantity=filled,
                remaining_quantity=remaining,
                reason=None,
            )
        )


def _submitted_with_venue(*, order_id: str, vid: str) -> LiveOrder:
    o = build_live_order(
        order_id=order_id, instrument_id="inst-1", side="buy",
        quantity=100.0, account_id="acc-1",
    )
    return transition_live_order(
        transition_live_order(o, "SUBMITTING"),
        "SUBMITTED",
        venue_order_id=vid,
    )


def _working(*, order_id: str, vid: str) -> LiveOrder:
    return transition_live_order(
        _submitted_with_venue(order_id=order_id, vid=vid),
        "WORKING",
    )


def _partial(*, order_id: str, vid: str) -> LiveOrder:
    return transition_live_order(
        _working(order_id=order_id, vid=vid),
        "PARTIAL",
        filled_quantity=50.0,
    )


def _cancel_requested(*, order_id: str, vid: str) -> LiveOrder:
    return transition_live_order(
        _working(order_id=order_id, vid=vid),
        "CANCEL_REQUESTED",
    )


async def _store(*orders: LiveOrder) -> InMemoryLiveOrderStore:
    s = InMemoryLiveOrderStore()
    for o in orders:
        await s.put(o)
    return s


@pytest.mark.asyncio
async def test_no_drift_when_broker_matches_machine() -> None:
    store = await _store(_working(order_id="w1", vid="v1"))
    prov = _FakeProvider({"v1": "working"})
    report = await reconcile_live_order_machine(store, query_provider=prov, limit=10)
    assert report.checked == 1
    assert report.drifts == []


@pytest.mark.asyncio
async def test_cancel_broker_side_drift() -> None:
    store = await _store(_working(order_id="w2", vid="v2"))
    prov = _FakeProvider({"v2": "cancelled"})
    report = await reconcile_live_order_machine(store, query_provider=prov, limit=10)
    assert any(d.kind == "cancel_broker_side" for d in report.drifts)
    drift = report.drifts[0]
    assert drift.order_id == "w2"
    assert drift.machine_state == "WORKING"
    assert drift.broker_state == "cancelled"


@pytest.mark.asyncio
async def test_fill_unseen_drift_only_no_heal() -> None:
    store = await _store(_working(order_id="w3", vid="v3"))
    prov = _FakeProvider({"v3": "partial"})
    report = await reconcile_live_order_machine(store, query_provider=prov, limit=10)
    assert any(d.kind == "fill_unseen" for d in report.drifts)
    drift = next(d for d in report.drifts if d.kind == "fill_unseen")
    assert drift.suggested == "PARTIAL"
    assert drift.broker_filled == 50.0
    # no auto-heal: la fila NO se mutó hacia PARTIAL en el store
    after = await store.get("w3")
    assert after is not None and after.status == "WORKING"


@pytest.mark.asyncio
async def test_match_partial_local_no_drift_when_partial() -> None:
    store = await _store(_partial(order_id="p1", vid="v4"))
    prov = _FakeProvider({"v4": "partial"})
    report = await reconcile_live_order_machine(store, query_provider=prov, limit=10)
    assert report.checked == 1
    assert report.drifts == []


@pytest.mark.asyncio
async def test_query_unavailable_reported_as_drift() -> None:
    store = await _store(_working(order_id="q1", vid="boom"))
    prov = _FakeProvider({"boom": "boom"})
    report = await reconcile_live_order_machine(store, query_provider=prov, limit=10)
    assert any(d.kind == "query_unavailable" for d in report.drifts)


@pytest.mark.asyncio
async def test_cancel_requested_local_and_broker_working_is_state_mismatch() -> None:
    store = await _store(_cancel_requested(order_id="c1", vid="v5"))
    prov = _FakeProvider({"v5": "working"})
    report = await reconcile_live_order_machine(store, query_provider=prov, limit=10)
    # intención local no coincide con el venue (sigue working) → mismatch.
    assert any(d.kind == "state_mismatch" for d in report.drifts)
    assert all(isinstance(d, LiveOrderDrift) for d in report.drifts)


@pytest.mark.asyncio
async def test_summary_counts_kinds() -> None:
    store = await _store(
        _working(order_id="a", vid="va"),
        _working(order_id="b", vid="boom"),
    )
    prov = _FakeProvider({"va": "cancelled", "boom": "boom"})
    report = await reconcile_live_order_machine(store, query_provider=prov, limit=10)
    s = report.summary()
    assert s["checked"] == 2
    assert s["drifts"] == 2
    assert s["kinds"].get("cancel_broker_side") == 1
    assert s["kinds"].get("query_unavailable") == 1
