"""Ciclo RX1 — exits full_auto → Router paper_auto fail-closed (no thaw)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bolsa_analytics.signals.evaluate import SignalEvent
from bolsa_application.paper_auto_http_gate import (
    LAB_EXIT_EXECUTE_RETIRED,
    LabExitExecuteRetiredError,
)
from bolsa_application.position_exit_evaluator import EvaluatePositionExits
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord
from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.entities.portfolio import Portfolio, PortfolioSummary, Position
from bolsa_domain.entities.position_policy import PositionPolicyRecord


def _portfolio_with_long() -> PortfolioSummary:
    return PortfolioSummary(
        portfolio=Portfolio(id="pf1", name="t", currency="EUR", cash=10_000),
        positions=[
            Position(
                id="pos1",
                instrument_id="inst1",
                symbol="AAA",
                name="AAA Co",
                quantity=10.0,
                avg_cost=50.0,
                last_price=55.0,
                market_value=550.0,
                unrealized_pnl=50.0,
                unrealized_pnl_pct=10.0,
            )
        ],
        total_market_value=550.0,
        total_cost=500.0,
        total_unrealized_pnl=50.0,
        total_equity=10_550.0,
    )


def _full_auto_policy(*, execution_policy_id: str = "ep1") -> PositionPolicyRecord:
    return PositionPolicyRecord(
        id="pp1",
        account_id="acc1",
        instrument_id="inst1",
        definition={},
        mode="full_auto",
        exit_strategy_definition_id=None,
        execution_policy_id=execution_policy_id,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def _exec_policy(*, mode: str = "paper_auto") -> ExecutionPolicyRecord:
    return ExecutionPolicyRecord(
        id="ep1",
        name="paper",
        definition={},
        mode=mode,
        account_id="acc1",
        strategy_definition_id="strat1",
        origin="user",
        enabled=True,
        user_id=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def _bars() -> list[OhlcvBar]:
    return [
        OhlcvBar(
            timestamp="2026-01-01T00:00:00Z",
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1,
        ),
        OhlcvBar(
            timestamp="2026-01-02T00:00:00Z",
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1,
        ),
    ]


def _build_use_case(
    *,
    exec_mode: str = "paper_auto",
    router: AsyncMock | None = None,
) -> EvaluatePositionExits:
    portfolio = AsyncMock()
    portfolio.execute = AsyncMock(return_value=_portfolio_with_long())

    policy_lookup = AsyncMock()
    policy_lookup.execute = AsyncMock(return_value=_full_auto_policy())

    strategies = AsyncMock()
    strategies.get_definition = AsyncMock(
        return_value=SimpleNamespace(
            definition={"id": "strat1", "version": 1, "presetKey": "sma_crossover"}
        )
    )

    execution_policies = AsyncMock()
    execution_policies.get_policy = AsyncMock(return_value=_exec_policy(mode=exec_mode))

    ohlcv = AsyncMock()
    ohlcv.execute = AsyncMock(return_value=_bars())

    return EvaluatePositionExits(
        portfolio_summary=portfolio,
        position_policy_lookup=policy_lookup,
        strategy_repository=strategies,
        execution_policy_repository=execution_policies,
        get_ohlcv_bars=ohlcv,
        execution_router=router if router is not None else AsyncMock(),
    )


@pytest.fixture
def _force_exit_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "bolsa_application.position_exit_evaluator.enrich_definition_with_preset_rules",
        lambda definition: definition,
    )
    monkeypatch.setattr(
        "bolsa_application.position_exit_evaluator.evaluate_exit_last_bar_gated",
        lambda *_a, **_k: SignalEvent(
            kind="exit",
            bar_index=1,
            timestamp="2026-01-02T00:00:00Z",
            price=1.0,
            preset_key="sma_crossover",
        ),
    )


@pytest.mark.asyncio
async def test_eval_only_full_auto_paper_auto_skips_env_gate(
    monkeypatch: pytest.MonkeyPatch,
    _force_exit_signal: None,
) -> None:
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    router = AsyncMock()
    use_case = _build_use_case(router=router)
    result = await use_case.execute("acc1", execute_trades=False)
    assert result.results[0].status == "exit_signal"
    router.execute.assert_not_called()


@pytest.mark.asyncio
async def test_execute_full_auto_paper_auto_blocked_without_env(
    monkeypatch: pytest.MonkeyPatch,
    _force_exit_signal: None,
) -> None:
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    router = AsyncMock()
    use_case = _build_use_case(router=router)
    with pytest.raises(LabExitExecuteRetiredError) as exc:
        await use_case.execute("acc1", execute_trades=True)
    assert str(exc.value) == LAB_EXIT_EXECUTE_RETIRED
    router.execute.assert_not_called()


@pytest.mark.asyncio
async def test_execute_full_auto_retired_even_with_env(
    monkeypatch: pytest.MonkeyPatch,
    _force_exit_signal: None,
) -> None:
    """V1.52 GP Lab: executeTrades=true DENY aunque PAPER_D_EXECUTE on."""
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    router = AsyncMock()
    use_case = _build_use_case(router=router)
    with pytest.raises(LabExitExecuteRetiredError) as exc:
        await use_case.execute("acc1", execute_trades=True)
    assert str(exc.value) == LAB_EXIT_EXECUTE_RETIRED
    router.execute.assert_not_called()


@pytest.mark.asyncio
async def test_execute_full_auto_inform_only_also_retired(
    monkeypatch: pytest.MonkeyPatch,
    _force_exit_signal: None,
) -> None:
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    router = AsyncMock()
    use_case = _build_use_case(exec_mode="inform_only", router=router)
    with pytest.raises(LabExitExecuteRetiredError):
        await use_case.execute("acc1", execute_trades=True)
    router.execute.assert_not_called()
