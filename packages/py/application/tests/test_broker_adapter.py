"""IBrokerAdapter — paper wrap + mock LIVE + XTB (submitted ≠ fill; filled→ledger)."""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.broker_adapter import (
    MockBrokerAdapter,
    PaperBrokerAdapter,
    XtbBrokerAdapter,
)
from bolsa_market.providers import XtbBridgeOrderResult


class _OkExecute:
    async def execute(self, **kwargs: Any) -> Any:
        return type("Trade", (), {"transaction_id": "tx-ba"})()


class _BoomExecute:
    async def execute(self, **kwargs: Any) -> Any:
        raise RuntimeError("ledger timeout")


class _SpyExecute:
    def __init__(self) -> None:
        self.calls = 0
        self.kwargs: dict[str, Any] | None = None

    async def execute(self, **kwargs: Any) -> Any:
        self.calls += 1
        self.kwargs = kwargs
        return type("Trade", (), {"transaction_id": "tx-spy"})()


class _FakeXtb:
    def __init__(self, result: XtbBridgeOrderResult) -> None:
        self.result = result
        self.calls = 0

    async def submit_order(self, **kwargs: Any) -> XtbBridgeOrderResult:
        self.calls += 1
        _ = kwargs
        return self.result


@pytest.mark.asyncio
async def test_paper_adapter_ok_fills() -> None:
    adapter = PaperBrokerAdapter(_OkExecute())
    result = await adapter.submit(
        instrument_id="inst-1",
        side="buy",
        quantity=10.0,
        price=100.0,
        account_id="acc-1",
        idempotency_key="idem-1",
        intent_id="intent-1",
    )
    assert result.venue == "PAPER"
    assert result.adapter == "paper_broker"
    assert result.status == "executed"
    assert result.paper_order is not None
    assert result.paper_order.status == "FILLED"
    assert result.paper_receipt is not None
    receipt = result.receipt()
    assert receipt.venue == "PAPER"
    assert receipt.fill_status == "executed"


@pytest.mark.asyncio
async def test_paper_adapter_exception_unknown() -> None:
    adapter = PaperBrokerAdapter(_BoomExecute())
    result = await adapter.submit(
        instrument_id="inst-1",
        side="sell",
        quantity=5.0,
        price=50.0,
        account_id="acc-1",
        idempotency_key="idem-2",
    )
    assert result.status == "unknown"
    assert result.paper_order is not None
    assert result.paper_order.status == "CREATED"
    assert result.receipt().fill_status == "unknown"


@pytest.mark.asyncio
async def test_mock_adapter_never_calls_execute() -> None:
    spy = _SpyExecute()
    adapter = MockBrokerAdapter()
    result = await adapter.submit(
        instrument_id="inst-1",
        side="buy",
        quantity=1.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="idem-3",
    )
    assert spy.calls == 0
    assert result.venue == "LIVE"
    assert result.adapter == "mock"
    assert result.status == "not_wired"
    assert result.fill_status == "not_wired"
    assert result.paper_order is None
    assert result.trade is None
    assert result.reason == "live_not_wired"
    assert result.receipt().fill_status != "executed"


@pytest.mark.asyncio
async def test_xtb_without_bridge_is_not_wired() -> None:
    adapter = XtbBrokerAdapter()
    result = await adapter.submit(
        instrument_id="inst-1",
        side="buy",
        quantity=1.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="idem-xtb-0",
    )
    assert result.adapter == "xtb"
    assert result.venue == "LIVE"
    assert result.status == "not_wired"
    assert result.reason == "xtb_bridge_not_configured"
    assert result.trade is None


@pytest.mark.asyncio
async def test_xtb_rejected_never_touches_ledger() -> None:
    spy = _SpyExecute()
    fake = _FakeXtb(XtbBridgeOrderResult(status="rejected", reason="live_orders_disabled"))
    adapter = XtbBrokerAdapter(client=fake, execute_trade=spy)
    result = await adapter.submit(
        instrument_id="inst-1",
        side="buy",
        quantity=2.0,
        price=20.0,
        account_id="acc-1",
        idempotency_key="idem-xtb-1",
    )
    assert spy.calls == 0
    assert fake.calls == 1
    assert result.status == "rejected"
    assert result.fill_status == "rejected"
    assert result.reason == "live_orders_disabled"
    assert result.trade is None
    assert result.paper_order is None
    assert result.receipt().fill_status != "executed"


