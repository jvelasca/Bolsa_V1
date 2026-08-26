"""PA-1 — lazy Confirm/Fill resolve con preferencia account.settings_json.brokerVenue."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent
from bolsa_application.fill_pending_order import FillPendingOrder
from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary, TradeResult, Transaction
from bolsa_infrastructure.database.repositories.pending_order_repository import (
    PendingOrderRecord,
)


class _OkExecute:
    async def execute(self, **kwargs: Any) -> Any:
        return type("Trade", (), {"transaction_id": "tx-ok"})()


def _triggered(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "dec-1",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "quantity": 10.0,
        "entry": 100.0,
        "structuralStop": 95.0,
        "riskAmount": 50.0,
    }
    base.update(overrides)
    return base


def _raw(*, qty: float = 10.0, price: float = 100.0, plan: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "decisionId": "dec-1",
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": qty,
        "suggestedPrice": price,
        "tradePlan": plan,
    }


class _AccountsWithVenue:
    def __init__(self, settings: dict[str, Any] | None) -> None:
        self._settings = settings

    async def resolve_scope(self, account_id: str, portfolio_id: str | None = None) -> Any:
        return type("Scope", (), {"account": type("A", (), {"id": account_id, "active_profile_id": None})()})()

    async def get_settings_json(self, account_id: str) -> dict[str, Any] | None:
        _ = account_id
        return self._settings


@pytest.mark.asyncio
async def test_confirm_lazy_live_from_account_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin adapter inyectado + brokerVenue=live → Xtb (sin bridge → not_wired)."""
    from bolsa_application import broker_venue_runtime as bvr

    bvr.set_runtime_broker_venue(None)

    class _FakeSettings:
        broker_venue = "paper"
        redis_url = ""
        xtb_bridge_url = None
        risk_kill_switch = False

    monkeypatch.setattr(
        "bolsa_infrastructure.config.get_settings",
        lambda: _FakeSettings(),
    )

    async def _redis_miss() -> None:
        return None

    monkeypatch.setattr(bvr, "read_redis_broker_venue", _redis_miss)
    try:
        uc = ConfirmRecommendationIntent(
            execute_trade=_OkExecute(),
            broker_adapter=None,
            accounts=_AccountsWithVenue({"brokerVenue": "live"}),  # type: ignore[arg-type]
        )
        result = await uc.execute(
            recommendation_raw=_raw(plan=_triggered()),
            account_id="acc-1",
            execute=True,
        )
        assert result["trade"]["status"] == "skipped"
        assert result["trade"]["reason"] in ("live_not_wired", "xtb_bridge_not_configured")
        assert result["brokerAdapter"]["venue"] == "LIVE"
        assert result["brokerAdapter"]["adapter"] == "xtb"
        assert "paperOrder" not in result
    finally:
        bvr.set_runtime_broker_venue(None)


@pytest.mark.asyncio
async def test_confirm_lazy_paper_default_without_account_pref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bolsa_application import broker_venue_runtime as bvr

    bvr.set_runtime_broker_venue(None)

    class _FakeSettings:
        broker_venue = "paper"
        redis_url = ""
        xtb_bridge_url = None

    monkeypatch.setattr(
        "bolsa_infrastructure.config.get_settings",
        lambda: _FakeSettings(),
    )

    async def _redis_miss() -> None:
        return None

    monkeypatch.setattr(bvr, "read_redis_broker_venue", _redis_miss)
    try:
        uc = ConfirmRecommendationIntent(
            execute_trade=_OkExecute(),
            broker_adapter=None,
            accounts=_AccountsWithVenue({}),  # type: ignore[arg-type]
        )
        result = await uc.execute(
            recommendation_raw=_raw(plan=_triggered()),
            account_id="acc-1",
            execute=True,
        )
        assert result["brokerAdapter"]["venue"] == "PAPER"
        assert result["brokerAdapter"]["adapter"] == "paper_broker"
        assert result["paperOrder"]["status"] == "FILLED"
    finally:
        bvr.set_runtime_broker_venue(None)


