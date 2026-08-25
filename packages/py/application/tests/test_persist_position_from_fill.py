"""P1 — persistir PositionState tras fill (ADR-033 §2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.fill_pending_order import FillPendingOrder
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFill,
    PersistPositionFromFillInput,
)
from bolsa_domain.entities.portfolio import (
    Portfolio,
    PortfolioSummary,
    TradeResult,
    Transaction,
)
from bolsa_infrastructure.database.repositories.pending_order_repository import (
    PendingOrderRecord,
)


def _triggered_plan(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "dec-1",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
    }
    base.update(overrides)
    return base


class _FakeStore:
    def __init__(self) -> None:
        self.by_tx: dict[str, dict[str, Any]] = {}
        self.open_by_instrument: dict[tuple[str, str], dict[str, Any]] = {}
        self.inserts: list[dict[str, Any]] = []

    async def get_by_open_transaction_id(self, open_transaction_id: str) -> dict[str, Any] | None:
        return self.by_tx.get(open_transaction_id)

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        return self.open_by_instrument.get((account_id, instrument_id))

    async def insert(self, **kwargs: Any) -> dict[str, Any]:
        self.inserts.append(kwargs)
        row = {"id": kwargs.get("position_id") or "pos-new", **kwargs}
        self.by_tx[kwargs["open_transaction_id"]] = row
        self.open_by_instrument[(kwargs["account_id"], kwargs["instrument_id"])] = row
        return row


@pytest.mark.asyncio
async def test_persist_triggered_inserts_row() -> None:
    store = _FakeStore()
    uc = PersistPositionFromFill(store)
    row = await uc.persist(
        PersistPositionFromFillInput(
            account_id="acc-1",
            trade_plan=_triggered_plan(),
            fill_price=100.0,
            fill_quantity=10.0,
            filled_at="2026-08-25T15:00:00Z",
            open_transaction_id="tx-1",
            ledger_position_id="led-1",
        )
    )
    assert row is not None
    assert len(store.inserts) == 1
    assert store.inserts[0]["open_transaction_id"] == "tx-1"
    assert store.inserts[0]["status"] == "OPEN"
    assert store.inserts[0]["position_state"]["currentStop"] == 95.0


@pytest.mark.asyncio
async def test_persist_watch_does_not_insert() -> None:
    store = _FakeStore()
    uc = PersistPositionFromFill(store)
    row = await uc.persist(
        PersistPositionFromFillInput(
            account_id="acc-1",
            trade_plan=_triggered_plan(status="WATCH"),
            fill_price=100.0,
            fill_quantity=10.0,
            filled_at=None,
            open_transaction_id="tx-watch",
            ledger_position_id=None,
        )
    )
    assert row is None
    assert store.inserts == []


@pytest.mark.asyncio
async def test_persist_same_transaction_id_is_idempotent() -> None:
    store = _FakeStore()
    uc = PersistPositionFromFill(store)
    first = await uc.persist(
        PersistPositionFromFillInput(
            account_id="acc-1",
            trade_plan=_triggered_plan(),
            fill_price=100.0,
            fill_quantity=10.0,
            filled_at=None,
            open_transaction_id="tx-dup",
            ledger_position_id=None,
        )
    )
    second = await uc.persist(
        PersistPositionFromFillInput(
            account_id="acc-1",
            trade_plan=_triggered_plan(),
            fill_price=101.0,
            fill_quantity=2.0,
            filled_at=None,
            open_transaction_id="tx-dup",
            ledger_position_id=None,
        )
    )
    assert first is second
    assert len(store.inserts) == 1


@dataclass
class _FakeAccount:
    id: str = "acc-1"


@dataclass
class _FakeScope:
    account: _FakeAccount = field(default_factory=_FakeAccount)


class _FakeAccountRepo:
    async def resolve_scope(self, account_id: str | None, portfolio_id: str | None = None) -> _FakeScope:
        return _FakeScope()


class _FakeExecuteTrade:
    def __init__(self, tx_id: str = "tx-po") -> None:
        self.tx_id = tx_id
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> TradeResult:
        self.calls.append(kwargs)
        tx = Transaction(
            id=self.tx_id,
            type="buy",  # type: ignore[arg-type]
            instrument_id="inst-1",
            symbol="SYM",
            quantity=10.0,
            price=100.0,
            total=1000.0,
            executed_at="2026-08-25T15:00:00Z",
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


class _FakePersist:
    def __init__(self) -> None:
        self.calls: list[PersistPositionFromFillInput] = []

    async def persist(self, inp: PersistPositionFromFillInput) -> dict[str, Any]:
        self.calls.append(inp)
        return {"id": "pos-1", "open_transaction_id": inp.open_transaction_id}


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


def _buy_order(*, snapshot: dict[str, Any] | None = None) -> PendingOrderRecord:
    return PendingOrderRecord(
        id="po-1",
        instrument_id="inst-1",
        symbol="SAN",
        side="buy",
        order_type="limit",
        quantity=10.0,
        limit_price=100.0,
        expiry_at=None,
        created_at="2026-08-25T00:00:00Z",
        trade_plan_snapshot=snapshot,
    )


@pytest.mark.asyncio
async def test_confirm_opening_triggered_persists_position() -> None:
    fake_trade = _FakeExecuteTrade("tx-confirm")
    fake_persist = _FakePersist()
    uc = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        position_from_fill=fake_persist,
    )
    result = await uc.execute(
        recommendation_raw={
            "decisionId": "dec-1",
            "instrumentId": "inst-1",
            "action": "recommend_long",
            "suggestedQuantity": 10.0,
            "suggestedPrice": 100.0,
            "tradePlan": _triggered_plan(),
        },
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "executed"
    assert len(fake_persist.calls) == 1
    assert fake_persist.calls[0].open_transaction_id == "tx-confirm"
    assert fake_persist.calls[0].trade_plan is not None
    assert fake_persist.calls[0].trade_plan["status"] == "TRIGGERED"


@pytest.mark.asyncio
async def test_confirm_watch_still_calls_persist_factory_rejects() -> None:
    """Holding nace; factory H2 no crea PositionState (WATCH)."""
    fake_trade = _FakeExecuteTrade("tx-watch")
    store = _FakeStore()
    uc = ConfirmRecommendationIntent(
        execute_trade=fake_trade,
        position_from_fill=PersistPositionFromFill(store),
    )
    result = await uc.execute(
        recommendation_raw={
            "decisionId": "dec-1",
            "instrumentId": "inst-1",
            "action": "recommend_long",
            "suggestedQuantity": 10.0,
            "suggestedPrice": 100.0,
            "tradePlan": _triggered_plan(status="WATCH"),
        },
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "executed"
    assert store.inserts == []


@pytest.mark.asyncio
async def test_fill_pending_with_snapshot_persists() -> None:
    fake_trade = _FakeExecuteTrade("tx-pending")
    fake_persist = _FakePersist()
    repo = _FakePendingRepo(_buy_order(snapshot=_triggered_plan()))
    uc = FillPendingOrder(
        repo,  # type: ignore[arg-type]
        _FakeAccountRepo(),  # type: ignore[arg-type]
        execute_trade=fake_trade,
        position_from_fill=fake_persist,
    )
    result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
    assert result["status"] == "executed"
    assert len(fake_persist.calls) == 1
    assert fake_persist.calls[0].open_transaction_id == "tx-pending"


@pytest.mark.asyncio
async def test_fill_pending_without_snapshot_does_not_persist() -> None:
    fake_trade = _FakeExecuteTrade("tx-bare")
    fake_persist = _FakePersist()
    repo = _FakePendingRepo(_buy_order(snapshot=None))
    uc = FillPendingOrder(
        repo,  # type: ignore[arg-type]
        _FakeAccountRepo(),  # type: ignore[arg-type]
        execute_trade=fake_trade,
        position_from_fill=fake_persist,
    )
    result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
    assert result["status"] == "executed"
    assert fake_persist.calls == []