@pytest.mark.asyncio
async def test_xtb_submitted_is_not_executed_fill() -> None:
    spy = _SpyExecute()
    fake = _FakeXtb(
        XtbBridgeOrderResult(
            status="submitted",
            reason=None,
            venue_order_id="xtb-ord-1",
        )
    )
    adapter = XtbBrokerAdapter(client=fake, execute_trade=spy)
    result = await adapter.submit(
        instrument_id="inst-1",
        side="sell",
        quantity=3.0,
        price=30.0,
        account_id="acc-1",
        idempotency_key="idem-xtb-2",
    )
    assert spy.calls == 0
    assert result.status == "submitted"
    assert result.fill_status == "submitted"
    assert result.reason == "live_submitted_no_fill"
    assert result.venue_order_id == "xtb-ord-1"
    assert result.trade is None
    assert result.receipt().fill_status != "executed"


@pytest.mark.asyncio
async def test_xtb_filled_executes_ledger() -> None:
    spy = _SpyExecute()
    fake = _FakeXtb(
        XtbBridgeOrderResult(
            status="filled",
            reason="live_filled",
            venue_order_id="xtb-fill-1",
        )
    )
    adapter = XtbBrokerAdapter(client=fake, execute_trade=spy)
    result = await adapter.submit(
        instrument_id="inst-1",
        side="buy",
        quantity=4.0,
        price=40.0,
        account_id="acc-1",
        idempotency_key="idem-xtb-fill",
    )
    assert spy.calls == 1
    assert spy.kwargs == {
        "instrument_id": "inst-1",
        "trade_type": "buy",
        "quantity": 4.0,
        "price": 40.0,
        "account_id": "acc-1",
        "idempotency_key": "idem-xtb-fill",
    }
    assert result.status == "executed"
    assert result.fill_status == "executed"
    assert result.transaction_id == "tx-spy"
    assert result.trade is not None
    assert result.venue_order_id == "xtb-fill-1"
    assert result.paper_order is None
    assert result.receipt().fill_status == "executed"


@pytest.mark.asyncio
async def test_xtb_filled_without_execute_is_unknown() -> None:
    fake = _FakeXtb(
        XtbBridgeOrderResult(
            status="filled",
            reason="live_filled",
            venue_order_id="xtb-fill-2",
        )
    )
    adapter = XtbBrokerAdapter(client=fake)
    result = await adapter.submit(
        instrument_id="inst-1",
        side="buy",
        quantity=1.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="idem-xtb-nowire",
    )
    assert result.status == "unknown"
    assert result.fill_status == "unknown"
    assert result.reason == "xtb_execute_not_wired"
    assert result.trade is None
    assert result.transaction_id is None
    assert result.venue_order_id == "xtb-fill-2"


def test_normalize_broker_venue() -> None:
    from bolsa_application.broker_venue_runtime import normalize_broker_venue

    assert normalize_broker_venue(None) == "paper"
    assert normalize_broker_venue("") == "paper"
    assert normalize_broker_venue("PAPER") == "paper"
    assert normalize_broker_venue("live") == "live"
    assert normalize_broker_venue("LIVE") == "live"
    assert normalize_broker_venue("xtb") == "paper"


def test_effective_broker_venue_runtime_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from bolsa_application import broker_venue_runtime as bvr

    bvr.set_runtime_broker_venue(None)

    class _FakeSettings:
        broker_venue = "paper"

    monkeypatch.setattr(
        "bolsa_infrastructure.config.get_settings",
        lambda: _FakeSettings(),
    )
    try:
        assert bvr.effective_broker_venue() == "paper"

        bvr.set_runtime_broker_venue("live")
        assert bvr.effective_broker_venue() == "live"
        assert bvr.get_runtime_broker_venue() == "live"

        bvr.set_runtime_broker_venue(None)
        assert bvr.effective_broker_venue() == "paper"
        assert bvr.get_runtime_broker_venue() is None
    finally:
        bvr.set_runtime_broker_venue(None)


