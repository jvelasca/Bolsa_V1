"""Evalúa señales de salida para posiciones abiertas con position_policy (P7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from bolsa_analytics.signals.preset_rules import enrich_definition_with_preset_rules
from bolsa_analytics.signals.rules_engine import evaluate_exit_last_bar_gated
from bolsa_analytics.signals.strategy import SignalEventV1, _to_signal_event_v1
from bolsa_application.accounts import GetPortfolioSummary
from bolsa_application.execution_router import ExecutionActionResult, ExecutionRouter
from bolsa_application.get_ohlcv_bars import GetOhlcvBars
from bolsa_application.paper_auto_http_gate import (
    LabExitExecuteRetiredError,
    require_http_paper_auto_env,
)
from bolsa_application.persist_position_from_exit import (
    PersistPositionFromExit,
    PersistPositionFromExitInput,
)
from bolsa_application.position_policies import GetPositionPolicyForHolding
from bolsa_domain.repositories.execution_policy_repository import ExecutionPolicyRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True, slots=True)
class PositionExitEvalResult:
    """Resultado de Position Exit Eval."""
    account_id: str
    instrument_id: str
    symbol: str
    quantity: float
    policy_id: str | None
    mode: str | None
    status: Literal[
        "no_policy",
        "manual",
        "no_exit_strategy",
        "no_bars",
        "no_signal",
        "exit_signal",
        "executed",
        "skipped",
        "error",
    ]
    signal: dict[str, Any] | None = None
    action: ExecutionActionResult | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluatePositionExitsResult:
    """Evalúa Position Exits Result."""
    account_id: str
    evaluated_count: int
    results: list[PositionExitEvalResult] = field(default_factory=list)


def _signal_to_hit(signal: SignalEventV1, *, symbol: str) -> dict[str, Any]:
    return {
        "instrumentId": signal.instrument_id,
        "symbol": symbol,
        "signal": {
            "id": signal.id,
            "instrumentId": signal.instrument_id,
            "timestamp": signal.timestamp,
            "kind": signal.kind,
            "strategyDefinitionId": signal.strategy_definition_id,
            "strategyVersion": signal.strategy_version,
            "barIndex": signal.bar_index,
            "price": signal.price,
            "dataVersion": signal.data_version,
            "indicatorSnapshotHash": signal.indicator_snapshot_hash,
            "presetKey": signal.preset_key,
        },
    }


class EvaluatePositionExits:
    """Evalúa Position Exits."""
    def __init__(
        self,
        portfolio_summary: GetPortfolioSummary,
        position_policy_lookup: GetPositionPolicyForHolding,
        strategy_repository: StrategyDefinitionRepository,
        execution_policy_repository: ExecutionPolicyRepository,
        get_ohlcv_bars: GetOhlcvBars,
        execution_router: ExecutionRouter | None = None,
        position_from_exit: PersistPositionFromExit | None = None,
    ) -> None:
        self._portfolio = portfolio_summary
        self._policy_lookup = position_policy_lookup
        self._strategies = strategy_repository
        self._execution_policies = execution_policy_repository
        self._ohlcv = get_ohlcv_bars
        self._router = execution_router
        self._position_from_exit = position_from_exit

    async def _resolve_exit_definition(
        self,
        *,
        mode: str,
        exit_strategy_definition_id: str | None,
        execution_policy_id: str | None,
    ) -> dict[str, Any] | None:
        if exit_strategy_definition_id:
            record = await self._strategies.get_definition(exit_strategy_definition_id)
            return record.definition if record else None

        if mode == "full_auto" and execution_policy_id:
            policy = await self._execution_policies.get_policy(execution_policy_id)
            if policy is None or not policy.strategy_definition_id:
                return None
            record = await self._strategies.get_definition(policy.strategy_definition_id)
            return record.definition if record else None

        return None

    async def execute(
        self,
        account_id: str,
        *,
        execute_trades: bool = False,
        timeframe: str = "1d",
        bar_limit: int = 120,
    ) -> EvaluatePositionExitsResult:
        if execute_trades:
            # V1.52 — única autoridad AUTO SELL = PaperDesk / ExecutePositionPolicyAuto.
            raise LabExitExecuteRetiredError()
        summary = await self._portfolio.execute(account_id=account_id)
        tf = TimeFrame.W1 if timeframe == "1wk" else TimeFrame.D1

        results: list[PositionExitEvalResult] = []
        open_positions = [pos for pos in summary.positions if pos.quantity > 0]

        for position in open_positions:
            policy = await self._policy_lookup.execute(account_id, position.instrument_id)
            if policy is None:
                results.append(
                    PositionExitEvalResult(
                        account_id=account_id,
                        instrument_id=position.instrument_id,
                        symbol=position.symbol,
                        quantity=position.quantity,
                        policy_id=None,
                        mode=None,
                        status="no_policy",
                    )
                )
                continue

            if policy.mode == "manual":
                results.append(
                    PositionExitEvalResult(
                        account_id=account_id,
                        instrument_id=position.instrument_id,
                        symbol=position.symbol,
                        quantity=position.quantity,
                        policy_id=policy.id,
                        mode=policy.mode,
                        status="manual",
                    )
                )
                continue

            definition = await self._resolve_exit_definition(
                mode=policy.mode,
                exit_strategy_definition_id=policy.exit_strategy_definition_id,
                execution_policy_id=policy.execution_policy_id,
            )
            if definition is None:
                results.append(
                    PositionExitEvalResult(
                        account_id=account_id,
                        instrument_id=position.instrument_id,
                        symbol=position.symbol,
                        quantity=position.quantity,
                        policy_id=policy.id,
                        mode=policy.mode,
                        status="no_exit_strategy",
                    )
                )
                continue

            bars = await self._ohlcv.execute(
                position.instrument_id,
                limit=bar_limit,
                timeframe=tf,
            )
            if not bars:
                results.append(
                    PositionExitEvalResult(
                        account_id=account_id,
                        instrument_id=position.instrument_id,
                        symbol=position.symbol,
                        quantity=position.quantity,
                        policy_id=policy.id,
                        mode=policy.mode,
                        status="no_bars",
                    )
                )
                continue

            timestamps = [bar.timestamp for bar in bars]
            closes = [bar.close for bar in bars]
            resolved = enrich_definition_with_preset_rules(definition)
            raw_event = evaluate_exit_last_bar_gated(resolved, timestamps, closes)
            if raw_event is None:
                results.append(
                    PositionExitEvalResult(
                        account_id=account_id,
                        instrument_id=position.instrument_id,
                        symbol=position.symbol,
                        quantity=position.quantity,
                        policy_id=policy.id,
                        mode=policy.mode,
                        status="no_signal",
                    )
                )
                continue

            strategy_definition_id = str(resolved.get("id") or "unknown")
            strategy_version = int(resolved.get("version") or 1)
            signal = _to_signal_event_v1(
                raw_event,
                instrument_id=position.instrument_id,
                strategy_definition_id=strategy_definition_id,
                strategy_version=strategy_version,
            )
            signal_dict = {
                "id": signal.id,
                "instrumentId": signal.instrument_id,
                "timestamp": signal.timestamp,
                "kind": signal.kind,
                "strategyDefinitionId": signal.strategy_definition_id,
                "strategyVersion": signal.strategy_version,
                "barIndex": signal.bar_index,
                "price": signal.price,
                "presetKey": signal.preset_key,
            }

            if policy.mode == "exit_strategy" or not execute_trades or self._router is None:
                results.append(
                    PositionExitEvalResult(
                        account_id=account_id,
                        instrument_id=position.instrument_id,
                        symbol=position.symbol,
                        quantity=position.quantity,
                        policy_id=policy.id,
                        mode=policy.mode,
                        status="exit_signal",
                        signal=signal_dict,
                    )
                )
                continue

            if policy.mode == "full_auto" and policy.execution_policy_id:
                # RX1: same honesty as I3 — paper_auto fill needs PAPER_D_EXECUTE.
                # Gate before Router (not inside it); eval-only never reaches here.
                exec_policy = await self._execution_policies.get_policy(
                    policy.execution_policy_id
                )
                require_http_paper_auto_env(
                    exec_policy.mode if exec_policy is not None else None
                )
                try:
                    route = await self._router.execute(
                        policy.execution_policy_id,
                        [_signal_to_hit(signal, symbol=position.symbol)],
                    )
                    action = route.actions[0] if route.actions else None
                    status: Literal["executed", "skipped", "error"] = (
                        "executed" if action and action.status == "trade_executed" else "skipped"
                    )
                    if (
                        status == "executed"
                        and action is not None
                        and action.transaction_id
                        and self._position_from_exit is not None
                    ):
                        fill_price = float(signal.price) if signal.price else 0.0
                        if fill_price > 0:
                            await self._position_from_exit.persist(
                                PersistPositionFromExitInput(
                                    account_id=account_id,
                                    instrument_id=position.instrument_id,
                                    fill_quantity=float(position.quantity),
                                    fill_price=fill_price,
                                    exit_transaction_id=str(action.transaction_id),
                                )
                            )
                    results.append(
                        PositionExitEvalResult(
                            account_id=account_id,
                            instrument_id=position.instrument_id,
                            symbol=position.symbol,
                            quantity=position.quantity,
                            policy_id=policy.id,
                            mode=policy.mode,
                            status=status,
                            signal=signal_dict,
                            action=action,
                            reason=action.reason if action else None,
                        )
                    )
                except ValueError as exc:
                    results.append(
                        PositionExitEvalResult(
                            account_id=account_id,
                            instrument_id=position.instrument_id,
                            symbol=position.symbol,
                            quantity=position.quantity,
                            policy_id=policy.id,
                            mode=policy.mode,
                            status="error",
                            signal=signal_dict,
                            reason=str(exc),
                        )
                    )
                continue

            results.append(
                PositionExitEvalResult(
                    account_id=account_id,
                    instrument_id=position.instrument_id,
                    symbol=position.symbol,
                    quantity=position.quantity,
                    policy_id=policy.id,
                    mode=policy.mode,
                    status="exit_signal",
                    signal=signal_dict,
                )
            )

        return EvaluatePositionExitsResult(
            account_id=account_id,
            evaluated_count=len(open_positions),
            results=results,
        )
