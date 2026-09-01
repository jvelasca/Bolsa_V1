from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.execution_router import ExecutionRouter, signal_kind_to_trade_type
from bolsa_application.paper_auto_http_gate import (
    PAPER_AUTO_ENV_BLOCKED,
    PaperAutoEnvBlockedError,
)
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord
from bolsa_domain.platform_kernel import validate_execution_mode


class _FakePolicyRepo:
    def __init__(self, policy: ExecutionPolicyRecord) -> None:
        self._policy = policy

    async def get_policy(self, policy_id: str) -> ExecutionPolicyRecord | None:
        if self._policy.id == policy_id:
            return self._policy
        return None


def _paper_auto_policy() -> ExecutionPolicyRecord:
    return ExecutionPolicyRecord(
        id="pol-paper-gate",
        name="paper-gate",
        definition={"signalKinds": ["entry_long"]},
        mode="paper_auto",
        account_id="acc-1",
        strategy_definition_id=None,
        origin="test",
        enabled=True,
        user_id=None,
        created_at="2026-08-26T00:00:00Z",
        updated_at="2026-08-26T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_execute_paper_auto_blocked_without_paper_d_execute(monkeypatch) -> None:
    """F5 — Router.execute() exige PAPER_D_EXECUTE en mode paper_auto."""
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    router = ExecutionRouter(
        policy_repo=_FakePolicyRepo(_paper_auto_policy()),  # type: ignore[arg-type]
        account_repo=object(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=object(),  # type: ignore[arg-type]
        portfolio_summary=object(),  # type: ignore[arg-type]
    )
    hits: list[dict[str, Any]] = [
        {
            "instrumentId": "inst-1",
            "symbol": "SAN",
            "signal": {
                "id": "sig-1",
                "instrumentId": "inst-1",
                "timestamp": "2026-08-26T12:00:00Z",
                "kind": "entry_long",
                "strategyDefinitionId": "st-1",
                "strategyVersion": 1,
                "barIndex": 0,
                "price": 10.0,
            },
        }
    ]
    with pytest.raises(PaperAutoEnvBlockedError) as exc:
        await router.execute("pol-paper-gate", hits)
    assert str(exc.value) == PAPER_AUTO_ENV_BLOCKED


@pytest.mark.asyncio
async def test_execute_inform_only_skips_paper_d_execute_gate(monkeypatch) -> None:
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    policy = ExecutionPolicyRecord(
        id="pol-inform",
        name="inform",
        definition={"signalKinds": ["entry_long"]},
        mode="inform_only",
        account_id=None,
        strategy_definition_id=None,
        origin="test",
        enabled=True,
        user_id=None,
        created_at="2026-08-26T00:00:00Z",
        updated_at="2026-08-26T00:00:00Z",
    )
    router = ExecutionRouter(
        policy_repo=_FakePolicyRepo(policy),  # type: ignore[arg-type]
        account_repo=object(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=object(),  # type: ignore[arg-type]
        portfolio_summary=object(),  # type: ignore[arg-type]
    )
    result = await router.execute(
        "pol-inform",
        [
            {
                "instrumentId": "inst-1",
                "signal": {
                    "id": "sig-1",
                    "instrumentId": "inst-1",
                    "timestamp": "2026-08-26T12:00:00Z",
                    "kind": "entry_long",
                    "strategyVersion": 1,
                    "barIndex": 0,
                    "price": 10.0,
                },
            }
        ],
    )
    assert result.mode == "inform_only"
    assert result.actions[0].status == "inform_only"


@pytest.mark.asyncio
async def test_entry_short_skipped_as_unsupported(monkeypatch) -> None:
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    policy = ExecutionPolicyRecord(
        id="pol-inform-short",
        name="inform-short",
        definition={"signalKinds": ["entry_short"]},
        mode="inform_only",
        account_id=None,
        strategy_definition_id=None,
        origin="test",
        enabled=True,
        user_id=None,
        created_at="2026-08-26T00:00:00Z",
        updated_at="2026-08-26T00:00:00Z",
    )
    router = ExecutionRouter(
        policy_repo=_FakePolicyRepo(policy),  # type: ignore[arg-type]
        account_repo=object(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=object(),  # type: ignore[arg-type]
        portfolio_summary=object(),  # type: ignore[arg-type]
    )
    result = await router.execute(
        "pol-inform-short",
        [
            {
                "instrumentId": "inst-1",
                "signal": {
                    "id": "sig-1",
                    "instrumentId": "inst-1",
                    "timestamp": "2026-08-26T12:00:00Z",
                    "kind": "entry_short",
                    "strategyVersion": 1,
                    "barIndex": 0,
                    "price": 10.0,
                },
            }
        ],
    )
    assert result.actions[0].status == "skipped"
    assert result.actions[0].reason == "unsupported_short"


def test_signal_kind_to_trade_type() -> None:
    assert signal_kind_to_trade_type("entry_long") == "buy"
    assert signal_kind_to_trade_type("exit") == "sell"
    assert signal_kind_to_trade_type("reduce") == "sell"
    assert signal_kind_to_trade_type("watch") is None


def test_validate_execution_mode() -> None:
    assert validate_execution_mode("paper_auto") == "paper_auto"
    try:
        validate_execution_mode("invalid")
    except ValueError as exc:
        assert "mode debe ser" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def _triggered_plan(*, quantity: float = 5.0, price: float = 10.0) -> dict[str, Any]:
    stop = price * 0.95
    return {
        "decisionId": "dec-a-beta",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "quantity": quantity,
        "entry": price,
        "structuralStop": stop,
        "riskAmount": quantity * (price - stop),
        "initialRiskR": 1,
        "whyNot": [],
        "executionAllowed": True,
    }


class _FakeAccount:
    id = "acc-1"
    type = "simulated"
    initial_deposit = 10_000.0
    active_profile_id = None


class _FakeScope:
    account = _FakeAccount()


class _FakeAccountRepo:
    async def resolve_scope(self, account_id: str, portfolio_id: str | None = None):
        return _FakeScope()

    async def get_settings_json(self, account_id: str) -> dict[str, Any]:
        return {}

    async def merge_settings_json(self, account_id: str, fragment: dict[str, Any]) -> None:
        return None


class _FakeSummary:
    positions: list[Any] = []
    total_equity = 10_000.0

    async def execute(self, account_id: str | None = None, portfolio_id: str | None = None):
        return self


class _FakeTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        tx = type("Tx", (), {"id": "tx-a-beta"})()
        return type("TradeResult", (), {"transaction": tx})()


def _router_for_a_beta() -> ExecutionRouter:
    return ExecutionRouter(
        policy_repo=_FakePolicyRepo(_paper_auto_policy()),  # type: ignore[arg-type]
        account_repo=_FakeAccountRepo(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=_FakeTrade(),  # type: ignore[arg-type]
        portfolio_summary=_FakeSummary(),  # type: ignore[arg-type]
        profile_store=None,
        enforce_cognitive_gate=False,
    )


def _entry_hit(
    *,
    auto_source: str | None = "estudio_dictamen",
    trade_plan: dict[str, Any] | None = None,
    price: float = 10.0,
) -> dict[str, Any]:
    from bolsa_analytics.signals.strategy import SignalEventV1

    signal = SignalEventV1(
        id="sig-a-beta",
        instrument_id="inst-1",
        timestamp="2026-08-30T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=price,
    )
    hit: dict[str, Any] = {
        "instrumentId": "inst-1",
        "symbol": "SAN",
        "signal": {
            "id": signal.id,
            "instrumentId": signal.instrument_id,
            "timestamp": signal.timestamp,
            "kind": signal.kind,
            "strategyDefinitionId": signal.strategy_definition_id,
            "strategyVersion": signal.strategy_version,
            "barIndex": signal.bar_index,
            "price": signal.price,
        },
    }
    if auto_source is not None:
        hit["autoSource"] = auto_source
    if trade_plan is not None:
        hit["tradePlan"] = trade_plan
    return hit


@pytest.mark.asyncio
async def test_paper_auto_opening_uses_triggered_plan_quantity(monkeypatch) -> None:
    """V1.33 A-β — qty = TradePlan TRIGGERED, no sizing_value/price."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    router = _router_for_a_beta()
    trade = router._execute_trade
    assert isinstance(trade, _FakeTrade)
    signal = __import__(
        "bolsa_analytics.signals.strategy", fromlist=["SignalEventV1"]
    ).SignalEventV1(
        id="sig-a-beta",
        instrument_id="inst-1",
        timestamp="2026-08-30T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=10.0,
    )
    result = await router._execute_paper_trade(
        _paper_auto_policy(),
        signal,
        hit=_entry_hit(trade_plan=_triggered_plan(quantity=7.0, price=10.0)),
        sizing_value=1000.0,  # would yield qty=100 if libro sizing — must not win
    )
    assert result.status == "trade_executed", result.reason
    assert len(trade.calls) == 1
    assert trade.calls[0]["quantity"] == 7.0


@pytest.mark.asyncio
async def test_paper_auto_opening_denied_without_triggered_plan(monkeypatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    router = _router_for_a_beta()
    from bolsa_analytics.signals.strategy import SignalEventV1

    signal = SignalEventV1(
        id="sig-no-plan",
        instrument_id="inst-1",
        timestamp="2026-08-30T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=10.0,
    )
    result = await router._execute_paper_trade(
        _paper_auto_policy(),
        signal,
        hit=_entry_hit(trade_plan=None),
        sizing_value=1000.0,
    )
    assert result.status == "skipped"
    assert result.reason == "no_tradeplan"


@pytest.mark.asyncio
async def test_paper_auto_non_estudio_source_skipped(monkeypatch) -> None:
    """V1.33 A-δ — Paper D / radar no abren hasta ampliar fuente."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    router = _router_for_a_beta()
    from bolsa_analytics.signals.strategy import SignalEventV1

    signal = SignalEventV1(
        id="sig-paper-d",
        instrument_id="inst-1",
        timestamp="2026-08-30T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=10.0,
    )
    result = await router._execute_paper_trade(
        _paper_auto_policy(),
        signal,
        hit=_entry_hit(
            auto_source="paper_d",
            trade_plan=_triggered_plan(quantity=5.0),
        ),
        sizing_value=1000.0,
    )
    assert result.status == "skipped"
    assert result.reason == "auto_source_not_estudio"


@pytest.mark.asyncio
async def test_paper_auto_opening_risk_signature_qty_above_plan(monkeypatch) -> None:
    """AUTO no tiene override humano → qty ≠ plan no aplica; plan qty is used.

    Si el plan no es TRIGGERED, DENY no_tradeplan / risk_signature.
    """
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    router = _router_for_a_beta()
    from bolsa_analytics.signals.strategy import SignalEventV1

    signal = SignalEventV1(
        id="sig-watch",
        instrument_id="inst-1",
        timestamp="2026-08-30T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=10.0,
    )
    watch = _triggered_plan(quantity=5.0)
    watch["status"] = "WATCH"
    result = await router._execute_paper_trade(
        _paper_auto_policy(),
        signal,
        hit=_entry_hit(trade_plan=watch),
        sizing_value=1000.0,
    )
    assert result.status == "skipped"
    assert result.reason == "no_tradeplan"


class _Desk07FillStore:
    """OI-1 style store for GP-DESK-07 Position birth."""

    def __init__(self) -> None:
        self.inserts: list[dict[str, Any]] = []
        self.by_tx: dict[str, dict[str, Any]] = {}
        self.open_by_instrument: dict[tuple[str, str], dict[str, Any]] = {}

    async def get_by_open_transaction_id(self, open_transaction_id: str) -> dict[str, Any] | None:
        return self.by_tx.get(open_transaction_id)

    async def get_open_for_instrument(
        self, account_id: str, instrument_id: str
    ) -> dict[str, Any] | None:
        return self.open_by_instrument.get((account_id, instrument_id))

    async def insert(self, **kwargs: Any) -> dict[str, Any]:
        row = {"id": kwargs.get("position_id") or f"pos-{len(self.inserts)+1}", **kwargs}
        self.inserts.append(row)
        self.by_tx[str(kwargs["open_transaction_id"])] = row
        self.open_by_instrument[(kwargs["account_id"], kwargs["instrument_id"])] = row
        return row


def _router_with_position_store(store: _Desk07FillStore) -> ExecutionRouter:
    from bolsa_application.persist_position_from_fill import PersistPositionFromFill

    return ExecutionRouter(
        policy_repo=_FakePolicyRepo(_paper_auto_policy()),  # type: ignore[arg-type]
        account_repo=_FakeAccountRepo(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=_FakeTrade(),  # type: ignore[arg-type]
        portfolio_summary=_FakeSummary(),  # type: ignore[arg-type]
        profile_store=None,
        enforce_cognitive_gate=False,
        position_from_fill=PersistPositionFromFill(store),
    )


def _triggered_plan_full(*, quantity: float = 5.0, price: float = 10.0) -> dict[str, Any]:
    stop = price * 0.95
    t1 = price * 1.05
    t2 = price * 1.10
    return {
        "decisionId": "dec-stale",
        "instrumentId": "inst-1",
        "direction": "long",
        "status": "TRIGGERED",
        "quantity": quantity,
        "entry": price,
        "structuralStop": stop,
        "target1": t1,
        "target2": t2,
        "riskAmount": quantity * (price - stop),
        "initialRiskR": 1,
        "whyNot": [],
        "executionAllowed": True,
    }


@pytest.mark.asyncio
async def test_gp_desk_07_opening_fill_births_position(monkeypatch) -> None:
    """GP-DESK-07 — trade_executed → Position; plan/candidate/fill ids distintas."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _Desk07FillStore()
    router = _router_with_position_store(store)
    from bolsa_analytics.signals.strategy import SignalEventV1

    signal = SignalEventV1(
        id="sig-desk-07",
        instrument_id="inst-1",
        timestamp="2026-08-30T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=10.0,
    )
    plan = _triggered_plan_full(quantity=7.0, price=10.0)
    hit = _entry_hit(trade_plan=plan, auto_source="estudio_dictamen")
    hit["templateId"] = "moderate"
    hit["dictamenStars"] = 4
    hit["signal"]["id"] = signal.id

    result = await router._execute_paper_trade(
        _paper_auto_policy(),
        signal,
        hit=hit,
        sizing_value=1000.0,
    )
    assert result.status == "trade_executed", result.reason
    assert result.reason is None
    assert result.transaction_id == "tx-a-beta"
    assert len(store.inserts) == 1
    row = store.inserts[0]
    assert row["trade_plan_id"] == "dec-stale"
    snap = row["trade_plan_snapshot"]
    assert snap["decisionId"] == "dec-stale"
    assert snap["candidateDecisionId"] == "sig-desk-07"
    assert snap["fillId"] == "tx-a-beta"
    assert snap["entry"] == 10.0
    assert snap["structuralStop"] == 9.5
    assert snap["target1"] == 10.5
    assert snap["target2"] == 11.0
    assert snap["riskAmount"] == pytest.approx(7.0 * 0.5)
    assert snap["templateId"] == "moderate"
    assert snap["autoSource"] == "estudio_dictamen"
    assert snap["dictamenStars"] == 4
    assert snap["candidateSnapshot"]["decisionId"] == "sig-desk-07"
    assert row["open_transaction_id"] == "tx-a-beta"
    assert row["open_transaction_id"] == snap["fillId"]


@pytest.mark.asyncio
async def test_gp_desk_07_idempotent_same_open_transaction(monkeypatch) -> None:
    """Misma open_transaction_id no duplica Position."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _Desk07FillStore()
    router = _router_with_position_store(store)
    from bolsa_analytics.signals.strategy import SignalEventV1

    signal = SignalEventV1(
        id="sig-desk-07-idem",
        instrument_id="inst-1",
        timestamp="2026-08-30T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=10.0,
    )
    hit = _entry_hit(trade_plan=_triggered_plan_full())
    hit["signal"]["id"] = signal.id

    first = await router._execute_paper_trade(
        _paper_auto_policy(), signal, hit=hit, sizing_value=1000.0
    )
    second = await router._execute_paper_trade(
        _paper_auto_policy(), signal, hit=hit, sizing_value=1000.0
    )
    assert first.status == "trade_executed"
    assert second.status == "trade_executed"
    assert len(store.inserts) == 1


@pytest.mark.asyncio
async def test_gp_desk_07_gate_deny_no_position(monkeypatch) -> None:
    """Gate DENY / no_tradeplan → sin fill → sin Position (regresión GP-DESK-05)."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    store = _Desk07FillStore()
    router = _router_with_position_store(store)
    from bolsa_analytics.signals.strategy import SignalEventV1

    signal = SignalEventV1(
        id="sig-desk-07-deny",
        instrument_id="inst-1",
        timestamp="2026-08-30T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=10.0,
    )
    result = await router._execute_paper_trade(
        _paper_auto_policy(),
        signal,
        hit=_entry_hit(trade_plan=None),
        sizing_value=1000.0,
    )
    assert result.status == "skipped"
    assert result.reason == "no_tradeplan"
    assert store.inserts == []


def test_enrich_opening_trade_plan_preserves_plan_decision_id() -> None:
    from bolsa_application.execution_router import enrich_opening_trade_plan_for_position

    plan = {"decisionId": "old", "status": "TRIGGERED", "entry": 1.0}
    out = enrich_opening_trade_plan_for_position(
        plan,
        signal_id="sig-new",
        hit={"templateId": "conservative", "autoSource": "estudio_alarma", "rank": 2},
        fill_id="tx-fill-1",
    )
    assert out["decisionId"] == "old"
    assert out["candidateDecisionId"] == "sig-new"
    assert out["fillId"] == "tx-fill-1"
    assert out["templateId"] == "conservative"
    assert out["autoSource"] == "estudio_alarma"
    assert out["rank"] == 2
    assert out["candidateSnapshot"]["decisionId"] == "sig-new"
    assert plan["decisionId"] == "old"


@pytest.mark.asyncio
async def test_gp_desk_05b_real_opening_gate_no_position(monkeypatch) -> None:
    """GP-DESK-05b — check_opening real (book max) → skipped · 0 Positions."""
    from types import SimpleNamespace

    from bolsa_analytics.signals.strategy import SignalEventV1
    from bolsa_application.persist_position_from_fill import PersistPositionFromFill

    monkeypatch.setenv("PAPER_D_EXECUTE", "1")

    async def _kill_off() -> bool:
        return False

    monkeypatch.setattr(
        "bolsa_application.execution_router.effective_kill_switch",
        _kill_off,
    )
    store = _Desk07FillStore()
    summary = SimpleNamespace(
        positions=[SimpleNamespace(instrument_id="held", quantity=1.0)],
        total_equity=10_000.0,
    )

    class _Summary:
        async def execute(self, account_id: str | None = None, portfolio_id: str | None = None):
            _ = account_id, portfolio_id
            return summary

    policy = ExecutionPolicyRecord(
        id="pol-paper-gate",
        name="paper-gate",
        definition={"signalKinds": ["entry_long"], "bookMaxOpenPositions": 1},
        mode="paper_auto",
        account_id="acc-1",
        strategy_definition_id=None,
        origin="test",
        enabled=True,
        user_id=None,
        created_at="2026-08-26T00:00:00Z",
        updated_at="2026-08-26T00:00:00Z",
    )
    router = ExecutionRouter(
        policy_repo=_FakePolicyRepo(policy),  # type: ignore[arg-type]
        account_repo=_FakeAccountRepo(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=_FakeTrade(),  # type: ignore[arg-type]
        portfolio_summary=_Summary(),  # type: ignore[arg-type]
        profile_store=None,
        enforce_cognitive_gate=True,
        position_from_fill=PersistPositionFromFill(store),
    )
    signal = SignalEventV1(
        id="sig-desk-05b",
        instrument_id="inst-1",
        timestamp="2026-09-01T11:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=10.0,
    )
    result = await router._execute_paper_trade(
        policy,
        signal,
        hit=_entry_hit(trade_plan=_triggered_plan_full()),
        sizing_value=1000.0,
    )
    assert result.status == "skipped"
    assert result.reason is not None
    assert "book_max_open_positions" in result.reason
    assert store.inserts == []
    assert result.transaction_id is None