@pytest.mark.asyncio
async def test_effective_broker_venue_async_redis_coalesce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bolsa_application import broker_venue_runtime as bvr

    bvr.set_runtime_broker_venue(None)

    class _FakeSettings:
        broker_venue = "paper"
        redis_url = "redis://test"

    monkeypatch.setattr(
        "bolsa_infrastructure.config.get_settings",
        lambda: _FakeSettings(),
    )

    async def _redis_live() -> str:
        return "live"

    monkeypatch.setattr(bvr, "read_redis_broker_venue", _redis_live)
    try:
        assert await bvr.effective_broker_venue_async() == "live"

        bvr.set_runtime_broker_venue("paper")
        assert await bvr.effective_broker_venue_async() == "paper"
    finally:
        bvr.set_runtime_broker_venue(None)


def test_account_broker_venue_from_settings() -> None:
    from bolsa_application.broker_venue_runtime import account_broker_venue_from_settings

    assert account_broker_venue_from_settings(None) is None
    assert account_broker_venue_from_settings({}) is None
    assert account_broker_venue_from_settings({"brokerVenue": 1}) is None
    assert account_broker_venue_from_settings({"brokerVenue": "live"}) == "live"
    assert account_broker_venue_from_settings({"brokerVenue": "paper"}) == "paper"


@pytest.mark.asyncio
async def test_effective_broker_venue_async_account_pref_after_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PA-1: memory ?? redis ?? account ?? env ?? paper."""
    from bolsa_application import broker_venue_runtime as bvr

    bvr.set_runtime_broker_venue(None)

    class _FakeSettings:
        broker_venue = "paper"
        redis_url = ""

    monkeypatch.setattr(
        "bolsa_infrastructure.config.get_settings",
        lambda: _FakeSettings(),
    )

    async def _redis_miss() -> None:
        return None

    monkeypatch.setattr(bvr, "read_redis_broker_venue", _redis_miss)
    try:
        assert await bvr.effective_broker_venue_async(account_venue="live") == "live"
        assert await bvr.effective_broker_venue_async(account_venue=None) == "paper"

        # Redis gana sobre account
        async def _redis_paper() -> str:
            return "paper"

        monkeypatch.setattr(bvr, "read_redis_broker_venue", _redis_paper)
        assert await bvr.effective_broker_venue_async(account_venue="live") == "paper"

        # Memory gana sobre todo
        bvr.set_runtime_broker_venue("live")
        assert await bvr.effective_broker_venue_async(account_venue="paper") == "live"
    finally:
        bvr.set_runtime_broker_venue(None)


def test_effective_broker_venue_sync_account_pref(monkeypatch: pytest.MonkeyPatch) -> None:
    from bolsa_application import broker_venue_runtime as bvr

    bvr.set_runtime_broker_venue(None)

    class _FakeSettings:
        broker_venue = "paper"

    monkeypatch.setattr(
        "bolsa_infrastructure.config.get_settings",
        lambda: _FakeSettings(),
    )
    try:
        assert bvr.effective_broker_venue(account_venue="live") == "live"
        assert bvr.effective_broker_venue() == "paper"
        bvr.set_runtime_broker_venue("paper")
        assert bvr.effective_broker_venue(account_venue="live") == "paper"
    finally:
        bvr.set_runtime_broker_venue(None)


@pytest.mark.asyncio
async def test_set_broker_venue_writes_memory_and_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bolsa_application import broker_venue_runtime as bvr

    bvr.set_runtime_broker_venue(None)
    wrote: list[str] = []

    async def _write(venue: str) -> bool:
        wrote.append(venue)
        return True

    monkeypatch.setattr(bvr, "write_redis_broker_venue", _write)
    try:
        out = await bvr.set_broker_venue("live")
        assert out["venue"] == "live"
        assert out["memory"] is True
        assert out["redis"] is True
        assert wrote == ["live"]
        assert bvr.get_runtime_broker_venue() == "live"
    finally:
        bvr.set_runtime_broker_venue(None)


def test_resolve_broker_adapter_paper_vs_live() -> None:
    from bolsa_application.broker_adapter import resolve_broker_adapter

    paper = resolve_broker_adapter(_OkExecute(), venue="paper")
    assert isinstance(paper, PaperBrokerAdapter)

    live = resolve_broker_adapter(_OkExecute(), venue="live", bridge_url=None)
    assert isinstance(live, XtbBrokerAdapter)
