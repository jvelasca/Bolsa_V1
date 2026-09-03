"""OR-5 — Broker execution scenario suite A–L + retry + crash (ADR-035).

Certificación spine (paper/mock). Sin live accepted · sin OR-6 · sin mass sim.
"""

from __future__ import annotations

from typing import Any, Literal

import pytest
from bolsa_analytics.cognitive.exit_plan import build_exit_plan_from_position
from bolsa_analytics.cognitive.order_intent import stable_intent_id_from_decision
from bolsa_analytics.cognitive.paper_order import stable_order_id_from_decision
from bolsa_analytics.cognitive.position_state import build_position_state_from_fill
from bolsa_analytics.cognitive.submit_intent import record_submit_intent
from bolsa_domain.entities.portfolio import (
    Portfolio,
    PortfolioSummary,
    TradeResult,
    Transaction,
)

from bolsa_application.broker_adapter import MockBrokerAdapter
from bolsa_application.confirm_recommendation import (
    ConfirmRecommendationIntent,
    confirm_leg_idempotency_key,
)
from bolsa_application.execute_gated_portfolio_trade import ExecuteGatedPortfolioTrade
from bolsa_application.persist_position_from_exit import (
    LAST_EXIT_TRANSACTION_KEY,
    PersistPositionFromExit,
    PersistPositionFromExitInput,
)
from bolsa_application.persist_position_from_fill import PersistPositionFromFill
from bolsa_application.reconciliation_opening_gate import (
    reconciliation_opening_veto_reason,
)
from bolsa_application.submit_intent_store import InMemorySubmitIntentStore


def _triggered(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decisionId": "dec-or5",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "entry": 100.0,
        "structuralStop": 95.0,
        "target1": 105.0,
        "target2": 110.0,
        "quantity": 10.0,
        "riskAmount": 50.0,
    }
    base.update(overrides)
    return base


def _opening_raw(*, decision_id: str = "dec-or5", qty: float = 10.0) -> dict[str, Any]:
    return {
        "decisionId": decision_id,
        "instrumentId": "inst-1",
        "action": "recommend_long",
        "suggestedQuantity": qty,
        "suggestedPrice": 100.0,
        "tradePlan": _triggered(decisionId=decision_id, quantity=qty),
    }


def _protect_raw(*, suggested_stop: float, current_stop: float = 95.0) -> dict[str, Any]:
    return {
        "decisionId": "dec-or5-protect",
        "instrumentId": "inst-1",
        "action": "wait",
        "suggestedQuantity": 10.0,
        "suggestedPrice": suggested_stop,
        "decisionPackage": {
            "operativaIntent": "protect",
            "suggestedStop": suggested_stop,
            "currentStop": current_stop,
            "direction": "long",
            "stopOverrideRequired": False,
        },
    }


class _OkExecute:
    def __init__(self, tx_id: str = "tx-or5") -> None:
        self.tx_id = tx_id
        self.execute_calls = 0

    async def find_existing_by_idempotency(self, **kwargs: Any) -> Any | None:
        return None

    async def execute(self, **kwargs: Any) -> Any:
        self.execute_calls += 1
        return type("Trade", (), {"transaction_id": self.tx_id})()


class _BoomExecute:
    async def execute(self, **kwargs: Any) -> Any:
        raise RuntimeError("ledger timeout")


class _IdempotentPeekExecute:
    """OR-1-shaped: first fill stored; peek returns it; no second execute."""

    def __init__(self) -> None:
        self.execute_calls = 0
        self._by_key: dict[str, Any] = {}

    async def find_existing_by_idempotency(self, **kwargs: Any) -> Any | None:
        return self._by_key.get(str(kwargs.get("idempotency_key") or ""))

    async def execute(self, **kwargs: Any) -> Any:
        self.execute_calls += 1
        key = str(kwargs.get("idempotency_key") or "")
        trade = type("Trade", (), {"transaction_id": f"tx-{key}"})()
        self._by_key[key] = trade
        return trade


