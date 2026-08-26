"""FillPendingOrder — pending_orders pasan por check_opening (ADR-031)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from bolsa_application.fill_pending_order import FillPendingOrder
from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary, TradeResult, Transaction
from bolsa_infrastructure.database.repositories.pending_order_repository import (
    PendingOrderRecord,
)


@dataclass
class _FakeAccount:
    id: str = "acc-1"


@dataclass
class _FakeScope:
    account: _FakeAccount = field(default_factory=_FakeAccount)


class _FakeAccountRepo:
    async def resolve_scope(self, account_id: str | None, portfolio_id: str | None = None) -> _FakeScope:
        return _FakeScope()


class _FakePendingRepo:
    def __init__(self, order: PendingOrderRecord) -> None:
        self.order = order
        self.deleted: list[str] = []

    async def get_by_id(self, order_id: str, account_id: str | None = None) -> PendingOrderRecord | None:
        if order_id == self.order.id:
            return self.order
        return None

    async def delete(self, order_id: str, account_id: str | None = None) -> bool:
        self.deleted.append(order_id)
        return True


class _FakeExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> TradeResult:
        self.calls.append(kwargs)
        tx = Transaction(
            id="tx-po",
            type="buy",  # type: ignore[arg-type]
            instrument_id="inst-1",
            symbol="SYM",
            quantity=1.0,
            price=10.0,
            total=10.0,
            executed_at="2026-08-24T00:00:00Z",
        )
        return TradeResult(
            transaction=tx,
            summary=PortfolioSummary(
                portfolio=Portfolio(id="pf", name="p", currency="EUR", cash=0.0),
                positions=[],
                total_market_value=0.0,
                total_cost=0.0,
                total_unrealized_pnl=0.0,
                total_equity=0.0,
            ),
        )


class _AllowSummary:
    async def execute(self, *, account_id: str) -> Any:
        return type(
            "Sum",
            (),
            {
                "total_equity": 10_000.0,
                "positions": [],
            },
        )()


class _VetoSummary:
    async def execute(self, *, account_id: str) -> Any:
        raise RuntimeError("summary down")


def _buy_order() -> PendingOrderRecord:
    return PendingOrderRecord(
        id="po-1",
        instrument_id="inst-1",
        symbol="SAN",
        side="buy",
        order_type="limit",
        quantity=10.0,
        limit_price=5.0,
        expiry_at=None,
        created_at="2026-08-24T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_fill_pending_buy_executes_when_gate_allows() -> None:
    fake_trade = _FakeExecuteTrade()
    repo = _FakePendingRepo(_buy_order())
    uc = FillPendingOrder(
        repo,  # type: ignore[arg-type]
        _FakeAccountRepo(),  # type: ignore[arg-type]
        execute_trade=fake_trade,
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
    )
    result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
    assert result["status"] == "executed"
    assert len(fake_trade.calls) == 1
    assert repo.deleted == ["po-1"]
    order = result["paperOrder"]
    assert order["status"] == "FILLED"
    assert order["orderId"] == "po-1"
    assert order["venue"] == "PAPER"
    assert order["transactionId"] == "tx-po"
    assert order["status"] != "CREATED"
    broker = result["paperBroker"]
    assert broker["venue"] == "PAPER"
    assert broker["adapter"] == "paper_broker"
    assert broker["fillStatus"] == "executed"
    adapter = result["brokerAdapter"]
    assert adapter["venue"] == "PAPER"
    assert adapter["adapter"] == "paper_broker"
    assert adapter["fillStatus"] == "executed"


@pytest.mark.asyncio
async def test_fill_pending_buy_risk_veto_no_trade() -> None:
    fake_trade = _FakeExecuteTrade()
    repo = _FakePendingRepo(_buy_order())
    uc = FillPendingOrder(
        repo,  # type: ignore[arg-type]
        _FakeAccountRepo(),  # type: ignore[arg-type]
        execute_trade=fake_trade,
        portfolio_summary=_VetoSummary(),  # type: ignore[arg-type]
    )
    result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
    assert result["status"] == "rejected_by_gate"
    assert len(fake_trade.calls) == 0
    assert repo.deleted == []
    assert "paperOrder" not in result
    assert "paperBroker" not in result
    assert "brokerAdapter" not in result


@pytest.mark.asyncio
async def test_fill_pending_execute_boom_unknown_keeps_order() -> None:
    class _Boom:
        async def execute(self, **kwargs: Any) -> Any:
            raise RuntimeError("ledger timeout")

    repo = _FakePendingRepo(_buy_order())
    uc = FillPendingOrder(
        repo,  # type: ignore[arg-type]
        _FakeAccountRepo(),  # type: ignore[arg-type]
        execute_trade=_Boom(),
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
    )
    result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
    assert result["status"] == "unknown"
    assert result["paperOrder"]["status"] == "CREATED"
    assert result["paperBroker"]["fillStatus"] == "unknown"
    assert result["brokerAdapter"]["fillStatus"] == "unknown"
    assert repo.deleted == []


@pytest.mark.asyncio
async def test_fill_pending_mock_live_does_not_fill() -> None:
    from bolsa_application.broker_adapter import MockBrokerAdapter

    fake_trade = _FakeExecuteTrade()
    repo = _FakePendingRepo(_buy_order())
    uc = FillPendingOrder(
        repo,  # type: ignore[arg-type]
        _FakeAccountRepo(),  # type: ignore[arg-type]
        execute_trade=fake_trade,
        broker_adapter=MockBrokerAdapter(),
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
    )
    result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
    assert result["status"] == "skipped"
    assert result["reason"] == "live_not_wired"
    assert result["brokerAdapter"]["venue"] == "LIVE"
    assert result["brokerAdapter"]["adapter"] == "mock"
    assert result["brokerAdapter"]["fillStatus"] == "not_wired"
    assert "paperOrder" not in result
    assert len(fake_trade.calls) == 0
    assert repo.deleted == []


@pytest.mark.asyncio
async def test_fill_pending_xtb_rejected_keeps_order() -> None:
    from bolsa_application.broker_adapter import XtbBrokerAdapter
    from bolsa_market.providers import XtbBridgeOrderResult

    class _FakeXtb:
        async def submit_order(self, **kwargs: object) -> XtbBridgeOrderResult:
            _ = kwargs
            return XtbBridgeOrderResult(status="rejected", reason="live_orders_disabled")

    fake_trade = _FakeExecuteTrade()
    repo = _FakePendingRepo(_buy_order())
    uc = FillPendingOrder(
        repo,  # type: ignore[arg-type]
        _FakeAccountRepo(),  # type: ignore[arg-type]
        execute_trade=fake_trade,
        broker_adapter=XtbBrokerAdapter(client=_FakeXtb()),
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
    )
    result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
    assert result["status"] == "skipped"
    assert result["reason"] == "live_orders_disabled"
    assert result["brokerAdapter"]["adapter"] == "xtb"
    assert result["brokerAdapter"]["fillStatus"] == "rejected"
    assert len(fake_trade.calls) == 0
    assert repo.deleted == []


@pytest.mark.asyncio
async def test_fill_pending_xtb_submitted_keeps_order() -> None:
    from bolsa_application.broker_adapter import XtbBrokerAdapter
    from bolsa_market.providers import XtbBridgeOrderResult

    class _FakeXtb:
        async def submit_order(self, **kwargs: object) -> XtbBridgeOrderResult:
            _ = kwargs
            return XtbBridgeOrderResult(
                status="submitted",
                venue_order_id="xtb-sub-1",
            )

    fake_trade = _FakeExecuteTrade()
    repo = _FakePendingRepo(_buy_order())
    uc = FillPendingOrder(
        repo,  # type: ignore[arg-type]
        _FakeAccountRepo(),  # type: ignore[arg-type]
        execute_trade=fake_trade,
        broker_adapter=XtbBrokerAdapter(client=_FakeXtb(), execute_trade=fake_trade),
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
    )
    result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
    assert result["status"] == "unknown"
    assert result["reason"] == "live_submitted_no_fill"
    assert result["venueOrderId"] == "xtb-sub-1"
    assert result["brokerAdapter"]["fillStatus"] == "submitted"
    assert len(fake_trade.calls) == 0
    assert repo.deleted == []


@pytest.mark.asyncio
async def test_fill_pending_xtb_filled_executes_and_deletes() -> None:
    from bolsa_application.broker_adapter import XtbBrokerAdapter
    from bolsa_market.providers import XtbBridgeOrderResult

    class _FakeXtb:
        async def submit_order(self, **kwargs: object) -> XtbBridgeOrderResult:
            _ = kwargs
            return XtbBridgeOrderResult(
                status="filled",
                reason="live_filled",
                venue_order_id="xtb-fill-po",
            )

    fake_trade = _FakeExecuteTrade()
    repo = _FakePendingRepo(_buy_order())
    uc = FillPendingOrder(
        repo,  # type: ignore[arg-type]
        _FakeAccountRepo(),  # type: ignore[arg-type]
        execute_trade=fake_trade,
        broker_adapter=XtbBrokerAdapter(client=_FakeXtb(), execute_trade=fake_trade),
        portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
    )
    result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
    assert result["status"] == "executed"
    assert result["transactionId"] == "tx-po"
    assert result["brokerAdapter"]["venue"] == "LIVE"
    assert result["brokerAdapter"]["adapter"] == "xtb"
    assert result["brokerAdapter"]["fillStatus"] == "executed"
    assert len(fake_trade.calls) == 1
    assert repo.deleted == ["po-1"]
    assert "paperOrder" not in result
