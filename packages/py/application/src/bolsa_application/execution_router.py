"""Router de ejecución (scan hits → acciones)."""

from dataclasses import dataclass, field
from typing import Any, Literal

from bolsa_analytics.cognitive.market_events import MarketEventCalendar
from bolsa_analytics.signals.strategy import SignalEventV1
from bolsa_application.accounts import ExecuteTrade, GetPortfolioSummary
from bolsa_application.cognitive_persistence import CognitiveStore, memory_entry_to_record
from bolsa_application.events.payloads import signal_event_payload
from bolsa_application.events.platform_event_bus import PlatformEventBus
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.risk_engine import check_opening
from bolsa_application.trading_policy_guard import CognitiveGuardResult
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord
from bolsa_domain.platform_kernel import PAPER_ACCOUNT_TYPES
from bolsa_domain.repositories.execution_policy_repository import ExecutionPolicyRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_infrastructure.alerts.alert_channels import (
    AlertChannelDispatchResult,
    SignalAlertChannelDispatcher,
)
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.backtest_repository import (
    SqlAlchemyBacktestRepository,
)
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SignalAlertSubscriptionRecord,
)


@dataclass(frozen=True, slots=True)
class ExecutionActionResult:
    """Resultado de Execution Action."""
    instrument_id: str
    signal_kind: str
    status: Literal[
        "inform_only",
        "alert_dispatched",
        "trade_executed",
        "skipped",
        "live_dry_run_pass",
        "live_dry_run_veto",
    ]
    reason: str | None = None
    transaction_id: str | None = None
    dispatches: list[AlertChannelDispatchResult] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ExecutionRouteResult:
    """Resultado de Execution Route."""
    policy_id: str
    mode: str
    actions: list[ExecutionActionResult]


def signal_kind_to_trade_type(kind: str) -> Literal["buy", "sell"] | None:
    if kind == "entry_long":
        return "buy"
    if kind in ("entry_short", "exit"):
        return "sell"
    return None


def _signal_from_hit(hit: dict[str, Any]) -> SignalEventV1:
    raw = hit.get("signal") or {}
    return SignalEventV1(
        id=str(raw.get("id") or ""),
        instrument_id=str(hit.get("instrumentId") or raw.get("instrumentId") or ""),
        timestamp=str(raw.get("timestamp") or ""),
        kind=raw.get("kind"),  # type: ignore[arg-type]
        strategy_definition_id=str(raw.get("strategyDefinitionId") or ""),
        strategy_version=int(raw.get("strategyVersion") or 1),
        bar_index=int(raw.get("barIndex") or 0),
        price=float(raw.get("price") or 0),
        data_version=raw.get("dataVersion"),
        indicator_snapshot_hash=raw.get("indicatorSnapshotHash"),
        preset_key=raw.get("presetKey"),
    )


def _subscription_from_policy(
    policy: ExecutionPolicyRecord,
    *,
    instrument_id: str,
    symbol: str,
    timeframe: str = "1d",
) -> SignalAlertSubscriptionRecord:
    definition = policy.definition
    return SignalAlertSubscriptionRecord(
        id=f"policy:{policy.id}",
        instrument_id=instrument_id,
        symbol=symbol,
        strategy_definition_id=policy.strategy_definition_id,
        preset_key=None,
        timeframe=timeframe,
        signal_kinds=list(definition.get("signalKinds") or []),
        channels=list(definition.get("channels") or ["toast"]),
        webhook_url=definition.get("webhookUrl"),
        email_to=definition.get("emailTo"),
        is_active=True,
        last_triggered_at=None,
        last_bar_timestamp=None,
        last_signal_kind=None,
        last_signal_price=None,
        note=f"ExecutionPolicy {policy.name}",
        created_at=policy.created_at,
    )


