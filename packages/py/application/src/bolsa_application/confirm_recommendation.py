"""F3 — Confirm Recommendation → OrderIntent (+ opcional trade) + DecisionSession.

DEX-4: Confirm = **orquestador**. La lógica vive en
``bolsa_application.confirm`` (Identity / RiskGate / OpeningGate / ExitGate /
Execution / SubmitIntent / PositionSync). Política y semántica OR-1…OR-4 /
DEX-1…3 intactas; esta firma sigue siendo la única transaccional SEMI.

Decision Spine — rebanada confirm SEMI (D2 + Escalón 3/D1 + cierre de la deuda):

- **D2 (contrato):** cuando la sesión `propose` persiste un `DecisionPackage`,
  es la fuente de verdad de la **identidad** (dirección + instrumento) del intent;
  si diverge → `rejected_by_gate`/`decision_package_conflict` fail-closed.
- **Escalón 3/D1 (VETO de cesta):** OpeningGate → `check_opening` / `allow_opening_fill`.
- **P2 firma de riesgo:** RiskGate → `risk_signature`.
- **P3 cadena de salida:** ExitGate → ExitPermission / protect.
- **OR-1/OR-2/DEX-1:** Execution + SubmitIntent (replay · durable · UNKNOWN).
- **OI-1:** PositionSync post-fill / exit.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from bolsa_analytics.cognitive.decision_session import (
    attach_execution_to_payload,
    build_auto_session,
)
from bolsa_analytics.cognitive.execution_record import build_execution_record
from bolsa_analytics.cognitive.exit_risk_signature import evaluate_exit_risk_signature
from bolsa_analytics.cognitive.order_intent import intent_from_recommendation
from bolsa_analytics.cognitive.paper_order import stable_order_id_from_decision
from bolsa_analytics.cognitive.recommendation import Recommendation
from bolsa_analytics.cognitive.risk_signature import apply_signed_levels_to_trade_plan
from bolsa_application.account_mandate_gate import AccountMandateLookup
from bolsa_application.accounts import GetPortfolioSummary
from bolsa_application.broker_adapter import IBrokerAdapter, resolve_broker_adapter
from bolsa_application.broker_venue_runtime import (
    account_broker_venue_from_settings,
    effective_broker_venue_async,
)
from bolsa_application.cognitive_persistence import CognitiveStore, decision_session_to_record
from bolsa_application.confirm.actions import (
    _TRADE_ACTIONS,
    is_closing_action,
    is_opening_action,
)
from bolsa_application.confirm.execution import ExecutionCoordinator
from bolsa_application.confirm.exit_gate import ExitGateCoordinator
from bolsa_application.confirm.identity import (
    IdentityCoordinator,
    build_recommendation_from_raw,
    extract_operativa_exit_meta,
    extract_operativa_protect_meta,
    price_revalidation_reason,
    recommendation_is_expired,
    required_fill_side,
    resolve_confirm_trade_plan,
    resolve_protect_revision_origin,
)
from bolsa_application.confirm.opening_gate import OpeningGateCoordinator
from bolsa_application.confirm.position_sync import PositionSyncCoordinator
from bolsa_application.confirm.risk_gate import (
    RiskGateCoordinator,
)
from bolsa_application.confirm.submit_intent import SubmitIntentCoordinator
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.journal_writer import (
    append_journal_event,
    attribution_setup_payload,
)
from bolsa_application.opening_permission import (
    AccountScopeLookup,
    InstrumentSectorLookup,
    LatestBarLookup,
)
from bolsa_application.persist_position_from_exit import row_position_state
from bolsa_application.reconciliation_opening_gate import (
    LiveReconLookup,
    PortfolioReconLookup,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord

# Compat: nombres privados históricos usados por tests internos / re-exports.
_OPENING_ACTIONS = {"recommend_long", "recommend_short"}
_CLOSING_ACTIONS = {"exit_hint", "reduce"}
_is_opening_action = is_opening_action
_is_closing_action = is_closing_action

# Re-exports públicos (API estable pre-DEX-4).
from bolsa_application.confirm.actions import (  # noqa: E402
    PRICE_REVALIDATION_MAX_REL_DEVIATION,
)
from bolsa_application.confirm.identity import (  # noqa: E402
    resolve_session_decision_package,
)
from bolsa_application.confirm.risk_gate import (  # noqa: E402
    risk_signature_reject_reason,
)

__all__ = [
    "ConfirmRecommendationIntent",
    "PRICE_REVALIDATION_MAX_REL_DEVIATION",
    "extract_operativa_protect_meta",
    "extract_operativa_exit_meta",
    "price_revalidation_reason",
    "recommendation_is_expired",
    "resolve_confirm_trade_plan",
    "resolve_session_decision_package",
    "risk_signature_reject_reason",
]


def _attach_execution_record(result: dict[str, Any]) -> None:
    """OI-3 — foto honesta del intento. Protect no es fill ledger."""
    trade = result.get("trade")
    if not isinstance(trade, dict):
        return
    status = trade.get("status")
    reason = trade.get("reason") if isinstance(trade.get("reason"), str) else None
    tx = trade.get("transactionId")
    tx_id = tx if isinstance(tx, str) and tx.strip() else None
    if status == "executed":
        rec = build_execution_record(filled=True, transaction_id=tx_id)
    elif status == "unknown":
        rec = build_execution_record(send_attempted=True, exception=reason)
    elif status == "error":
        rec = build_execution_record(exception=reason)
    elif status in {"rejected_by_gate", "skipped"}:
        rec = build_execution_record(not_executed_reason=reason)
    else:
        return
    result["executionRecord"] = rec.to_dict()


# Re-exports / aliases históricos (tests / introspección).
_required_fill_side = required_fill_side


def _reject_reason_for_execute(
    *,
    action: str,
    intent_side: str,
    intent_instrument_id: str,
    package: dict[str, Any] | None,
) -> str | None:
    from bolsa_application.confirm.identity import reject_reason_for_execute

    return reject_reason_for_execute(
        action=action,
        intent_side=intent_side,
        intent_instrument_id=intent_instrument_id,
        package=package,
    )


class ConfirmRecommendationIntent:
    """Humano confirma Recommendation; audita Session (update o append confirm).

    DEX-4 — orquesta Identity / RiskGate / OpeningGate / ExitGate / Execution /
    SubmitIntent / PositionSync. No contiene la política de cada gate.
    """

    def __init__(
        self,
        *,
        cognitive_store: CognitiveStore | None = None,
        execute_trade: Any | None = None,
        portfolio_summary: GetPortfolioSummary | None = None,
        instruments: InstrumentSectorLookup | None = None,
        profile_store: InvestorProfileStore | None = None,
        accounts: AccountScopeLookup | None = None,
        ohlcv: LatestBarLookup | None = None,
        mandates: AccountMandateLookup | None = None,
        portfolio_recon: PortfolioReconLookup | None = None,
        live_recon: LiveReconLookup | None = None,
        incident_store: Any | None = None,
        instrument_data_status: Any | None = None,
        journal_writer: Any | None = None,
        position_from_fill: Any | None = None,
        position_from_exit: Any | None = None,
        position_from_protect: Any | None = None,
        lifecycle_append: Any | None = None,
        lifecycle_outbox: Any | None = None,
        broker_adapter: IBrokerAdapter | None = None,
        submit_intent_store: Any | None = None,
    ) -> None:
        self._store = cognitive_store
        self._execute_trade = execute_trade
        self._broker_adapter = broker_adapter
        self._submit_intent_store = submit_intent_store
        self._portfolio_summary = portfolio_summary
        self._instruments = instruments
        self._profile_store = profile_store
        self._accounts = accounts
        self._ohlcv = ohlcv
        self._mandates = mandates
        self._portfolio_recon = portfolio_recon
        self._live_recon = live_recon
        self._incident_store = incident_store
        self._instrument_data_status = instrument_data_status
        self._journal_writer = journal_writer
        self._position_from_fill = position_from_fill
        self._position_from_exit = position_from_exit
        self._position_from_protect = position_from_protect
        self._lifecycle_append = lifecycle_append
        self._lifecycle_outbox = lifecycle_outbox

        self._identity = IdentityCoordinator(
            cognitive_store=cognitive_store,
            ohlcv=ohlcv,
            position_from_exit=position_from_exit,
        )
        self._opening = OpeningGateCoordinator(
            portfolio_summary=portfolio_summary,
            instruments=instruments,
            profile_store=profile_store,
            accounts=accounts,
            ohlcv=ohlcv,
            mandates=mandates,
            portfolio_recon=portfolio_recon,
            live_recon=live_recon,
            incident_store=incident_store,
            instrument_data_status=instrument_data_status,
            resolve_broker_venue=self._resolve_broker_venue_for_account,
        )
        self._risk = RiskGateCoordinator()
        self._exit = ExitGateCoordinator(
            position_from_exit=position_from_exit,
            position_from_protect=position_from_protect,
        )
        self._execution = ExecutionCoordinator(
            execute_trade=execute_trade,
            broker_adapter=broker_adapter,
            resolve_broker_adapter=self._resolve_broker_adapter_for_account,
        )
        self._submit = SubmitIntentCoordinator(
            submit_intent_store=submit_intent_store,
            resolve_broker_venue=self._resolve_broker_venue_for_account,
        )
        self._positions = PositionSyncCoordinator(
            position_from_fill=position_from_fill,
            position_from_exit=position_from_exit,
            lifecycle_append=lifecycle_append,
            lifecycle_outbox=lifecycle_outbox,
        )

    async def _resolve_broker_venue_for_account(self, account_id: str) -> str:
        account_venue: str | None = None
        getter = getattr(self._accounts, "get_settings_json", None) if self._accounts else None
        if getter is not None:
            try:
                settings = await getter(account_id)
                account_venue = account_broker_venue_from_settings(settings)
            except Exception:  # noqa: BLE001
                account_venue = None
        return await effective_broker_venue_async(account_venue=account_venue)

    async def _resolve_broker_adapter_for_account(self, account_id: str) -> IBrokerAdapter:
        """PA-1: adapter inyectado (tests) o lazy resolve tras account_id."""
        if self._broker_adapter is not None:
            return self._broker_adapter
        account_venue: str | None = None
        getter = getattr(self._accounts, "get_settings_json", None) if self._accounts else None
        if getter is not None:
            try:
                settings = await getter(account_id)
                account_venue = account_broker_venue_from_settings(settings)
            except Exception:  # noqa: BLE001
                account_venue = None
        venue = await effective_broker_venue_async(account_venue=account_venue)
        return resolve_broker_adapter(self._execute_trade, venue=venue)

    async def execute(
        self,
        *,
        recommendation_raw: dict[str, Any],
        account_id: str,
        execute: bool = False,
        session_id: str | None = None,
        risk_override_reason: str | None = None,
        signed_stop: float | None = None,
    ) -> dict[str, Any]:
        raw = recommendation_raw
        rec = build_recommendation_from_raw(raw, account_id=account_id)
        intent = intent_from_recommendation(rec, account_id=account_id, authorized_by="human")
        result: dict[str, Any] = {
            "intent": {**intent.to_dict(), "contract": "absent"},
            "trade": None,
            "decisionSession": None,
        }

        # --- Identity: contrato + side + TradePlan + firma humana ---
        contract_status, package, session_record = await self._identity.resolve_package(
            session_id=session_id,
        )
        side_package = await self._identity.effective_package_for_side(
            rec=rec,
            account_id=account_id,
            package=package,
        )
        if is_closing_action(rec.action):
            _, required_side = required_fill_side(
                rec.action,
                None if side_package is None else side_package.get("action"),
            )
            if required_side is not None and intent.side != required_side:
                intent = replace(intent, side=required_side)  # type: ignore[arg-type]
                result["intent"] = {**intent.to_dict(), "contract": contract_status}
        result["intent"]["contract"] = contract_status
        result["tradePlan"] = resolve_confirm_trade_plan(
            raw=raw,
            rec=rec,
            package=package,
            session_record=session_record,
        )
        session_payload = (
            session_record.payload
            if session_record is not None and isinstance(session_record.payload, dict)
            else None
        )
        trade_plan_dict = (
            result["tradePlan"] if isinstance(result.get("tradePlan"), dict) else None
        )
        await append_journal_event(
            self._journal_writer,
            event_type=(
                "contract_verified"
                if contract_status == "present_verified"
                else "contract_absent"
            ),
            decision_id=rec.decision_id,
            session_id=session_id,
            account_id=account_id,
            instrument_id=rec.instrument_id,
            actor="human",
            payload={"contract": contract_status},
        )
        await append_journal_event(
            self._journal_writer,
            event_type="human_confirm",
            decision_id=rec.decision_id,
            session_id=session_id,
            account_id=account_id,
            instrument_id=rec.instrument_id,
            actor="human",
            payload=attribution_setup_payload(
                trade_plan_dict,
                session_payload=session_payload,
                base={"execute": bool(execute)},
            ),
        )

        protect_meta = extract_operativa_protect_meta(raw)
        if execute and protect_meta is not None:
            await self._run_protect_path(
                result=result,
                rec=rec,
                intent=intent,
                account_id=account_id,
                session_id=session_id,
                contract_status=contract_status,
                protect_meta=protect_meta,
                trade_plan_dict=trade_plan_dict,
                session_payload=session_payload,
                risk_override_reason=risk_override_reason,
            )
        elif (
            execute
            and rec.action in _TRADE_ACTIONS
            and intent.side in {"buy", "sell"}
            and intent.quantity > 0
        ):
            await self._run_trade_path(
                result=result,
                rec=rec,
                intent=intent,
                account_id=account_id,
                session_id=session_id,
                contract_status=contract_status,
                package=package,
                side_package=side_package,
                trade_plan_dict=trade_plan_dict,
                session_payload=session_payload,
                risk_override_reason=risk_override_reason,
                signed_stop=signed_stop,
                exit_meta=extract_operativa_exit_meta(raw),
            )

        _attach_execution_record(result)

        execution = {
            "intent": result["intent"],
            "trade": result["trade"],
            "authorizedBy": "human",
        }

        if self._store is not None:
            try:
                session_payload_out = await self._persist_session(
                    session_id=session_id,
                    rec=rec,
                    account_id=account_id,
                    execution=execution,
                )
                result["decisionSession"] = session_payload_out
            except Exception:  # noqa: BLE001 — confirm no tumba por audit
                pass

        return result

    async def _run_protect_path(
        self,
        *,
        result: dict[str, Any],
        rec: Recommendation,
        intent: Any,
        account_id: str,
        session_id: str | None,
        contract_status: str,
        protect_meta: dict[str, Any],
        trade_plan_dict: dict[str, Any] | None,
        session_payload: dict[str, Any] | None,
        risk_override_reason: str | None,
    ) -> None:
        suggested_stop = float(protect_meta.get("suggestedStop") or rec.suggested_price or 0)
        if suggested_stop <= 0:
            result["trade"] = {
                "status": "skipped",
                "reason": "suggestedStop requerido para proteger",
            }
            return
        if not self._exit.protect_configured:
            result["trade"] = {
                "status": "skipped",
                "reason": "position_from_protect no configurado",
            }
            return
        row = await self._exit.get_open_for_protect(
            account_id=account_id,
            instrument_id=str(rec.instrument_id or ""),
        )
        state_blob = row_position_state(row)
        exit_perm = self._exit.protect_permission(
            state_blob,
            suggested_stop=suggested_stop,
        )
        if not exit_perm.allowed:
            result["trade"] = {
                "status": "rejected_by_gate",
                "reason": "exit_permission",
                "exitPermission": exit_perm.to_dict(),
            }
            result["intent"] = {
                **intent.to_dict(),
                "status": "rejected_by_gate",
                "contract": contract_status,
            }
            await append_journal_event(
                self._journal_writer,
                event_type="human_reject",
                decision_id=rec.decision_id,
                session_id=session_id,
                account_id=account_id,
                instrument_id=rec.instrument_id,
                actor="human",
                payload=attribution_setup_payload(
                    trade_plan_dict,
                    session_payload=session_payload,
                    base={
                        "reason": "exit_permission",
                        "status": "rejected_by_gate",
                        "exitPlanId": exit_perm.exit_plan_id,
                        "exitAction": exit_perm.action,
                        "exitReasons": list(exit_perm.reasons),
                    },
                ),
            )
            return

        revision_origin = resolve_protect_revision_origin(protect_meta)
        revision_reason = (
            "trail_confirm"
            if revision_origin == "trail"
            else None
        )
        position_persist: dict[str, Any] = {"status": "applied"}
        try:
            applied_row = await self._exit.persist_protect(
                account_id=account_id,
                instrument_id=str(rec.instrument_id or ""),
                suggested_stop=suggested_stop,
                override_reason=risk_override_reason,
                origin=revision_origin,
                reason=revision_reason,
            )
        except Exception as exc:  # noqa: BLE001
            position_persist = {"status": "error", "reason": str(exc)}
            result["trade"] = {"status": "skipped", "reason": "persist_error"}
            result["positionPersist"] = position_persist
            return

        if applied_row is None:
            position_persist = {"status": "skipped", "reason": "stop_not_applied"}
            result["trade"] = {"status": "skipped", "reason": "stop_not_applied"}
            result["positionPersist"] = position_persist
            return

        await append_journal_event(
            self._journal_writer,
            event_type="protect_applied",
            decision_id=rec.decision_id,
            session_id=session_id,
            account_id=account_id,
            instrument_id=rec.instrument_id,
            actor="human",
            payload=attribution_setup_payload(
                trade_plan_dict,
                session_payload=session_payload,
                base={
                    "suggestedStop": suggested_stop,
                    "currentStop": protect_meta.get("currentStop"),
                    "overrideReason": risk_override_reason,
                    "revisionOrigin": revision_origin,
                },
            ),
        )
        result["trade"] = {"status": "protect_applied"}
        result["intent"] = {
            **intent.to_dict(),
            "status": "executed",
            "contract": contract_status,
        }
        result["positionPersist"] = position_persist

    async def _run_trade_path(
        self,
        *,
        result: dict[str, Any],
        rec: Recommendation,
        intent: Any,
        account_id: str,
        session_id: str | None,
        contract_status: str,
        package: dict[str, Any] | None,
        side_package: dict[str, Any] | None,
        trade_plan_dict: dict[str, Any] | None,
        session_payload: dict[str, Any] | None,
        risk_override_reason: str | None,
        signed_stop: float | None = None,
        exit_meta: dict[str, Any] | None = None,
    ) -> None:
        price = float(rec.suggested_price or 0)

        # Identity pretrade (TTL / orphan / package / precio)
        reject_reason = _reject_reason_for_execute(
            action=rec.action,
            intent_side=intent.side,
            intent_instrument_id=intent.instrument_id,
            package=side_package,
        )
        if recommendation_is_expired(rec.expires_at):
            reject_reason = "expired"
        elif (
            reject_reason is None
            and is_opening_action(rec.action)
            and package is None
            and self._store is not None
        ):
            reject_reason = "orphan_opening_blocked"
        if (
            reject_reason is None
            and is_opening_action(rec.action)
            and self._ohlcv is not None
        ):
            last_close = await self._identity.resolve_latest_close(intent.instrument_id)
            reject_reason = price_revalidation_reason(price, last_close)

        if price <= 0 and reject_reason is None:
            result["trade"] = {
                "status": "skipped",
                "reason": "suggestedPrice requerido para ejecutar",
            }
            return

        if reject_reason is not None:
            await self._reject_gate(
                result=result,
                intent=intent,
                contract_status=contract_status,
                rec=rec,
                session_id=session_id,
                account_id=account_id,
                trade_plan_dict=trade_plan_dict,
                session_payload=session_payload,
                reason=reject_reason,
            )
            return

        # OpeningGate — risk_veto
        if (
            is_opening_action(rec.action)
            and self._portfolio_summary is not None
            and not await self._opening.allows_opening(
                rec=rec,
                intent=intent,
                price=price,
                account_id=account_id,
            )
        ):
            result["trade"] = {"status": "rejected_by_gate", "reason": "risk_veto"}
            result["intent"] = {
                **intent.to_dict(),
                "status": "rejected_by_gate",
                "contract": contract_status,
            }
            await append_journal_event(
                self._journal_writer,
                event_type="gate_evaluated",
                decision_id=rec.decision_id,
                session_id=session_id,
                account_id=account_id,
                instrument_id=rec.instrument_id,
                actor="human",
                payload=attribution_setup_payload(
                    trade_plan_dict,
                    session_payload=session_payload,
                    base={"allowed": False, "reason": "risk_veto"},
                ),
            )
            await append_journal_event(
                self._journal_writer,
                event_type="risk_veto",
                decision_id=rec.decision_id,
                session_id=session_id,
                account_id=account_id,
                instrument_id=rec.instrument_id,
                actor="human",
                payload=attribution_setup_payload(
                    trade_plan_dict,
                    session_payload=session_payload,
                    base={"reason": "risk_veto", "status": "rejected_by_gate"},
                ),
            )
            return

        # RiskGate — risk_signature (qty/price/stop firmados)
        if is_opening_action(rec.action) and self._risk.reject_reason(
            trade_plan=trade_plan_dict if isinstance(trade_plan_dict, dict) else None,
            signed_qty=float(intent.quantity),
            signed_price=price,
            override_reason=risk_override_reason,
            signed_stop=signed_stop,
        ) is not None:
            await self._reject_gate(
                result=result,
                intent=intent,
                contract_status=contract_status,
                rec=rec,
                session_id=session_id,
                account_id=account_id,
                trade_plan_dict=trade_plan_dict,
                session_payload=session_payload,
                reason="risk_signature",
            )
            return

        # V1.32 — Exit risk signature (qty firmada vs plannedQty)
        if is_closing_action(rec.action):
            planned: float | None = None
            if isinstance(exit_meta, dict):
                raw_planned = exit_meta.get("plannedQty")
                if isinstance(raw_planned, (int, float)):
                    planned = float(raw_planned)
            exit_sig = evaluate_exit_risk_signature(
                planned_qty=planned,
                signed_qty=float(intent.quantity),
                override_reason=risk_override_reason,
            )
            if not exit_sig.get("allowed"):
                await self._reject_gate(
                    result=result,
                    intent=intent,
                    contract_status=contract_status,
                    rec=rec,
                    session_id=session_id,
                    account_id=account_id,
                    trade_plan_dict=trade_plan_dict,
                    session_payload=session_payload,
                    reason="exit_risk_signature",
                )
                return

        # ExitGate — exit_permission
        if is_closing_action(rec.action):
            exit_perm = await self._exit.semi_exit_permission(
                rec=rec,
                intent=intent,
                price=price,
                account_id=account_id,
            )
            if exit_perm is not None and not exit_perm.allowed:
                result["trade"] = {
                    "status": "rejected_by_gate",
                    "reason": "exit_permission",
                    "exitPermission": exit_perm.to_dict(),
                }
                result["intent"] = {
                    **intent.to_dict(),
                    "status": "rejected_by_gate",
                    "contract": contract_status,
                }
                await append_journal_event(
                    self._journal_writer,
                    event_type="human_reject",
                    decision_id=rec.decision_id,
                    session_id=session_id,
                    account_id=account_id,
                    instrument_id=rec.instrument_id,
                    actor="human",
                    payload=attribution_setup_payload(
                        trade_plan_dict,
                        session_payload=session_payload,
                        base={
                            "reason": "exit_permission",
                            "status": "rejected_by_gate",
                            "exitPlanId": exit_perm.exit_plan_id,
                            "exitAction": exit_perm.action,
                            "exitReasons": list(exit_perm.reasons),
                        },
                    ),
                )
                return

        if not self._execution.configured:
            result["trade"] = {"status": "skipped", "reason": "execute_trade no configurado"}
            return

        signed_plan = (
            apply_signed_levels_to_trade_plan(
                trade_plan_dict if isinstance(trade_plan_dict, dict) else None,
                signed_qty=float(intent.quantity),
                signed_price=price,
                signed_stop=signed_stop,
            )
            if is_opening_action(rec.action)
            else trade_plan_dict
        )

        await self._run_submit_and_sync(
            result=result,
            rec=rec,
            intent=intent,
            account_id=account_id,
            session_id=session_id,
            contract_status=contract_status,
            price=price,
            trade_plan_dict=signed_plan if isinstance(signed_plan, dict) else trade_plan_dict,
            session_payload=session_payload,
        )

    async def _reject_gate(
        self,
        *,
        result: dict[str, Any],
        intent: Any,
        contract_status: str,
        rec: Recommendation,
        session_id: str | None,
        account_id: str,
        trade_plan_dict: dict[str, Any] | None,
        session_payload: dict[str, Any] | None,
        reason: str,
    ) -> None:
        result["trade"] = {"status": "rejected_by_gate", "reason": reason}
        result["intent"] = {
            **intent.to_dict(),
            "status": "rejected_by_gate",
            "contract": contract_status,
        }
        await append_journal_event(
            self._journal_writer,
            event_type="human_reject",
            decision_id=rec.decision_id,
            session_id=session_id,
            account_id=account_id,
            instrument_id=rec.instrument_id,
            actor="human",
            payload=attribution_setup_payload(
                trade_plan_dict,
                session_payload=session_payload,
                base={"reason": reason, "status": "rejected_by_gate"},
            ),
        )

    async def _run_submit_and_sync(
        self,
        *,
        result: dict[str, Any],
        rec: Recommendation,
        intent: Any,
        account_id: str,
        session_id: str | None,
        contract_status: str,
        price: float,
        trade_plan_dict: dict[str, Any] | None,
        session_payload: dict[str, Any] | None,
    ) -> None:
        idem_key = (rec.decision_id or "").strip()
        if not idem_key:
            result["trade"] = {"status": "error", "reason": "decision_id_required"}
            result["intent"] = {
                **intent.to_dict(),
                "status": "error",
                "contract": contract_status,
            }
            return

        existing_fill = await self._execution.find_existing_fill(
            account_id=account_id,
            idempotency_key=idem_key,
        )
        if existing_fill is not None:
            self._execution.apply_idempotent_replay(
                result=result,
                intent=intent,
                contract_status=contract_status,
                trade=existing_fill,
                order_id=stable_order_id_from_decision(idem_key),
            )
            return

        if await self._submit.try_recover_in_flight(
            result=result,
            intent=intent,
            contract_status=contract_status,
            decision_id=idem_key,
        ):
            return

        try:
            if is_opening_action(rec.action) and self._portfolio_summary is not None:
                await append_journal_event(
                    self._journal_writer,
                    event_type="gate_evaluated",
                    decision_id=rec.decision_id,
                    session_id=session_id,
                    account_id=account_id,
                    instrument_id=rec.instrument_id,
                    actor="human",
                    payload=attribution_setup_payload(
                        trade_plan_dict,
                        session_payload=session_payload,
                        base={"allowed": True},
                    ),
                )
        except Exception as exc:  # noqa: BLE001 — pre-send; no se llamó execute
            result["trade"] = {"status": "error", "reason": str(exc)}
            result["intent"] = {
                **intent.to_dict(),
                "status": "error",
                "contract": contract_status,
            }
            return

        durable = await self._submit.record_before_submit(
            result=result,
            intent=intent,
            contract_status=contract_status,
            decision_id=idem_key,
            account_id=account_id,
        )
        if durable is None:
            return

        pb = await self._execution.submit(
            account_id=account_id,
            intent=intent,
            price=price,
            idempotency_key=idem_key,
        )
        trade = ExecutionCoordinator.map_adapter_receipt(
            result=result,
            intent=intent,
            contract_status=contract_status,
            pb=pb,
        )
        if trade is not None:
            tx_id = pb.transaction_id
            position_persist: dict[str, Any] = {"status": "applied"}
            try:
                await append_journal_event(
                    self._journal_writer,
                    event_type="executed",
                    decision_id=rec.decision_id,
                    session_id=session_id,
                    account_id=account_id,
                    instrument_id=rec.instrument_id,
                    actor="human",
                    payload=attribution_setup_payload(
                        trade_plan_dict,
                        session_payload=session_payload,
                        base=await self._executed_journal_base(
                            rec=rec,
                            intent=intent,
                            price=price,
                            account_id=account_id,
                            transaction_id=tx_id,
                        ),
                    ),
                )
                position_persist = await self._positions.sync_after_fill(
                    rec=rec,
                    intent=intent,
                    price=price,
                    account_id=account_id,
                    trade=trade,
                    trade_plan_dict=trade_plan_dict,
                    tx_id=tx_id,
                )
            except Exception as exc:  # noqa: BLE001
                position_persist = {"status": "error", "reason": str(exc)}
            result["positionPersist"] = position_persist

        await self._submit.persist_after_adapter(
            durable=durable,
            pb=pb,
            result=result,
        )

    async def _executed_journal_base(
        self,
        *,
        rec: Recommendation,
        intent: Any,
        price: float,
        account_id: str,
        transaction_id: Any,
    ) -> dict[str, Any]:
        base: dict[str, Any] = {
            "status": "executed",
            "transactionId": transaction_id,
        }
        if not is_closing_action(rec.action):
            return base
        perm = await self._exit.semi_exit_permission(
            rec=rec,
            intent=intent,
            price=price,
            account_id=account_id,
        )
        if perm is None:
            return base
        base["exitPlanId"] = perm.exit_plan_id
        base["exitAction"] = perm.action
        base["exitVerdict"] = perm.verdict
        return base

    async def _persist_session(
        self,
        *,
        session_id: str | None,
        rec: Recommendation,
        account_id: str,
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        assert self._store is not None
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        if session_id:
            existing = await self._store.get_decision_session(session_id)
            if existing is not None and existing.payload:
                payload = attach_execution_to_payload(
                    existing.payload,
                    execution,
                    kind="confirm",
                    extra_lineage={"confirmedAt": now, "confirmLinked": True},
                )
                updated = DecisionSessionRecord(
                    id=existing.id,
                    kind="confirm",
                    status=existing.status,
                    instrument_id=existing.instrument_id,
                    created_at=existing.created_at,
                    account_id=existing.account_id or account_id,
                    symbol=existing.symbol,
                    recommendation_id=existing.recommendation_id,
                    decision_id=existing.decision_id,
                    payload=payload,
                )
                await self._store.update_decision_session(updated)
                return payload

        session = build_auto_session(
            kind="confirm",
            instrument_id=rec.instrument_id,
            account_id=account_id,
            symbol=rec.symbol,
            recommendation=rec.to_dict(),
            execution=execution,
            lineage={"confirmedAt": now, "orphanConfirm": True},
            decision_id=rec.decision_id or None,
            parent_session_id=session_id,
        )
        await self._store.append_decision_session(decision_session_to_record(session))
        return session.to_dict()