@pytest.mark.asyncio
async def test_confirm_injected_adapter_skips_lazy() -> None:
    """Compat tests: adapter explícito no lee preferencia cuenta."""
    from bolsa_application.broker_adapter import MockBrokerAdapter

    uc = ConfirmRecommendationIntent(
        execute_trade=_OkExecute(),
        broker_adapter=MockBrokerAdapter(),
        accounts=_AccountsWithVenue({"brokerVenue": "paper"}),  # type: ignore[arg-type]
    )
    result = await uc.execute(
        recommendation_raw=_raw(plan=_triggered()),
        account_id="acc-1",
        execute=True,
    )
    assert result["brokerAdapter"]["adapter"] == "mock"
    assert result["brokerAdapter"]["venue"] == "LIVE"


@dataclass
class _FakeAccount:
    id: str = "acc-1"


@dataclass
class _FakeScope:
    account: _FakeAccount = field(default_factory=_FakeAccount)


class _FakeAccountRepo:
    def __init__(self, settings: dict[str, Any] | None = None) -> None:
        self._settings = settings if settings is not None else {}

    async def resolve_scope(self, account_id: str | None, portfolio_id: str | None = None) -> _FakeScope:
        return _FakeScope()

    async def get_settings_json(self, account_id: str) -> dict[str, Any] | None:
        _ = account_id
        return self._settings


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
        return type("Sum", (), {"total_equity": 10_000.0, "positions": []})()


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
async def test_fill_lazy_live_from_account_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bolsa_application import broker_venue_runtime as bvr

    bvr.set_runtime_broker_venue(None)

    class _FakeSettings:
        broker_venue = "paper"
        redis_url = ""
        xtb_bridge_url = None
        risk_kill_switch = False

    monkeypatch.setattr(
        "bolsa_infrastructure.config.get_settings",
        lambda: _FakeSettings(),
    )

    async def _redis_miss() -> None:
        return None

    monkeypatch.setattr(bvr, "read_redis_broker_venue", _redis_miss)
    try:
        fake_trade = _FakeExecuteTrade()
        repo = _FakePendingRepo(_buy_order())
        uc = FillPendingOrder(
            repo,  # type: ignore[arg-type]
            _FakeAccountRepo({"brokerVenue": "live"}),  # type: ignore[arg-type]
            execute_trade=fake_trade,
            broker_adapter=None,
            portfolio_summary=_AllowSummary(),  # type: ignore[arg-type]
        )
        result = await uc.execute("po-1", account_id="acc-1", idempotency_key="k" * 16)
        assert result["status"] == "skipped"
        assert result["reason"] in ("live_not_wired", "xtb_bridge_not_configured")
        assert result["brokerAdapter"]["venue"] == "LIVE"
        assert result["brokerAdapter"]["adapter"] == "xtb"
        assert len(fake_trade.calls) == 0
        assert repo.deleted == []
    finally:
        bvr.set_runtime_broker_venue(None)


def test_update_settings_preserve_keys_include_broker_venue() -> None:
    """Honesty: preserve list must keep brokerVenue with equityMarks/labEvidence."""
    import inspect

    from bolsa_infrastructure.database.repositories import account_repository as ar

    src = inspect.getsource(ar.SqlAlchemyAccountRepository.update_settings)
    assert '"brokerVenue"' in src
    assert '"equityMarks"' in src
    assert '"labEvidence"' in src


@pytest.mark.asyncio
async def test_confirm_memory_overrides_account_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bolsa_application import broker_venue_runtime as bvr

    bvr.set_runtime_broker_venue("paper")

    class _FakeSettings:
        broker_venue = "live"
        redis_url = ""
        xtb_bridge_url = None

    monkeypatch.setattr(
        "bolsa_infrastructure.config.get_settings",
        lambda: _FakeSettings(),
    )
    try:
        uc = ConfirmRecommendationIntent(
            execute_trade=_OkExecute(),
            broker_adapter=None,
            accounts=_AccountsWithVenue({"brokerVenue": "live"}),  # type: ignore[arg-type]
        )
        result = await uc.execute(
            recommendation_raw=_raw(plan=_triggered()),
            account_id="acc-1",
            execute=True,
        )
        assert result["brokerAdapter"]["venue"] == "PAPER"
        assert result["paperOrder"]["status"] == "FILLED"
    finally:
        bvr.set_runtime_broker_venue(None)
