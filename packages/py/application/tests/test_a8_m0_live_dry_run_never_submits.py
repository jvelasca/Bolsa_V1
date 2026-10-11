"""A8 · M0 · §7 — negativo E2E: ``live_auto`` dry-run JAMÁS toca la vía real.

``_evaluate_live_dry_run`` es el único punto donde AUTO "roza" el modo LIVE (evalúa Gate
+ ``check_auto_live`` + manifest) y hasta F6-broker NO está cableado: su contrato es
PASS/VETO *sin orden real*. Antes de §7 eso se garantizaba por construcción, no por test.

Aquí se afirma de forma explícita y agresiva: **con AMBAS barreras LIVE abiertas**
(``LIVE_EXECUTION_AUTHORIZED`` + ``LIVE_EXECUTION_UNLOCKED``), recorrer el dry-run
completo no invoca ``resolve_broker_adapter``, ni ``*.submit`` de ningún adapter, ni
``ExecuteTrade``. Un cambio futuro que cablee el broker en el dry-run rompe este test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bolsa_application.execution_router import ExecutionRouter
from bolsa_application.live_execution_runtime import (
    LIVE_EXECUTION_AUTHORIZE_ENV,
    LIVE_EXECUTION_UNLOCK_ENV,
)
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord

_PKG = Path(__file__).resolve().parents[1] / "src" / "bolsa_application"
_DRY_RUN_RESULTS = {"live_dry_run_pass", "live_dry_run_veto"}


class _FakePolicyRepo:
    def __init__(self, policy: ExecutionPolicyRecord) -> None:
        self._policy = policy

    async def get_policy(self, policy_id: str) -> ExecutionPolicyRecord | None:
        return self._policy if self._policy.id == policy_id else None


class _FakeAccount:
    type = "simulated"
    initial_deposit = 10_000.0
    active_profile_id = None


class _FakeScope:
    account = _FakeAccount()


class _FakeAccountRepo:
    async def resolve_scope(self, account_id: str, portfolio_id: str | None = None):
        _ = account_id, portfolio_id
        return _FakeScope()

    async def get_settings_json(self, account_id: str) -> dict[str, Any]:
        _ = account_id
        return {}

    async def merge_settings_json(self, account_id: str, fragment: dict[str, Any]) -> None:
        _ = account_id, fragment
        return None


class _FakeSummary:
    positions: list[Any] = []
    total_equity = 10_000.0

    async def execute(self, account_id: str | None = None, portfolio_id: str | None = None):
        _ = account_id, portfolio_id
        return self


class _FakeTrade:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        tx = type("Tx", (), {"id": "tx-should-never-happen"})()
        return type("TradeResult", (), {"transaction": tx})()


def _live_auto_policy() -> ExecutionPolicyRecord:
    return ExecutionPolicyRecord(
        id="pol-live-dry",
        name="live-dry",
        definition={"signalKinds": ["entry_long"]},
        mode="live_auto",
        account_id="acc-1",
        strategy_definition_id=None,
        origin="test",
        enabled=True,
        user_id=None,
        created_at="2026-08-26T00:00:00Z",
        updated_at="2026-08-26T00:00:00Z",
    )


def _signal() -> Any:
    from bolsa_analytics.signals.strategy import SignalEventV1

    return SignalEventV1(
        id="sig-live-dry",
        instrument_id="inst-1",
        timestamp="2026-08-30T12:00:00Z",
        kind="entry_long",
        strategy_definition_id="st-1",
        strategy_version=1,
        bar_index=0,
        price=10.0,
    )


def _install_live_traps(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Sustituye la vía real por minas: cualquier toque queda registrado y explota."""
    import bolsa_application.broker_adapter as ba

    hits: list[str] = []

    def _trap(name: str):
        def _f(*_a: Any, **_k: Any) -> Any:
            hits.append(name)
            raise AssertionError(f"live_auto dry-run tocó la vía REAL: {name}")

        return _f

    def _atrap(name: str):
        async def _f(*_a: Any, **_k: Any) -> Any:
            hits.append(name)
            raise AssertionError(f"live_auto dry-run hizo POST real: {name}")

        return _f

    monkeypatch.setattr(
        ba, "resolve_broker_adapter", _trap("resolve_broker_adapter"), raising=False
    )
    for cls_name in ("XtbBrokerAdapter", "MockBrokerAdapter", "PaperBrokerAdapter"):
        klass = getattr(ba, cls_name, None)
        if klass is None:
            continue
        monkeypatch.setattr(klass, "submit", _atrap(f"{cls_name}.submit"), raising=False)
    return hits


def _router(trade: _FakeTrade) -> ExecutionRouter:
    return ExecutionRouter(
        policy_repo=_FakePolicyRepo(_live_auto_policy()),  # type: ignore[arg-type]
        account_repo=_FakeAccountRepo(),  # type: ignore[arg-type]
        strategy_repo=object(),  # type: ignore[arg-type]
        backtest_repo=object(),  # type: ignore[arg-type]
        execute_trade=trade,  # type: ignore[arg-type]
        portfolio_summary=_FakeSummary(),  # type: ignore[arg-type]
        profile_store=None,
        enforce_cognitive_gate=False,
    )


@pytest.mark.asyncio
async def test_live_auto_dry_run_never_reaches_real_path_even_with_barriers_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Barreras LIVE ABAJO... y también ARRIBA: el dry-run no toca broker ni ledger."""

    async def _kill_off() -> bool:
        return False

    monkeypatch.setattr("bolsa_application.execution_router.effective_kill_switch", _kill_off)
    hits = _install_live_traps(monkeypatch)
    trade = _FakeTrade()
    router = _router(trade)
    policy = _live_auto_policy()
    hit = {
        "instrumentId": "inst-1",
        "symbol": "SAN",
        "signal": {
            "id": "sig-live-dry",
            "instrumentId": "inst-1",
            "timestamp": "2026-08-30T12:00:00Z",
            "kind": "entry_long",
            "strategyDefinitionId": "st-1",
            "strategyVersion": 1,
            "barIndex": 0,
            "price": 10.0,
        },
    }

    for authorized, unlocked in ((None, None), ("1", "1")):
        if authorized is None:
            monkeypatch.delenv(LIVE_EXECUTION_AUTHORIZE_ENV, raising=False)
        else:
            monkeypatch.setenv(LIVE_EXECUTION_AUTHORIZE_ENV, authorized)
        if unlocked is None:
            monkeypatch.delenv(LIVE_EXECUTION_UNLOCK_ENV, raising=False)
        else:
            monkeypatch.setenv(LIVE_EXECUTION_UNLOCK_ENV, unlocked)

        result = await router._evaluate_live_dry_run(
            policy, _signal(), hit=hit, sizing_value=1000.0
        )

        assert result.status in _DRY_RUN_RESULTS, result.reason
        if result.status == "live_dry_run_pass":
            assert result.transaction_id is None
            assert "sin orden real" in (result.reason or "")

    assert hits == [], f"la vía real fue tocada desde live_auto dry-run: {hits}"
    assert trade.calls == [], "live_auto dry-run aplicó ExecuteTrade (dinero movido)"


def test_evaluate_live_dry_run_source_has_no_submit_or_adapter_resolution() -> None:
    """Complemento estructural: el método no contiene ninguna llamada de vía real."""
    source = (_PKG / "execution_router.py").read_text(encoding="utf-8")
    assert ".submit(" not in source
    assert "resolve_broker_adapter" not in source