class ExecutionRouter:
    """Use-case / tipo: Execution Router."""
    def __init__(
        self,
        policy_repo: ExecutionPolicyRepository,
        account_repo: SqlAlchemyAccountRepository,
        strategy_repo: StrategyDefinitionRepository,
        backtest_repo: SqlAlchemyBacktestRepository,
        execute_trade: ExecuteTrade,
        portfolio_summary: GetPortfolioSummary,
        alert_dispatcher: SignalAlertChannelDispatcher | None = None,
        event_bus: PlatformEventBus | None = None,
        event_calendar: MarketEventCalendar | None = None,
        enforce_cognitive_gate: bool = True,
        cognitive_store: CognitiveStore | None = None,
        profile_store: InvestorProfileStore | None = None,
    ) -> None:
        self._policies = policy_repo
        self._accounts = account_repo
        self._strategies = strategy_repo
        self._backtests = backtest_repo
        self._execute_trade = execute_trade
        self._portfolio_summary = portfolio_summary
        self._alert_dispatcher = alert_dispatcher or SignalAlertChannelDispatcher()
        self._event_bus = event_bus
        self._event_calendar = event_calendar
        self._enforce_cognitive_gate = enforce_cognitive_gate
        self._cognitive_store = cognitive_store
        self._profile_store = profile_store

    async def _persist_gate_memory(
        self,
        guard: CognitiveGuardResult,
        *,
        account_id: str | None,
        lineage: dict[str, Any] | None = None,
        symbol: str | None = None,
        execution_status: str | None = None,
    ) -> None:
        """D7+/F4: ART-DECISION-MEMORY + DecisionSession paper_auto/live_dry_run (best-effort)."""
        if self._cognitive_store is None or guard.memory is None:
            return
        try:
            from dataclasses import replace

            from bolsa_analytics.cognitive.decision_session import build_auto_session
            from bolsa_application.cognitive_persistence import decision_session_to_record

            record = memory_entry_to_record(guard.memory, account_id=account_id)
            if lineage:
                payload = dict(record.payload or {})
                payload["paperAutoManifest"] = {
                    k: v for k, v in lineage.items() if v is not None
                }
                record = replace(record, payload=payload)
            await self._cognitive_store.append_decision_memory(record)

            mode = str((lineage or {}).get("policyMode") or "paper_auto")
            kind = "live_dry_run" if mode == "live_auto" or (lineage or {}).get("dryRun") else "paper_auto"
            gate_dict = guard.to_dict() if hasattr(guard, "to_dict") else {"allowed": guard.allowed}
            session = build_auto_session(
                kind=kind,  # type: ignore[arg-type]
                instrument_id=guard.memory.instrument_id,
                account_id=account_id,
                symbol=symbol,
                policy_gate=gate_dict,
                execution={
                    "status": execution_status or ("accepted" if guard.allowed else "vetoed"),
                    "mode": mode,
                    "dryRun": bool((lineage or {}).get("dryRun")),
                },
                lineage=lineage,
                decision_id=guard.memory.decision_id,
            )
            await self._cognitive_store.append_decision_session(
                decision_session_to_record(session)
            )
        except Exception:  # noqa: BLE001 — no tumbar paper_auto por fallo de audit
            return

    async def execute(self, policy_id: str, hits: list[dict[str, Any]]) -> ExecutionRouteResult:
        policy = await self._policies.get_policy(policy_id)
        if policy is None:
            raise ValueError("Política de ejecución no encontrada")
        if not policy.enabled:
            raise ValueError("Política de ejecución deshabilitada")

        definition = policy.definition
        allowed_kinds = set(definition.get("signalKinds") or [])
        actions: list[ExecutionActionResult] = []

        if policy.mode == "live_auto":
            sizing_value = await self._resolve_sizing_value(policy)
            for hit in hits:
                signal = _signal_from_hit(hit)
                kind = str(signal.kind)
                if kind not in allowed_kinds:
                    actions.append(
                        ExecutionActionResult(
                            instrument_id=signal.instrument_id,
                            signal_kind=kind,
                            status="skipped",
                            reason="signalKind no permitido por la política",
                        )
                    )
                    continue
                await self._emit_signal(signal, policy)
                action = await self._evaluate_live_dry_run(
                    policy,
                    signal,
                    hit=hit,
                    sizing_value=sizing_value,
                )
                actions.append(action)
            return ExecutionRouteResult(policy_id=policy.id, mode=policy.mode, actions=actions)

        if bool(definition.get("requireValidatedBacktest")) and policy.strategy_definition_id:
            if not await self._has_validated_backtest(policy.strategy_definition_id):
                raise ValueError("Guardrail: se requiere backtest con manifest para esta estrategia")

        sizing_value = await self._resolve_sizing_value(policy)

        for hit in hits:
            signal = _signal_from_hit(hit)
            kind = str(signal.kind)
            if kind not in allowed_kinds:
                actions.append(
                    ExecutionActionResult(
                        instrument_id=signal.instrument_id,
                        signal_kind=kind,
                        status="skipped",
                        reason="signalKind no permitido por la política",
                    )
                )
                continue

            await self._emit_signal(signal, policy)

            if policy.mode == "inform_only":
                actions.append(
                    ExecutionActionResult(
                        instrument_id=signal.instrument_id,
                        signal_kind=kind,
                        status="inform_only",
                    )
                )
                continue

            if policy.mode == "alert":
                subscription = _subscription_from_policy(
                    policy,
                    instrument_id=signal.instrument_id,
                    symbol=str(hit.get("symbol") or signal.instrument_id),
                )
                dispatches = await self._alert_dispatcher.dispatch(subscription, signal)
                actions.append(
                    ExecutionActionResult(
                        instrument_id=signal.instrument_id,
                        signal_kind=kind,
                        status="alert_dispatched",
                        dispatches=dispatches,
                    )
                )
                continue

            if policy.mode == "paper_auto":
                action = await self._execute_paper_trade(
                    policy,
                    signal,
                    hit=hit,
                    sizing_value=sizing_value,
                )
                actions.append(action)
                continue

            actions.append(
                ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=kind,
                    status="skipped",
                    reason=f"mode no soportado: {policy.mode}",
                )
            )

        return ExecutionRouteResult(policy_id=policy.id, mode=policy.mode, actions=actions)

    async def _emit_signal(self, signal: SignalEventV1, policy: ExecutionPolicyRecord) -> None:
        if self._event_bus is None:
            return
        await self._event_bus.publish(
            "signal.emitted",
            signal_event_payload(signal, policyId=policy.id, policyMode=policy.mode),
            correlation_id=signal.id or None,
        )

    async def _has_validated_backtest(self, strategy_definition_id: str) -> bool:
        runs = await self._backtests.list_runs(limit=200)
        return any(
            run.strategy_definition_id == strategy_definition_id and run.manifest is not None
            for run in runs
        )

    async def _resolve_sizing_value(self, policy: ExecutionPolicyRecord) -> float:
        if not policy.strategy_definition_id:
            return 1000.0
        strategy = await self._strategies.get_definition(policy.strategy_definition_id)
        if strategy is None:
            return 1000.0
        sizing = strategy.definition.get("sizing") or {}
        mode = str(sizing.get("mode") or "fixed_cash")
        value = float(sizing.get("value") or 1000)
        if mode == "percent_equity" and policy.account_id:
            summary = await self._portfolio_summary.execute(account_id=policy.account_id)
            return max(summary.total_equity * value / 100.0, 0.0)
        return max(value, 0.0)

    async def _execute_paper_trade(
        self,
        policy: ExecutionPolicyRecord,
        signal: SignalEventV1,
        *,
        hit: dict[str, Any] | None = None,
        sizing_value: float,
    ) -> ExecutionActionResult:
        if not policy.account_id:
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="skipped",
                reason="accountId no configurado",
            )

        scope = await self._accounts.resolve_scope(policy.account_id)
        if scope.account.type not in PAPER_ACCOUNT_TYPES:
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="skipped",
                reason="La cuenta no es paper/simulated",
            )

        trade_type = signal_kind_to_trade_type(str(signal.kind))
        if trade_type is None:
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="skipped",
                reason="Señal watch sin acción de trading",
            )

        price = float(signal.price)
        if price <= 0:
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="skipped",
                reason="Precio de señal inválido",
            )

        summary = await self._portfolio_summary.execute(account_id=policy.account_id)

        quantity: float
        if trade_type == "sell" and str(signal.kind) == "exit":
            position = next(
                (item for item in summary.positions if item.instrument_id == signal.instrument_id),
                None,
            )
            if position is None or position.quantity <= 0:
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=str(signal.kind),
                    status="skipped",
                    reason="Sin posición abierta para exit",
                )
            quantity = float(position.quantity)
        else:
            quantity = sizing_value / price
            if quantity <= 0:
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=str(signal.kind),
                    status="skipped",
                    reason="Cantidad calculada inválida",
                )

        if self._enforce_cognitive_gate:
            symbol = signal.instrument_id  # fallback; UI hits pueden enriquecer después
            profile = None
            if self._profile_store is not None and scope.account.active_profile_id:
                profile = await self._profile_store.get(scope.account.active_profile_id)
            equity = float(summary.total_equity)
            initial = float(scope.account.initial_deposit or 0.0)
            from bolsa_application.account_drawdown import GLOBAL_EQUITY_MARK_BOOK

            account_key = policy.account_id or "default"
            # Hidratar marcas desde settings_json (cross-restart)
            try:
                raw_settings = await self._accounts.get_settings_json(account_key)
                GLOBAL_EQUITY_MARK_BOOK.load_from_settings(account_key, raw_settings)
            except Exception:  # noqa: BLE001
                pass

            dds = GLOBAL_EQUITY_MARK_BOOK.update(
                account_key,
                equity,
                initial_deposit=initial if initial > 0 else None,
            )
            # Persistir marcas (best-effort)
            try:
                await self._accounts.merge_settings_json(
                    account_key,
                    GLOBAL_EQUITY_MARK_BOOK.export_settings_fragment(account_key),
                )
            except Exception:  # noqa: BLE001
                pass
            guard_decision = check_opening(
                profile=profile,
                instrument_id=signal.instrument_id,
                symbol=symbol,
                trade_type=trade_type,
                quantity=quantity,
                price=price,
                signal_kind=str(signal.kind),
                equity=equity,
                open_positions_count=len(summary.positions),
                event_calendar=self._event_calendar,
                auto_live=False,  # paper_auto ≠ live; D3 auto-live cuando mode=live_auto
                account_daily_drawdown_pct=dds.daily_pct,
                account_weekly_drawdown_pct=dds.weekly_pct,
                account_max_drawdown_pct=dds.max_pct,
                kill_switch=bool(get_settings().risk_kill_switch),
            )
            guard = guard_decision.guard
            if guard is not None:
                await self._persist_gate_memory(
                    guard,
                    account_id=policy.account_id,
                    symbol=symbol,
                    execution_status="gate_pending_trade",
                    lineage={
                        "signalId": signal.id,
                        "strategyDefinitionId": signal.strategy_definition_id,
                        "policyId": policy.id,
                        "policyMode": policy.mode,
                        "dataVersion": signal.data_version,
                        "scanId": None if hit is None else hit.get("scanId"),
                        "featureSetHash": signal.indicator_snapshot_hash,
                        "drawdowns": dds.to_dict(),
                        "riskEngine": guard_decision.to_dict(),
                    },
                )
            if not guard_decision.allowed:
                if self._event_bus is not None:
                    await self._event_bus.publish(
                        "execution.order_vetoed",
                        {
                            **signal_event_payload(signal),
                            "policyId": policy.id,
                            "accountId": policy.account_id,
                            "tradeType": trade_type,
                            "quantity": quantity,
                            "cognitiveGate": guard_decision.to_dict(),
                            "riskEngine": guard_decision.to_dict(),
                        },
                        correlation_id=signal.id or None,
                    )
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=str(signal.kind),
                    status="skipped",
                    reason=f"Risk Engine: {'; '.join(guard_decision.reasons)}",
                )

        try:
            if self._event_bus is not None:
                await self._event_bus.publish(
                    "execution.order_requested",
                    {
                        **signal_event_payload(signal),
                        "policyId": policy.id,
                        "accountId": policy.account_id,
                        "tradeType": trade_type,
                        "quantity": quantity,
                    },
                    correlation_id=signal.id or None,
                )
            result = await self._execute_trade.execute(
                instrument_id=signal.instrument_id,
                trade_type=trade_type,
                quantity=quantity,
                price=price,
                account_id=policy.account_id,
            )
        except ValueError as exc:
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="skipped",
                reason=str(exc),
            )

        if self._event_bus is not None:
            await self._event_bus.publish(
                "execution.order_filled",
                {
                    **signal_event_payload(signal),
                    "policyId": policy.id,
                    "accountId": policy.account_id,
                    "transactionId": result.transaction.id,
                    "tradeType": trade_type,
                    "quantity": quantity,
                },
                correlation_id=result.transaction.id,
            )

        return ExecutionActionResult(
            instrument_id=signal.instrument_id,
            signal_kind=str(signal.kind),
            status="trade_executed",
            transaction_id=result.transaction.id,
        )

    async def _evaluate_live_dry_run(
        self,
        policy: ExecutionPolicyRecord,
        signal: SignalEventV1,
        *,
        hit: dict[str, Any],
        sizing_value: float,
    ) -> ExecutionActionResult:
        """
        F4→F6 bridge: live_auto evalúa Gate + check_auto_live + manifest.
        Nunca envía órdenes a broker (blocked_no_broker implícito en PASS dry-run).
        """
        trade_type = signal_kind_to_trade_type(str(signal.kind))
        if trade_type is None:
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="skipped",
                reason="Señal watch sin acción de trading",
            )

        price = float(signal.price)
        if price <= 0:
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="skipped",
                reason="Precio de señal inválido",
            )

        if not policy.account_id:
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="live_dry_run_veto",
                reason="live_auto requiere accountId",
            )

        scope = await self._accounts.resolve_scope(policy.account_id)
        # Hasta F6 broker: live_auto solo dry-run; cuenta paper aceptada para simular el gate
        summary = await self._portfolio_summary.execute(account_id=policy.account_id)
        quantity = sizing_value / price if trade_type == "buy" or str(signal.kind) != "exit" else 0.0
        if str(signal.kind) == "exit":
            position = next(
                (item for item in summary.positions if item.instrument_id == signal.instrument_id),
                None,
            )
            quantity = float(position.quantity) if position else 0.0
        if quantity <= 0 and str(signal.kind) != "exit":
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="live_dry_run_veto",
                reason="Cantidad calculada inválida",
            )

        profile = None
        if self._profile_store is not None and scope.account.active_profile_id:
            profile = await self._profile_store.get(scope.account.active_profile_id)

        edge_report = None
        if self._cognitive_store is not None and policy.strategy_definition_id:
            try:
                from bolsa_application.cognitive_persistence import record_to_edge_report

                edge_rec = await self._cognitive_store.latest_edge_report(
                    strategy_or_signal_ref=policy.strategy_definition_id,
                    account_id=policy.account_id,
                )
                if edge_rec is not None:
                    edge_report = record_to_edge_report(edge_rec)
            except Exception:  # noqa: BLE001
                edge_report = None

        equity = float(summary.total_equity)
        initial = float(scope.account.initial_deposit or 0.0)
        from bolsa_application.account_drawdown import GLOBAL_EQUITY_MARK_BOOK

        account_key = policy.account_id
        try:
            raw_settings = await self._accounts.get_settings_json(account_key)
            GLOBAL_EQUITY_MARK_BOOK.load_from_settings(account_key, raw_settings)
        except Exception:  # noqa: BLE001
            pass
        dds = GLOBAL_EQUITY_MARK_BOOK.update(
            account_key,
            equity,
            initial_deposit=initial if initial > 0 else None,
        )
        try:
            await self._accounts.merge_settings_json(
                account_key,
                GLOBAL_EQUITY_MARK_BOOK.export_settings_fragment(account_key),
            )
        except Exception:  # noqa: BLE001
            pass

        guard_decision = check_opening(
            profile=profile,
            instrument_id=signal.instrument_id,
            symbol=str(hit.get("symbol") or signal.instrument_id),
            trade_type=trade_type,
            quantity=max(quantity, 1e-9),
            price=price,
            signal_kind=str(signal.kind),
            equity=equity,
            open_positions_count=len(summary.positions),
            event_calendar=self._event_calendar,
            auto_live=True,
            edge_report=edge_report,
            account_daily_drawdown_pct=dds.daily_pct,
            account_weekly_drawdown_pct=dds.weekly_pct,
            account_max_drawdown_pct=dds.max_pct,
            kill_switch=bool(get_settings().risk_kill_switch),
        )
        guard = guard_decision.guard
        if guard is not None:
            await self._persist_gate_memory(
                guard,
                account_id=policy.account_id,
                symbol=str(hit.get("symbol") or signal.instrument_id),
                execution_status="live_dry_run",
                lineage={
                    "signalId": signal.id,
                    "strategyDefinitionId": signal.strategy_definition_id,
                    "policyId": policy.id,
                    "policyMode": policy.mode,
                    "dataVersion": signal.data_version,
                    "scanId": hit.get("scanId"),
                    "featureSetHash": signal.indicator_snapshot_hash,
                    "drawdowns": dds.to_dict(),
                    "edgeReportId": None if edge_report is None else edge_report.edge_report_id,
                    "broker": "none",
                    "dryRun": True,
                    "riskEngine": guard_decision.to_dict(),
                },
            )

        if not guard_decision.allowed:
            if self._event_bus is not None:
                await self._event_bus.publish(
                    "execution.live_dry_run_vetoed",
                    {
                        **signal_event_payload(signal),
                        "policyId": policy.id,
                        "accountId": policy.account_id,
                        "cognitiveGate": guard_decision.to_dict(),
                        "riskEngine": guard_decision.to_dict(),
                    },
                    correlation_id=signal.id or None,
                )
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="live_dry_run_veto",
                reason=f"Risk Engine VETO: {'; '.join(guard_decision.reasons)}",
            )

        if self._event_bus is not None:
            await self._event_bus.publish(
                "execution.live_dry_run_pass",
                {
                    **signal_event_payload(signal),
                    "policyId": policy.id,
                    "accountId": policy.account_id,
                    "cognitiveGate": guard_decision.to_dict(),
                    "riskEngine": guard_decision.to_dict(),
                    "broker": "none",
                },
                correlation_id=signal.id or None,
            )
        return ExecutionActionResult(
            instrument_id=signal.instrument_id,
            signal_kind=str(signal.kind),
            status="live_dry_run_pass",
            reason="Gate+auto_live PASS — broker no cableado (F6); sin orden real",
        )


class ExecuteScanJobHits:
    """Ejecuta Scan Job Hits."""
    def __init__(
        self,
        scan_job_repo,
        router: ExecutionRouter,
    ) -> None:
        self._jobs = scan_job_repo
        self._router = router

    async def execute(self, job_id: str, policy_id: str) -> ExecutionRouteResult:
        job = await self._jobs.get_by_id(job_id)
        if job is None:
            raise ValueError("Scan job no encontrado")
        if job.status != "completed" or job.result is None:
            raise ValueError("Scan job no completado")
        hits = list(job.result.get("hits") or [])
        if not hits:
            raise ValueError("El scan no tiene hits para ejecutar")
        return await self._router.execute(policy_id, hits)
