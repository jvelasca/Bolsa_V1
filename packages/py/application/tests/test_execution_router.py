from __future__ import annotations

from typing import Any

import pytest
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord
from bolsa_domain.platform_kernel import validate_execution_mode

from bolsa_application.execution_router import ExecutionRouter, signal_kind_to_trade_type
from bolsa_application.paper_auto_http_gate import (
    PAPER_AUTO_ENV_BLOCKED,
    PaperAutoEnvBlockedError,
)


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


def test_signal_kind_to_trade_type() -> None:
    assert signal_kind_to_trade_type("entry_long") == "buy"
    assert signal_kind_to_trade_type("exit") == "sell"
    assert signal_kind_to_trade_type("watch") is None


def test_validate_execution_mode() -> None:
    assert validate_execution_mode("paper_auto") == "paper_auto"
    try:
        validate_execution_mode("invalid")
    except ValueError as exc:
        assert "mode debe ser" in str(exc)
    else:
        raise AssertionError("expected ValueError")
