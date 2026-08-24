"""FillPendingOrder — pending_orders pasan por check_opening (ADR-031)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary, TradeResult, Transaction
from bolsa_infrastructure.database.repositories.pending_order_repository import (
    PendingOrderRecord,
)

from bolsa_application.fill_pending_order import FillPendingOrder


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
