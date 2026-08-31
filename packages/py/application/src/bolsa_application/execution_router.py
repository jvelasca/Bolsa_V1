"""Router de ejecución (scan hits → acciones).

Modos: inform/alert · ``paper_auto`` (fill DEMO vía Risk Engine) · ``live_auto`` dry-run.
A2: ``check_opening`` con kill switch efectivo + book maxOpen; DecisionSession en
DENY pre-Gate y en fill; claim de idempotencia AUTO antes del trade.
DS-05: aperturas pasan ``signal.timestamp`` + ``require_fresh_data=True`` al
mismo ``check_opening`` (VETO stale / missing).
DS-03: aperturas pasan tenure abierto desde BD + ``require_account_mandate=True``
(VETO sin mandato / mismatch estrategia AUTO).
V1.33 A-β: aperturas ``paper_auto`` exigen TradePlan TRIGGERED + ``risk_signature``
(paridad SEMI; solo salta Confirm). Sizing libro/% caja no es autoridad.
V1.33 A-δ: aperturas solo ``autoSource`` Estudio (``estudio_dictamen`` |
``estudio_alarma``). Exits/protect intactos (ExitPermission H2).

@see docs/engineering/risk-engine-or-re-2026-08-04.md
@see docs/engineering/camino-d-a2-a5-prep-2026-08-04.md
@see docs/engineering/estudio-operativa-auto-y-grafico-2026-08-28.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from bolsa_analytics.cognitive.edge_report import EdgeReport
from bolsa_analytics.cognitive.portfolio_fit import BasketPosition
from bolsa_analytics.cognitive.risk_signature import evaluate_risk_signature
from bolsa_analytics.cognitive.supervised_opening_sizing import (
    extract_hit_auto_source,
    extract_hit_trade_plan,
    is_allowed_auto_opening_source,
    resolve_supervised_opening_quantity,
)
from bolsa_analytics.signals.strategy import SignalEventV1
from bolsa_application.account_mandate_gate import AccountMandateLookup
from bolsa_application.accounts import ExecuteTrade, GetPortfolioSummary
from bolsa_application.auto_execute_idempotency import (
    as_of_from_iso,
    make_auto_execute_idempotency_key,
)
from bolsa_application.cognitive_persistence import CognitiveStore, memory_entry_to_record
from bolsa_application.events.payloads import signal_event_payload
from bolsa_application.events.platform_event_bus import PlatformEventBus
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.journal_writer import append_journal_event
from bolsa_application.operational_incident_store import (
    OperationalIncidentStore,
    sync_opening_incidents,
)
from bolsa_application.reconciliation_opening_gate import (
    LiveReconLookup,
    PortfolioReconLookup,
)
from bolsa_application.risk_engine import RiskDecision, check_opening
from bolsa_application.risk_runtime import (
    claim_auto_execute_idempotency,
    effective_kill_switch,
    release_auto_execute_idempotency,
)
from bolsa_application.trading_policy_guard import CognitiveGuardResult
from bolsa_domain.entities.execution_policy import ExecutionPolicyRecord
from bolsa_domain.entities.market_event import MarketEventCalendar
from bolsa_domain.platform_kernel import PAPER_ACCOUNT_TYPES
from bolsa_domain.repositories.execution_policy_repository import ExecutionPolicyRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_infrastructure.alerts.alert_channels import (
    AlertChannelDispatchResult,
    SignalAlertChannelDispatcher,
)
from bolsa_infrastructure.database.repositories.account_repository import (
    SqlAlchemyAccountRepository,
)
from bolsa_infrastructure.database.repositories.backtest_repository import (
    SqlAlchemyBacktestRepository,
)
from bolsa_infrastructure.database.repositories.scan_job_repository import (
    SqlAlchemyScanJobRepository,
)
from bolsa_infrastructure.database.repositories.signal_alert_repository import (
    SignalAlertSubscriptionRecord,
)


def _book_max_open_positions(policy: ExecutionPolicyRecord) -> int | None:
    """A2: tope Libro desde definition de la política (opcional)."""
    d = policy.definition or {}
    raw = d.get("bookMaxOpenPositions", d.get("maxOpenPositions"))
    if raw is None:
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _basket_positions_from_summary(summary: Any) -> list[BasketPosition] | None:
    """Construye la cesta de posiciones del Risk de cesta desde un PortfolioSummary.

    Nota: el `sector` viene resuelto desde `instruments.sector` en la capa de
    infraestructura (field `sector` de `Position`); si no está poblado, la
    posición entra su market_value como "unknown" en el agregado por sector.
    """
    positions = getattr(summary, "positions", None)
    if positions is None:
        return None
    return [
        BasketPosition(
            instrument_id=getattr(p, "instrument_id", ""),
            market_value=getattr(p, "market_value", None),
            sector=getattr(p, "sector", None),
        )
        for p in positions
    ]


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
    # V1.45 — ``reduce`` = sell parcial (qty en hit); ``exit`` = cierre pleno o qty clamp.
    if kind in ("entry_short", "exit", "reduce"):
        return "sell"
    return None


def resolve_exit_sell_quantity(
    *,
    open_qty: float,
    signal_kind: str,
    hit: dict[str, Any] | None,
) -> tuple[float | None, str | None]:
    """V1.45 — qty de sell para exit/reduce. (qty, error_reason)."""
    if open_qty <= 0:
        return None, "Sin posición abierta para exit"
    requested: float | None = None
    if isinstance(hit, dict):
        raw_qty = hit.get("quantity")
        if isinstance(raw_qty, (int, float)) and not isinstance(raw_qty, bool):
            requested = float(raw_qty)
        elif isinstance(hit.get("signal"), dict):
            sig_qty = hit["signal"].get("quantity")
            if isinstance(sig_qty, (int, float)) and not isinstance(sig_qty, bool):
                requested = float(sig_qty)
    kind = str(signal_kind)
    if kind == "reduce":
        if requested is None or requested <= 0:
            return None, "reduce_qty_required"
        qty = min(requested, open_qty)
    elif requested is not None and requested > 0:
        qty = min(requested, open_qty)
    else:
        qty = open_qty
    if qty <= 0:
        return None, "Cantidad de salida inválida"
    return qty, None


def _unsupported_short_skip(instrument_id: str, kind: str) -> ExecutionActionResult | None:
    if kind == "entry_short":
        return ExecutionActionResult(
            instrument_id=instrument_id,
            signal_kind=kind,
            status="skipped",
            reason="unsupported_short",
        )
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
        mandates: AccountMandateLookup | None = None,
        portfolio_recon: PortfolioReconLookup | None = None,
        live_recon: LiveReconLookup | None = None,
        incident_store: OperationalIncidentStore | None = None,
        journal_writer: Any | None = None,
        instrument_data_status: Any | None = None,
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
        self._mandates = mandates
        self._portfolio_recon = portfolio_recon
        self._live_recon = live_recon
        self._incident_store = incident_store
        self._journal_writer = journal_writer
        self._instrument_data_status = instrument_data_status

    async def _resolve_sanity_warnings(
        self, instrument_id: str
    ) -> tuple[str, ...] | RiskDecision:
        """Sanity de barras (split/dividendo). Indisponibilidad = veto fail-closed."""
        if self._instrument_data_status is None:
            return ()
        try:
            status = await self._instrument_data_status.execute(instrument_id)
            if status is None:
                return ()
            return tuple(getattr(status, "sanity_warnings", ()) or ())
        except Exception:  # noqa: BLE001
            return RiskDecision(
                verdict="DENY",
                reasons=("instrument_data_status:lookup_failed",),
                guard=None,
            )

    async def _resolve_recon_kwargs(
        self,
        account_id: str,
        *,
        broker_venue: str = "paper",
    ) -> dict[str, Any] | RiskDecision:
        """OR-4 — statuses para check_opening, o DENY si lookup falla."""
        portfolio_status = None
        live_status = None
        require = False
        if self._portfolio_recon is not None:
            require = True
            try:
                portfolio_status = await self._portfolio_recon.portfolio_recon_status(
                    account_id
                )
            except Exception:  # noqa: BLE001
                return RiskDecision(
                    verdict="DENY",
                    reasons=("reconciliation:portfolio_lookup_failed",),
                    guard=None,
                )
        venue = (broker_venue or "paper").strip().lower()
        if self._live_recon is not None and venue == "live":
            require = True
            try:
                live_status = await self._live_recon.live_recon_status(account_id)
            except Exception:  # noqa: BLE001
                return RiskDecision(
                    verdict="DENY",
                    reasons=("reconciliation:live_unavailable",),
                    guard=None,
                )
        incident_status = None
        require_incident = False
        if self._incident_store is not None:
            require_incident = True
            try:
                incident_status = await sync_opening_incidents(
                    self._incident_store,
                    account_id=account_id,
                    portfolio_recon_status=portfolio_status,
                    live_recon_status=live_status,
                    broker_venue=venue,
                )
            except Exception:  # noqa: BLE001
                return RiskDecision(
                    verdict="DENY",
                    reasons=("incident:lookup_failed",),
                    guard=None,
                )
        return {
            "portfolio_recon_status": portfolio_status,
            "live_recon_status": live_status,
            "broker_venue": venue,
            "require_recon_veto": require,
            "incident_status": incident_status,
            "require_incident_veto": require_incident,
        }

    async def _resolve_account_mandate_for_opening(
        self,
        account_id: str,
        instrument_id: str,
    ) -> tuple[bool, str | None, bool] | None:
        """DS-03 — tenure abierto. ``None`` = lookup falló (fail-closed)."""
        if self._mandates is None:
            return False, None, False
        try:
            has_open, strategy_id = await self._mandates.get_open_mandate_for_instrument(
                account_id,
                instrument_id,
            )
            return has_open, strategy_id, True
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _proposal_strategy_id(signal: SignalEventV1) -> str | None:
        raw = getattr(signal, "strategy_definition_id", None)
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    async def _publish_policy_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        policy: ExecutionPolicyRecord,
        *,
        correlation_id: str | None = None,
    ) -> None:
        if self._event_bus is None:
            return
        await self._event_bus.publish(
            event_type,
            payload,
            correlation_id=correlation_id,
            user_id=policy.user_id,
        )

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

    async def _persist_risk_session(
        self,
        *,
        kind: Literal["paper_auto", "live_dry_run"],
        instrument_id: str,
        account_id: str | None,
        symbol: str | None,
        risk_decision: Any,
        execution_status: str,
        lineage: dict[str, Any] | None = None,
        decision_id: str | None = None,
    ) -> None:
        """OR-T6: DecisionSession también en DENY pre-Gate (kill switch / maxOpen) y fills."""
        if self._cognitive_store is None:
            return
        try:
            from bolsa_analytics.cognitive.decision_session import build_auto_session
            from bolsa_application.cognitive_persistence import decision_session_to_record

            session = build_auto_session(
                kind=kind,
                instrument_id=instrument_id,
                account_id=account_id,
                symbol=symbol,
                policy_gate={
                    "riskEngine": (
                        risk_decision.to_dict()
                        if hasattr(risk_decision, "to_dict")
                        else risk_decision
                    )
                },
                execution={
                    "status": execution_status,
                    "mode": kind,
                },
                lineage=lineage,
                decision_id=decision_id,
            )
            await self._cognitive_store.append_decision_session(
                decision_session_to_record(session)
            )
        except Exception:  # noqa: BLE001
            return

    async def execute(self, policy_id: str, hits: list[dict[str, Any]]) -> ExecutionRouteResult:
        policy = await self._policies.get_policy(policy_id)
        if policy is None:
            raise ValueError("Política de ejecución no encontrada")
        if not policy.enabled:
            raise ValueError("Política de ejecución deshabilitada")

        from bolsa_application.paper_auto_http_gate import require_http_paper_auto_env

        require_http_paper_auto_env(policy.mode)

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
                short_skip = _unsupported_short_skip(signal.instrument_id, kind)
                if short_skip is not None:
                    actions.append(short_skip)
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
            short_skip = _unsupported_short_skip(signal.instrument_id, kind)
            if short_skip is not None:
                actions.append(short_skip)
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
        await self._publish_policy_event(
            "signal.emitted",
            signal_event_payload(signal, policyId=policy.id, policyMode=policy.mode),
            policy,
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

    async def _resolve_edge_report(
        self, policy: ExecutionPolicyRecord
    ) -> EdgeReport | None:
        if self._cognitive_store is None or not policy.strategy_definition_id:
            return None
        try:
            from bolsa_application.cognitive_persistence import record_to_edge_report

            edge_rec = await self._cognitive_store.latest_edge_report(
                strategy_or_signal_ref=policy.strategy_definition_id,
                account_id=policy.account_id,
            )
            if edge_rec is not None:
                return record_to_edge_report(edge_rec)
        except Exception:  # noqa: BLE001
            return None
        return None

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
        opening_trade_plan: dict[str, Any] | None = None
        sell_kind = str(signal.kind)
        if trade_type == "sell" and sell_kind in ("exit", "reduce"):
            position = next(
                (item for item in summary.positions if item.instrument_id == signal.instrument_id),
                None,
            )
            if position is None or position.quantity <= 0:
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=sell_kind,
                    status="skipped",
                    reason="Sin posición abierta para exit",
                )
            open_qty = float(position.quantity)
            # V1.45 — qty explícita en hit (reduce); clamp ≤ open. Sin qty + exit = full.
            quantity, qty_err = resolve_exit_sell_quantity(
                open_qty=open_qty,
                signal_kind=sell_kind,
                hit=hit if isinstance(hit, dict) else None,
            )
            if quantity is None:
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=sell_kind,
                    status="skipped",
                    reason=qty_err or "Cantidad de salida inválida",
                )
        else:
            # V1.33 A-β / A-δ — apertura: Estudio + TradePlan TRIGGERED + risk_signature.
            # No sizing libro (A-γ rechazada). ``sizing_value`` solo aplica a live_auto dry-run.
            _ = sizing_value
            auto_source = extract_hit_auto_source(hit if isinstance(hit, dict) else None)
            if not is_allowed_auto_opening_source(auto_source):
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=str(signal.kind),
                    status="skipped",
                    reason="auto_source_not_estudio",
                )
            opening_trade_plan = extract_hit_trade_plan(
                hit if isinstance(hit, dict) else None
            )
            plan_qty = resolve_supervised_opening_quantity(opening_trade_plan)
            if plan_qty is None:
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=str(signal.kind),
                    status="skipped",
                    reason="no_tradeplan",
                )
            plan_stop = None
            if isinstance(opening_trade_plan, dict):
                raw_stop = opening_trade_plan.get("structuralStop")
                if isinstance(raw_stop, (int, float)) and not isinstance(raw_stop, bool):
                    plan_stop = float(raw_stop)
            sig = evaluate_risk_signature(
                opening_trade_plan,
                signed_qty=plan_qty,
                signed_price=price,
                signed_stop=plan_stop,
                override_reason=None,
                require_triggered_plan=True,
            )
            if sig.get("allowed") is not True:
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=str(signal.kind),
                    status="skipped",
                    reason="risk_signature",
                )
            quantity = float(plan_qty)
            if quantity <= 0:
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=str(signal.kind),
                    status="skipped",
                    reason="Cantidad calculada inválida",
                )

        # OR-T4: clave de idempotencia del trade (día×política×kind). Se usa enviada a
        # ExecuteTrade como idempotency_key (B-4) y, si el cognitive gate está activo,
        # también como claim AUTO. Se calcula a nivel de función para que el guard DB de
        # idempotencia se active siempre (incluso con gate desactivado). Se inicializa
        # aqui también `claimed` para que el release del except ValueError nunca encuentre
        # la variable sin definir cuando el gate está desactivado.
        idem_key = make_auto_execute_idempotency_key(
            signal.instrument_id,
            as_of_from_iso(getattr(signal, "timestamp", None)),
            policy.id,
            str(signal.kind),
        )
        claimed = False

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
            mandate_ctx = await self._resolve_account_mandate_for_opening(
                policy.account_id or "",
                signal.instrument_id,
            )
            if mandate_ctx is None:
                guard_decision = RiskDecision(
                    verdict="DENY",
                    reasons=("account_mandate:lookup_failed",),
                    guard=None,
                )
            else:
                has_open_mandate, mandate_strategy_id, require_account_mandate = mandate_ctx
                recon = await self._resolve_recon_kwargs(
                    policy.account_id or "",
                    broker_venue="paper",
                )
                edge_report = await self._resolve_edge_report(policy)
                if isinstance(recon, RiskDecision):
                    guard_decision = recon
                else:
                    sanity = await self._resolve_sanity_warnings(signal.instrument_id)
                    if isinstance(sanity, RiskDecision):
                        guard_decision = sanity
                    else:
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
                            auto_live=False,  # paper_auto ≠ live
                            enforce_edge_thresholds=True,
                            edge_report=edge_report,
                            account_daily_drawdown_pct=dds.daily_pct,
                            account_weekly_drawdown_pct=dds.weekly_pct,
                            account_max_drawdown_pct=dds.max_pct,
                            kill_switch=await effective_kill_switch(),
                            book_max_open_positions=_book_max_open_positions(policy),
                            portfolio_positions=_basket_positions_from_summary(summary),
                            proposal_sector=(
                                hit.get("sector") if isinstance(hit, dict) else None
                            ),
                            last_bar_timestamp=getattr(signal, "timestamp", None) or None,
                            require_fresh_data=True,
                            has_open_mandate=has_open_mandate,
                            mandate_strategy_id=mandate_strategy_id,
                            require_account_mandate=require_account_mandate,
                            proposal_strategy_id=self._proposal_strategy_id(signal),
                            sanity_warnings=sanity,
                            **recon,
                        )
            auto_decision_id = str(signal.id or idem_key)
            await append_journal_event(
                self._journal_writer,
                event_type="gate_evaluated",
                decision_id=auto_decision_id,
                account_id=policy.account_id,
                instrument_id=signal.instrument_id,
                payload={
                    "allowed": guard_decision.allowed,
                    "verdict": guard_decision.verdict,
                    "reasons": list(guard_decision.reasons),
                },
            )
            guard = guard_decision.guard
            lineage_base = {
                "signalId": signal.id,
                "strategyDefinitionId": signal.strategy_definition_id,
                "policyId": policy.id,
                "policyMode": policy.mode,
                "dataVersion": signal.data_version,
                "scanId": None if hit is None else hit.get("scanId"),
                "featureSetHash": signal.indicator_snapshot_hash,
                "drawdowns": dds.to_dict(),
                "riskEngine": guard_decision.to_dict(),
            }
            if guard is not None:
                await self._persist_gate_memory(
                    guard,
                    account_id=policy.account_id,
                    symbol=symbol,
                    execution_status="gate_pending_trade",
                    lineage=lineage_base,
                )
            elif not guard_decision.allowed:
                await self._persist_risk_session(
                    kind="paper_auto",
                    instrument_id=signal.instrument_id,
                    account_id=policy.account_id,
                    symbol=symbol,
                    risk_decision=guard_decision,
                    execution_status="vetoed",
                    lineage=lineage_base,
                )
            if not guard_decision.allowed:
                await self._publish_policy_event(
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
                    policy,
                    correlation_id=signal.id or None,
                )
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=str(signal.kind),
                    status="skipped",
                    reason=f"Risk Engine: {'; '.join(guard_decision.reasons)}",
                )

            # OR-T4: claim AUTO idempotency before fill (mismo día×política×kind).
            claimed = await claim_auto_execute_idempotency(idem_key)
            if not claimed:
                await self._persist_risk_session(
                    kind="paper_auto",
                    instrument_id=signal.instrument_id,
                    account_id=policy.account_id,
                    symbol=symbol,
                    risk_decision=guard_decision,
                    execution_status="idempotent_skip",
                    lineage={**lineage_base, "idempotencyKey": idem_key},
                )
                return ExecutionActionResult(
                    instrument_id=signal.instrument_id,
                    signal_kind=str(signal.kind),
                    status="skipped",
                    reason=f"Idempotencia AUTO: ya ejecutado ({idem_key})",
                )

        try:
            await self._publish_policy_event(
                "execution.order_requested",
                {
                    **signal_event_payload(signal),
                    "policyId": policy.id,
                    "accountId": policy.account_id,
                    "tradeType": trade_type,
                    "quantity": quantity,
                },
                policy,
                correlation_id=signal.id or None,
            )
            result = await self._execute_trade.execute(
                instrument_id=signal.instrument_id,
                trade_type=trade_type,
                quantity=quantity,
                price=price,
                account_id=policy.account_id,
                idempotency_key=idem_key,
            )
            await append_journal_event(
                self._journal_writer,
                event_type="executed",
                decision_id=str(result.transaction.id),
                account_id=policy.account_id,
                instrument_id=signal.instrument_id,
                payload={
                    "status": "executed",
                    "transactionId": result.transaction.id,
                    "idempotencyKey": idem_key,
                },
            )
        except ValueError as exc:
            # El claim AUTO quedó tomado antes del fill (OR-T4). Si el fill falló
            # (no se ha ejecutado nada), liberarlo para permitir el reintento mismo
            # día×política×instrumento; no se ha movido dinero.
            if claimed:
                await release_auto_execute_idempotency(idem_key)
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="skipped",
                reason=str(exc),
            )

        await self._publish_policy_event(
            "execution.order_filled",
            {
                **signal_event_payload(signal),
                "policyId": policy.id,
                "accountId": policy.account_id,
                "transactionId": result.transaction.id,
                "tradeType": trade_type,
                "quantity": quantity,
            },
            policy,
            correlation_id=result.transaction.id,
        )

        await self._persist_risk_session(
            kind="paper_auto",
            instrument_id=signal.instrument_id,
            account_id=policy.account_id,
            symbol=str(signal.instrument_id),
            risk_decision={"verdict": "ALLOW", "reasons": ["fill"]},
            execution_status="accepted",
            lineage={
                "signalId": signal.id,
                "policyId": policy.id,
                "policyMode": policy.mode,
                "transactionId": result.transaction.id,
            },
            decision_id=result.transaction.id,
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

        mandate_ctx = await self._resolve_account_mandate_for_opening(
            policy.account_id,
            signal.instrument_id,
        )
        if mandate_ctx is None:
            guard_decision = RiskDecision(
                verdict="DENY",
                reasons=("account_mandate:lookup_failed",),
                guard=None,
            )
        else:
            has_open_mandate, mandate_strategy_id, require_account_mandate = mandate_ctx
            recon = await self._resolve_recon_kwargs(
                policy.account_id or "",
                broker_venue="live",
            )
            if isinstance(recon, RiskDecision):
                guard_decision = recon
            else:
                sanity = await self._resolve_sanity_warnings(signal.instrument_id)
                if isinstance(sanity, RiskDecision):
                    guard_decision = sanity
                else:
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
                        kill_switch=await effective_kill_switch(),
                        book_max_open_positions=_book_max_open_positions(policy),
                        portfolio_positions=_basket_positions_from_summary(summary),
                        proposal_sector=hit.get("sector"),
                        last_bar_timestamp=getattr(signal, "timestamp", None) or None,
                        require_fresh_data=True,
                        has_open_mandate=has_open_mandate,
                        mandate_strategy_id=mandate_strategy_id,
                        require_account_mandate=require_account_mandate,
                        proposal_strategy_id=self._proposal_strategy_id(signal),
                        sanity_warnings=sanity,
                        **recon,
                    )
        guard = guard_decision.guard
        lineage_live = {
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
        }
        if guard is not None:
            await self._persist_gate_memory(
                guard,
                account_id=policy.account_id,
                symbol=str(hit.get("symbol") or signal.instrument_id),
                execution_status="live_dry_run",
                lineage=lineage_live,
            )
        elif not guard_decision.allowed:
            await self._persist_risk_session(
                kind="live_dry_run",
                instrument_id=signal.instrument_id,
                account_id=policy.account_id,
                symbol=str(hit.get("symbol") or signal.instrument_id),
                risk_decision=guard_decision,
                execution_status="vetoed",
                lineage=lineage_live,
            )

        if not guard_decision.allowed:
            await self._publish_policy_event(
                "execution.live_dry_run_vetoed",
                {
                    **signal_event_payload(signal),
                    "policyId": policy.id,
                    "accountId": policy.account_id,
                    "cognitiveGate": guard_decision.to_dict(),
                    "riskEngine": guard_decision.to_dict(),
                },
                policy,
                correlation_id=signal.id or None,
            )
            return ExecutionActionResult(
                instrument_id=signal.instrument_id,
                signal_kind=str(signal.kind),
                status="live_dry_run_veto",
                reason=f"Risk Engine VETO: {'; '.join(guard_decision.reasons)}",
            )

        await self._publish_policy_event(
            "execution.live_dry_run_pass",
            {
                **signal_event_payload(signal),
                "policyId": policy.id,
                "accountId": policy.account_id,
                "cognitiveGate": guard_decision.to_dict(),
                "riskEngine": guard_decision.to_dict(),
                "broker": "none",
            },
            policy,
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
        scan_job_repo: SqlAlchemyScanJobRepository,
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