class _BoomPersist:
    async def persist(self, inp: Any) -> dict[str, Any]:
        raise RuntimeError("persist boom")


class _FakeProtect:
    def __init__(self, *, apply: bool = True) -> None:
        self.apply = apply
        self.calls: list[Any] = []

    async def get_open(self, account_id: str, instrument_id: str) -> dict[str, Any]:
        pos = build_position_state_from_fill(
            _triggered(),
            fill_price=100.0,
            fill_quantity=10.0,
            filled_at="2026-08-26T00:00:00Z",
            position_id="pos-or5",
        )
        assert pos is not None
        return {"id": "pos-or5", "position_state": pos.to_dict()}

    async def persist(self, inp: Any) -> dict[str, Any] | None:
        self.calls.append(inp)
        if not self.apply:
            return None
        return {"id": "pos-or5"}


class _HttpExecuteTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> TradeResult:
        self.calls.append(kwargs)
        side = str(kwargs.get("trade_type", "buy")).lower()
        tx_type: Literal["buy", "sell"] = "sell" if side == "sell" else "buy"
        tx = Transaction(
            id="tx-http-or5",
            type=tx_type,
            instrument_id=kwargs["instrument_id"],
            symbol="SYM",
            quantity=float(kwargs["quantity"]),
            price=float(kwargs["price"]),
            total=float(kwargs["quantity"]) * float(kwargs["price"]),
            executed_at="2026-08-26T00:00:00Z",
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


class _FillStore:
    def __init__(self) -> None:
        self.inserts: list[dict[str, Any]] = []
        self.open_by_instrument: dict[tuple[str, str], dict[str, Any]] = {}

    async def get_by_open_transaction_id(self, open_transaction_id: str) -> None:
        return None

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        return self.open_by_instrument.get((account_id, instrument_id))

    async def insert(self, **kwargs: Any) -> dict[str, Any]:
        row = {"id": kwargs.get("position_id") or "pos-http", **kwargs}
        self.open_by_instrument[(kwargs["account_id"], kwargs["instrument_id"])] = row
        self.inserts.append(kwargs)
        return row


class _ExitStore:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row
        self.updates: list[dict[str, Any]] = []

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
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
        self.updates.append(
            {"position_id": position_id, "status": status, "position_state": position_state}
        )
        self.row = {**self.row, "status": status, "position_state": position_state}
        return self.row


def _open_row() -> dict[str, Any]:
    pos = build_position_state_from_fill(
        _triggered(),
        fill_price=100.0,
        fill_quantity=10.0,
        filled_at="2026-08-26T00:00:00Z",
        position_id="pos-or5",
    )
    assert pos is not None
    return {
        "id": "pos-or5",
        "account_id": "acc-1",
        "instrument_id": "inst-1",
        "status": "OPEN",
        "position_state": pos.to_dict(),
    }


class _CountingAdapter:
    def __init__(self) -> None:
        self.submit_calls = 0

    async def submit(self, **kwargs: Any) -> Any:
        self.submit_calls += 1
        raise AssertionError("adapter.submit must not run on OR-5 crash recovery")


# ── A–L ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_or5_a_entrada_normal_semi_executed() -> None:
    uc = ConfirmRecommendationIntent(execute_trade=_OkExecute())
    result = await uc.execute(
        recommendation_raw=_opening_raw(),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "executed"
    assert result["executionRecord"]["outcome"] == "executed"
    assert result["intent"]["status"] == "executed"


@pytest.mark.asyncio
async def test_or5_b_manual_http_human_manual_origin() -> None:
    trade = _HttpExecuteTrade()
    fill_store = _FillStore()
    uc = ExecuteGatedPortfolioTrade(
        trade,  # type: ignore[arg-type]
        portfolio_summary=_AllowSummary(),
        position_from_fill=PersistPositionFromFill(fill_store),
    )
    await uc.execute(
        instrument_id="inst-1",
        trade_type="buy",
        quantity=2.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="k" * 16,
    )
    assert len(fill_store.inserts) == 1
    assert fill_store.inserts[0]["birth_override_reason"] == "human_manual"


@pytest.mark.asyncio
async def test_or5_c_sell_parcial_remaining() -> None:
    store = _ExitStore(_open_row())
    row = await PersistPositionFromExit(store).persist(
        PersistPositionFromExitInput(
            account_id="acc-1",
            instrument_id="inst-1",
            fill_quantity=4.0,
            fill_price=105.0,
            exit_transaction_id="tx-partial",
            filled_at="2026-08-26T01:00:00Z",
        )
    )
    assert row is not None
    assert store.updates[0]["status"] == "PARTIAL"
    assert store.updates[0]["position_state"]["remainingQuantity"] == 6.0
    assert store.updates[0]["position_state"][LAST_EXIT_TRANSACTION_KEY] == "tx-partial"


@pytest.mark.asyncio
async def test_or5_d_sell_total_closes() -> None:
    store = _ExitStore(_open_row())
    row = await PersistPositionFromExit(store).persist(
        PersistPositionFromExitInput(
            account_id="acc-1",
            instrument_id="inst-1",
            fill_quantity=10.0,
            fill_price=95.0,
            exit_transaction_id="tx-full",
            filled_at="2026-08-26T01:00:00Z",
        )
    )
    assert row is not None
    assert store.updates[0]["status"] == "CLOSED"
    assert store.updates[0]["position_state"]["remainingQuantity"] == 0.0


@pytest.mark.asyncio
async def test_or5_e_timeout_paper_is_unknown() -> None:
    uc = ConfirmRecommendationIntent(execute_trade=_BoomExecute())
    result = await uc.execute(
        recommendation_raw=_opening_raw(),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "unknown"
    assert "ledger timeout" in result["trade"]["reason"]
    assert result["executionRecord"]["outcome"] == "unknown"
    assert result["executionRecord"]["outcome"] != "error"
    assert result["executionRecord"]["outcome"] != "not_executed"


@pytest.mark.asyncio
async def test_or5_f_persist_fail_post_fill_keeps_executed() -> None:
    uc = ConfirmRecommendationIntent(
        execute_trade=_OkExecute("tx-persist-fail"),
        position_from_fill=_BoomPersist(),
    )
    result = await uc.execute(
        recommendation_raw=_opening_raw(),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "executed"
    assert result["positionPersist"]["status"] == "error"
    assert "persist boom" in result["positionPersist"]["reason"]
    assert result["executionRecord"]["outcome"] == "executed"


@pytest.mark.asyncio
async def test_or5_g_protect_ok() -> None:
    protect = _FakeProtect(apply=True)
    uc = ConfirmRecommendationIntent(
        execute_trade=_OkExecute("tx-should-not-run"),
        position_from_protect=protect,
    )
    result = await uc.execute(
        recommendation_raw=_protect_raw(suggested_stop=98.0),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "protect_applied"
    assert result["positionPersist"]["status"] == "applied"
    assert len(protect.calls) == 1


@pytest.mark.asyncio
async def test_or5_h_protect_fail_not_protect_applied() -> None:
    protect = _FakeProtect(apply=False)
    uc = ConfirmRecommendationIntent(
        execute_trade=_OkExecute("tx-should-not-run"),
        position_from_protect=protect,
    )
    result = await uc.execute(
        recommendation_raw=_protect_raw(suggested_stop=90.0, current_stop=95.0),
        account_id="acc-1",
        execute=True,
    )
    assert result["trade"]["status"] == "skipped"
    assert result["trade"]["reason"] == "stop_not_applied"
    assert result["positionPersist"]["status"] == "skipped"


def test_or5_i_t1_reduce() -> None:
    pos = build_position_state_from_fill(
        _triggered(),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-t1",
    )
    assert pos is not None
    plan = build_exit_plan_from_position(pos, mark_price=105.0, exit_plan_id="ex-t1")
    assert plan is not None
    assert plan.primary_reason == "TARGET_1"
    assert plan.suggested_action == "reduce"
    assert plan.suggested_qty == 5.0


def test_or5_j_t2_no_replay_subsumes_t1() -> None:
    pos = build_position_state_from_fill(
        _triggered(),
        fill_price=100.0,
        fill_quantity=10.0,
        position_id="pos-t2",
    )
    assert pos is not None
    plan = build_exit_plan_from_position(pos, mark_price=110.0, exit_plan_id="ex-t2")
    assert plan is not None
    assert plan.primary_reason == "TARGET_2"
    assert "TARGET_2" in plan.reasons
    assert "TARGET_1" not in plan.reasons
    assert plan.suggested_action == "full_exit"
    assert plan.suggested_qty == 10.0


def test_or5_k_recon_drift_vetoes_opening() -> None:
    assert (
        reconciliation_opening_veto_reason(portfolio_recon_status="drift")
        == "reconciliation:portfolio_drift"
    )


def test_or5_l_broker_unavailable_and_mock_not_wired() -> None:
    assert (
        reconciliation_opening_veto_reason(
            live_recon_status="unavailable",
            broker_venue="live",
            require=True,
        )
        == "reconciliation:live_unavailable"
    )
    assert (
        reconciliation_opening_veto_reason(
            live_recon_status="unavailable",
            broker_venue="paper",
            require=True,
        )
        is None
    )


@pytest.mark.asyncio
async def test_or5_l_mock_live_adapter_not_wired() -> None:
    adapter = MockBrokerAdapter()
    result = await adapter.submit(
        instrument_id="inst-1",
        side="buy",
        quantity=1.0,
        price=10.0,
        account_id="acc-1",
        idempotency_key="idem-or5-l",
        intent_id="intent-or5-l",
    )
    assert result.status == "not_wired"
    assert result.reason == "live_not_wired"


# ── retry (OR-1) · crash (OR-2) ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_or5_retry_confirm_short_circuits_without_second_execute() -> None:
    fake = _IdempotentPeekExecute()
    decision_id = "DEC-OR5-RETRY"
    leg_key = confirm_leg_idempotency_key(decision_id, "recommend_long", "buy")
    uc = ConfirmRecommendationIntent(execute_trade=fake)
    raw = _opening_raw(decision_id=decision_id, qty=5.0)
    first = await uc.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    second = await uc.execute(recommendation_raw=raw, account_id="acc-1", execute=True)
    assert fake.execute_calls == 1
    assert first["trade"]["status"] == "executed"
    assert second["trade"]["status"] == "executed"
    assert second["trade"].get("idempotentReplay") is True
    assert first["trade"]["transactionId"] == second["trade"]["transactionId"]
    assert first["intent"]["intentId"] == stable_intent_id_from_decision(decision_id)
    assert first["paperOrder"]["orderId"] == stable_order_id_from_decision(leg_key)


@pytest.mark.asyncio
async def test_or5_crash_recovery_unknown_without_repost() -> None:
    store = InMemorySubmitIntentStore()
    decision_id = "DEC-OR5-CRASH"
    leg_key = confirm_leg_idempotency_key(decision_id, "recommend_long", "buy")
    recorded = record_submit_intent(
        decision_id=leg_key,
        intent_id=stable_intent_id_from_decision(leg_key),
        order_id=stable_order_id_from_decision(leg_key),
        account_id="acc-1",
    )
    await store.put(recorded)
    adapter = _CountingAdapter()
    uc = ConfirmRecommendationIntent(
        execute_trade=_OkExecute(),
        broker_adapter=adapter,  # type: ignore[arg-type]
        submit_intent_store=store,
    )
    result = await uc.execute(
        recommendation_raw=_opening_raw(decision_id=decision_id),
        account_id="acc-1",
        execute=True,
    )
    assert adapter.submit_calls == 0
    assert result["trade"]["status"] == "unknown"
    assert result["trade"]["crashRecovery"] is True
    assert result["executionRecord"]["outcome"] == "unknown"
    assert result["paperOrder"]["status"] == "UNKNOWN"
