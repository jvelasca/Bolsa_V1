"""F3 — Confirm Recommendation → OrderIntent (+ opcional trade) + DecisionSession.

Decision Spine — rebanada confirm SEMI (D2 + Escalón 3/D1 + cierre de la deuda):

- **D2 (contrato):** cuando la sesión `propose` persiste un `DecisionPackage`,
  es la fuente de verdad de la **identidad** (dirección + instrumento) del intent;
  si diverge → `rejected_by_gate`/`decision_package_conflict` fail-closed.
- **Escalón 3/D1 (VETO de cesta):** si el use-case recibe `portfolio_summary`, y la
  recommendation es una **apertura** (`recommend_long`/`recommend_short`), se
  re-ejecuta el risk de cesta (`check_opening` + kill-switch) antes de `ExecuteTrade`;
  si veta → `rejected_by_gate`/`risk_veto`. `exit_hint`/`reduce` NO se someten al
  VETO (no abren cesta). `portfolio_summary=None` conserva el comportamiento previo.
- **H1 (auditoría spine):** el sector de la puesta propuesta se resuelve desde
  `instruments.sector` (mismo dato que AUTO `hit.sector`) y se pasa a
  `check_opening(proposal_sector=...)` para que `MaxSectorExposure` cuente el
  fill nuevo. Sin lookup inyectado o sin sector en DB → `None` (cae a
  `<unknown>` en Fit; no se inventa un sector).
- **H2 (auditoría spine, D1):** si `GetPortfolioSummary` está inyectado y
  **falla** (excepción), el confirm es fail-closed (`risk_veto`): no hay
  override por indisponibilidad. `portfolio_summary=None` sigue sin aplicar
  cesta (tests / wiring legado).
- **H5 (auditoría spine):** el confirm SEMI resuelve el `InvestorProfile` activo
  de la cuenta (`accounts.resolve_scope` → `active_profile_id` →
  `profile_store.get`) y lo pasa a `check_opening(profile=...)`, mismo SoT que
  AUTO en `execution_router`. Sin store/accounts inyectados, sin
  `active_profile_id`, o si la resolución falla → `profile=None` (fail-open
  solo en perfil; cesta/kill-switch siguen aplicándose con defaults moderate).
- **DS-05 (Data Freshness Gate):** si el use-case recibe `ohlcv` (lookup de
  última barra), las aperturas pasan `last_bar_timestamp` +
  `require_fresh_data=True` a `check_opening` (mismo path AUTO). Barra ausente,
  inválida o más vieja que el umbral → `risk_veto` fail-closed. Lookup que
  lanza → veto (como H2). `ohlcv=None` conserva compat (tests / wiring legado).
- **DS-03 (Account Mandate Gate):** si el use-case recibe `mandates` (lookup de
  tenure abierto en BD), las aperturas pasan `require_account_mandate=True` a
  `check_opening` (mismo path AUTO). Sin tenure abierto → `risk_veto`
  fail-closed. Lookup que lanza → veto (como H2/DS-05). `mandates=None`
  conserva compat (tests / wiring legado). Exits fuera del gate.
- **Cierre deuda confirm SEMI (Bug 1 + Bug 2):**
  - **Bug 1 (`wait` no trade):** solo las acciones transaccionales
    (`recommend_long`/`recommend_short`/`exit_hint`/`reduce`) pueden llegar a
    `ExecuteTrade`. Una tesis `wait` (ni siquiera con `suggested_quantity>0`) NO
    desencadena un sell default: el trade queda `None`.
  - **Bug 2 (side de `exit_hint`/`reduce`):** el lado de un cierre/reducción es el
    **inverso** de la posición, que solo se conoce desde el `DecisionPackage` de la
    sesión (`recommend_long`→`sell`, `recommend_short`→`buy`). Si no hay package para
    determinarlo → `rejected_by_gate`/`unknown_position_side` (fail-closed, nunca
    se asume el lado).
- **ADR-031 (Ciclo 1):** TTL `expiresAt` → `expired`; aperturas orphan con store
  cableado → `orphan_opening_blocked`; último close vs `suggestedPrice` (banda 2 %)
  → `stale_price`.
- **ADR-031 TradePlan (E1 P1):** `result["tradePlan"]` es la capa PLAN
  (WATCH|ARMED|TRIGGERED|BLOCKED|EXPIRED). No sustituye `check_opening`.
- **P2 firma de riesgo (ADR-033 §6):** execute de aperturas con TradePlan
  TRIGGERED + quantity>0 bloquea qty/pérdida por encima del plan sin
  `risk_override_reason`. Motivo `risk_signature` (≠ `risk_veto`).
- **P3 cadena de salida (ADR-033 §4):** execute de `exit_hint`/`reduce` con
  Position persistida pasa ExitPlan (`manual`) → ExitPermission. Motivo
  `exit_permission` (≠ `risk_veto` ≠ `risk_signature`). Sin fila → legado.
  Tras fill: `applyReduce`. Lab `EvaluatePositionExits` intacto.
- **OI-1 continuidad (ADR-034):** manual HTTP/pending sync PositionState;
  Confirm no pisa `trade.executed` si persist falla; Proteger persiste stop
  (ExitPermission protect, cero ledger); Lab executeTrades → exit persist.
- **PH-1 protect honesty:** `persist` → None (H2) o excepción → no
  `protect_applied` (cero ledger: el éxito es persistir). `skipped` /
  `stop_not_applied` | `persist_error`.
- **OI-3 ExecutionRecord (ADR-034):** excepción de `execute_trade` →
  `trade.status=unknown` (nunca `error`, nunca `rejected_by_gate`). ERROR solo
  si el envío no se intentó. `executionRecord` adjunta el outcome honesto.
- **OI-4 / OR-3 PaperOrder (ADR-034/035):** al enviar nace CREATED; PaperBroker
  marca SUBMITTED pre-send → fill FILLED; boom/crash → UNKNOWN (≠ CREATED).
  Gate/skip → no hay `paperOrder`. CREATED ≠ FILLED.
- **OR-1 idempotencia E2E (ADR-035):** clave = `decision_id` (sin fallback
  `confirm-{uuid}`). Sin `decision_id` → `error` pre-send. Fill local ya
  existente → replay sin `adapter.submit`. `intent_id`/`order_id` estables.
- **OR-2 crash/restart (ADR-035):** `DurableSubmitIntent` se persiste *antes*
  de `adapter.submit`. Sin fill local y con intento durable → `unknown`
  reconstruido (mapeo `intent` ↔ `venue_order_id`); no re-POST.
- **BrokerAdapter (ADR-034 / XL-1):** Confirm envía vía `IBrokerAdapter` (default
  paper = PaperBroker). Adjunta `brokerAdapter` + `paperBroker` en paper.
  Mock LIVE → `live_not_wired`. XTB → rejected/submitted sin ledger
  (`submitted` ≠ fill).
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
from bolsa_analytics.cognitive.order_intent import intent_from_recommendation
from bolsa_analytics.cognitive.paper_order import (
    apply_paper_order_fill,
    build_paper_order,
    stable_order_id_from_decision,
    transition_paper_order,
)
from bolsa_analytics.cognitive.submit_intent import (
    bind_venue_order,
    mark_submit_filled,
    record_submit_intent,
    reconstruct_unknown,
    send_attempted_durable,
)
from bolsa_analytics.cognitive.recommendation import Recommendation
from bolsa_analytics.cognitive.risk_signature import evaluate_risk_signature
from bolsa_analytics.cognitive.trade_plan import (
    WYCKOFF_SPRING_ANCHOR_KEY,
    build_v0_trade_plan_dict,
    parse_wyckoff_spring_anchor,
)
from bolsa_application.account_mandate_gate import AccountMandateLookup
from bolsa_application.accounts import GetPortfolioSummary
from bolsa_application.broker_adapter import IBrokerAdapter, resolve_broker_adapter
from bolsa_application.broker_venue_runtime import (
    account_broker_venue_from_settings,
    effective_broker_venue_async,
)
from bolsa_application.cognitive_persistence import CognitiveStore, decision_session_to_record
from bolsa_application.evaluate_exit_plan import semi_exit_permission, semi_protect_permission
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.journal_writer import (
    append_journal_event,
    attribution_setup_payload,
)
from bolsa_application.opening_permission import (
    AccountScopeLookup,
    InstrumentSectorLookup,
    LatestBarLookup,
    allow_opening_fill,
)
from bolsa_application.reconciliation_opening_gate import (
    LiveReconLookup,
    PortfolioReconLookup,
)
from bolsa_application.persist_position_from_exit import (
    PersistPositionFromExitInput,
    row_position_state,
)
from bolsa_application.persist_position_from_fill import (
    PersistPositionFromFillInput,
    ledger_position_id_from_trade,
    open_transaction_id_from_trade,
)
from bolsa_application.persist_position_from_protect import PersistPositionFromProtectInput
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord

_OPENING_ACTIONS = {"recommend_long", "recommend_short"}
_CLOSING_ACTIONS = {"exit_hint", "reduce"}
# Acciones transaccionales que pueden llegar a `ExecuteTrade` (solo estas)
# `wait` NO está: una tesis `wait` no abre ni cierra posición (Bug 1).
_TRADE_ACTIONS = _OPENING_ACTIONS | _CLOSING_ACTIONS

# ADR-031 — banda de revalidación de precio (último close vs suggestedPrice).
PRICE_REVALIDATION_MAX_REL_DEVIATION = 0.02


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


def resolve_session_decision_package(
    session_record: DecisionSessionRecord | None,
) -> dict[str, Any] | None:
    """Extrae el DecisionPackage de una sesión `propose` persistida, si existe.

    El paquete completo (action/instrumentId/decisionId) vive solo en
    `payload["runtime"]["decisionPackage"]` de la sesión `propose`. Las sesiones
    `confirm`/`paper_auto`/`live_dry_run` (build_auto_session) no llevan `runtime`,
    por lo que devuelven None. Retorna None si la sesión no existe o no tiene paquete.
    """
    if session_record is None or not session_record.payload:
        return None
    runtime = session_record.payload.get("runtime") or {}
    pkg = runtime.get("decisionPackage")
    return pkg if isinstance(pkg, dict) else None


def _required_fill_side(action: str, package_action: str | None) -> tuple[bool, str | None]:
    """Lado de llenado requerido para `action` dado el `action` de la sesión (`package`).

    Retorna `(determinable, side)`. Con `determinable=False` el contexto NO permite
    decidir el lado → el confirm debe rechazar (fail-closed), nunca asumir.

    - **Aperturas** (`recommend_long`/`recommend_short`): el lado viene de la propia
      acción (buy/sell). Si existe paquete de sesión, su tesis DEBE ser la misma
      apertura (fuente de verdad D2); si es incoherente → no determinable (conflict).
      Sin sesión (orphan) la apertura sigue permitida (contrato `absent`), D2 previo.
    - **Cierres** (`exit_hint`/`reduce`): el lado es el INVERSO de la posición, que
      solo se conoce desde el package (long→sell, short→buy). Bug 2: antes se asumía
      siempre `sell`, lo que re-abría un short en vez de cubrirlo. Sin package el lado
      es indeterminable → fail-closed (`unknown_position_side`).
    """
    if action in {"recommend_long", "recommend_short"}:
        if package_action not in (None, action):
            return False, None  # tesis de sesión incompatible con la apertura confirmada
        return True, "buy" if action == "recommend_long" else "sell"
    if action in _CLOSING_ACTIONS:
        if package_action == "recommend_long":
            return True, "sell"  # cerrar/reducir un largo = vender
        if package_action == "recommend_short":
            return True, "buy"  # cubrir/reducir un corto = comprar (no reabrir)
        return False, None  # sin posición conocida → no saber el lado
    # wait / desconocida: no transaccional; no deriva rechazo aquí (Bug 1).
    return True, None


def _package_action_from_position_direction(
    direction: object,
    *,
    instrument_id: str,
) -> dict[str, Any] | None:
    """P4 — inferir tesis de cierre desde Position persistida (≠ package de sesión)."""
    if direction == "long":
        return {"action": "recommend_long", "instrumentId": instrument_id}
    if direction == "short":
        return {"action": "recommend_short", "instrumentId": instrument_id}
    return None


def _reject_reason_for_execute(
    *,
    action: str,
    intent_side: str,
    intent_instrument_id: str,
    package: dict[str, Any] | None,
) -> str | None:
    """Motivo de rechazo fail-closed antes del fill, o `None` si procede ejecutar.

    Sustituye a `_identity_reconciles` (D2) y cubre además Bug 2 (side de cierre) y
    la identidad por instrumento. El sizing/notional NO se concilia: es decisión
    operativa del humano, externa al paquete.

    Retorna:
      - `"decision_package_conflict"` — lado/tesis/instrumento incoherentes con el package.
      - `"unknown_position_side"` — cierre (exit_hint/reduce) sin package: no se puede
        saber si va sell (largo) o buy (corto) → fail-closed.
      - `"non_trade_action"` — acción no transaccional en un path de execute.
      - `None` — procede (aún pasará por price/risk/execute gates).
    """
    if action not in _TRADE_ACTIONS:
        return "non_trade_action"
    pkg_action = None if package is None else package.get("action")
    determinable, required = _required_fill_side(action, pkg_action)
    if not determinable:
        return "decision_package_conflict" if package is not None else "unknown_position_side"
    if intent_side != required:
        return "decision_package_conflict"
    if package is not None:
        pkg_instrument = package.get("instrumentId")
        if pkg_instrument is not None and pkg_instrument != intent_instrument_id:
            return "decision_package_conflict"
    return None


def _parse_expires_at(raw: str | None) -> datetime | None:
    """ISO-8601 → datetime UTC; None si vacío o ilegible."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def recommendation_is_expired(expires_at: str | None, *, now: datetime | None = None) -> bool:
    """True si ``expiresAt`` está en el pasado (TTL ADR-031). Sin fecha → no caduca."""
    parsed = _parse_expires_at(expires_at)
    if parsed is None:
        return False
    moment = now if now is not None else datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    return parsed < moment


def resolve_confirm_trade_plan(
    *,
    raw: dict[str, Any],
    rec: Recommendation,
    package: dict[str, Any] | None,
    session_record: DecisionSessionRecord | None,
) -> dict[str, Any]:
    """PLAN layer on confirm: echo propose payload, else rebuild v0.

    Order: ``raw["tradePlan"]`` if dict; else session ``runtime.tradePlan`` if
    the propose session was already loaded; else ``build_v0_trade_plan_dict``
    (entry_ready False, structural_stop None). Does not grant permiso —
    ``check_opening`` remains the authority even if status were TRIGGERED.
    """
    incoming = raw.get("tradePlan")
    if isinstance(incoming, dict):
        return incoming

    runtime: dict[str, Any] | None = None
    if session_record is not None and session_record.payload:
        maybe_runtime = session_record.payload.get("runtime")
        if isinstance(maybe_runtime, dict):
            runtime = maybe_runtime
            session_plan = runtime.get("tradePlan")
            if isinstance(session_plan, dict):
                return session_plan

    opportunity: float | None = None
    wyckoff_prior: dict[str, object] | None = None
    if runtime is not None:
        raw_score = runtime.get("combinedScore")
        if isinstance(raw_score, int | float):
            opportunity = float(raw_score)
        wyckoff_prior = parse_wyckoff_spring_anchor(runtime.get(WYCKOFF_SPRING_ANCHOR_KEY))

    compliance = None if package is None else package.get("complianceCheck")
    entry: float | None = None
    if rec.suggested_price is not None:
        try:
            entry = float(rec.suggested_price)
        except (TypeError, ValueError):
            entry = None

    return build_v0_trade_plan_dict(
        decision_id=rec.decision_id,
        instrument_id=rec.instrument_id,
        action=str(rec.action),
        compliance_check=compliance,
        entry=entry,
        opportunity_score=opportunity,
        expires_at=rec.expires_at,
        expired=recommendation_is_expired(rec.expires_at),
        wyckoff_prior=wyckoff_prior,
    )


def price_revalidation_reason(
    suggested_price: float,
    last_close: float | None,
    *,
    max_rel_deviation: float = PRICE_REVALIDATION_MAX_REL_DEVIATION,
) -> str | None:
    """``stale_price`` si el close conocido se desvía más de la banda; None si no aplica.

    ``last_close`` None → no hay dato (compat tests / lookup sin close); no veta.
    Close ≤ 0 → ``stale_price`` fail-closed.
    """
    if last_close is None:
        return None
    if last_close <= 0 or suggested_price <= 0:
        return "stale_price"
    rel = abs(suggested_price - last_close) / last_close
    if rel > max_rel_deviation:
        return "stale_price"
    return None


def _is_opening_action(action: str) -> bool:
    """¿La recommendation abre una posición (sujeta al VETO de cesta en SEMI)?"""
    return action in _OPENING_ACTIONS


def _is_closing_action(action: str) -> bool:
    """¿La recommendation cierra o reduce (cadena P3, no cesta)?"""
    return action in _CLOSING_ACTIONS


def extract_operativa_protect_meta(raw: dict[str, Any]) -> dict[str, Any] | None:
    """OI-1 — meta protect desde Consola (``wait`` + ``operativaIntent=protect``)."""
    pkg = raw.get("decisionPackage")
    if not isinstance(pkg, dict):
        return None
    if pkg.get("operativaIntent") != "protect":
        return None
    stop = pkg.get("suggestedStop")
    if not isinstance(stop, (int, float)) or float(stop) <= 0:
        return None
    return pkg


def risk_signature_reject_reason(
    *,
    trade_plan: dict[str, Any] | None,
    signed_qty: float,
    signed_price: float,
    override_reason: str | None,
) -> str | None:
    """P2: ``risk_signature`` si el tamaño firmado supera el plan sin override."""
    verdict = evaluate_risk_signature(
        trade_plan,
        signed_qty=signed_qty,
        signed_price=signed_price,
        override_reason=override_reason,
        require_triggered_plan=True,
    )
    if verdict.get("allowed") is True:
        return None
    return "risk_signature"


class ConfirmRecommendationIntent:
    """Humano confirma Recommendation; audita Session (update o append confirm)."""

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
        journal_writer: Any | None = None,
        position_from_fill: Any | None = None,
        position_from_exit: Any | None = None,
        position_from_protect: Any | None = None,
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
        self._journal_writer = journal_writer
        self._position_from_fill = position_from_fill
        self._position_from_exit = position_from_exit
        self._position_from_protect = position_from_protect

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
            except Exception:  # noqa: BLE001 — preferencia opcional; fallback coalesce
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
    ) -> dict[str, Any]:
        raw = recommendation_raw
        metrics = raw.get("metrics") or {}
        rec = Recommendation(
            recommendation_id=str(raw.get("recommendationId") or raw.get("recommendation_id") or ""),
            decision_id=str(raw.get("decisionId") or ""),
            instrument_id=str(raw.get("instrumentId") or ""),
            action=str(raw.get("action") or "wait"),
            suggested_quantity=float(raw.get("suggestedQuantity") or 0),
            metrics={
                "confidence": float(metrics.get("confidence") or 0),
                "consensus": float(metrics.get("consensus") or 0),
                "evidenceStrength": float(metrics.get("evidenceStrength") or 0),
                "stability": float(metrics.get("stability") or 0),
                "conviction": float(metrics.get("conviction") or 0),
            },
            status="approved",
            created_at=str(raw.get("createdAt") or ""),
            symbol=raw.get("symbol"),
            account_id=account_id,
            suggested_price=raw.get("suggestedPrice"),
            expires_at=raw.get("expiresAt") or raw.get("expires_at"),
            notes=tuple(raw.get("notes") or ()),
        )
        intent = intent_from_recommendation(rec, account_id=account_id, authorized_by="human")
        result: dict[str, Any] = {
            "intent": {**intent.to_dict(), "contract": "absent"},
            "trade": None,
            "decisionSession": None,
        }

        # D2 — DecisionPackage como contrato (fuente de verdad = sesión `propose`).
        # Se verifica cuando la sesión persistida expone el paquete; si no hay
        # sesión/paquete (persist best-effort u orphan), no se bloquea el flujo pero
        # se marca la ausencia de contrato para visibilidad.
        contract_status: str = "absent"
        package: dict[str, Any] | None = None
        session_record: DecisionSessionRecord | None = None
        if self._store is not None and session_id:
            session_record = await self._store.get_decision_session(session_id)
            package = resolve_session_decision_package(session_record)
            if package is not None:
                contract_status = "present_verified"
        side_package = await self._effective_package_for_side(
            rec=rec,
            account_id=account_id,
            package=package,
        )
        if _is_closing_action(rec.action):
            _, required_side = _required_fill_side(
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
        # Ciclo 6 — firma humana (execute=False o intent autorizado).
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
            suggested_stop = float(
                protect_meta.get("suggestedStop") or rec.suggested_price or 0
            )
            if suggested_stop <= 0:
                result["trade"] = {
                    "status": "skipped",
                    "reason": "suggestedStop requerido para proteger",
                }
            elif self._position_from_protect is None:
                result["trade"] = {
                    "status": "skipped",
                    "reason": "position_from_protect no configurado",
                }
            else:
                row = await self._position_from_protect.get_open(
                    account_id, str(rec.instrument_id or "")
                )
                state_blob = row_position_state(row)
                exit_perm = semi_protect_permission(
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
                else:
                    position_persist: dict[str, Any] = {"status": "applied"}
                    applied_row: Any | None = None
                    try:
                        applied_row = await self._position_from_protect.persist(
                            PersistPositionFromProtectInput(
                                account_id=account_id,
                                instrument_id=str(rec.instrument_id or ""),
                                suggested_stop=suggested_stop,
                                override_reason=risk_override_reason,
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        position_persist = {"status": "error", "reason": str(exc)}
                        result["trade"] = {
                            "status": "skipped",
                            "reason": "persist_error",
                        }
                        result["positionPersist"] = position_persist
                    else:
                        if applied_row is None:
                            position_persist = {
                                "status": "skipped",
                                "reason": "stop_not_applied",
                            }
                            result["trade"] = {
                                "status": "skipped",
                                "reason": "stop_not_applied",
                            }
                            result["positionPersist"] = position_persist
                        else:
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
                                        "currentStop": protect_meta.get(
                                            "currentStop"
                                        ),
                                        "overrideReason": risk_override_reason,
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

        elif (
            execute
            and rec.action in _TRADE_ACTIONS
            and intent.side in {"buy", "sell"}
            and intent.quantity > 0
        ):
            price = float(rec.suggested_price or 0)
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
                and _is_opening_action(rec.action)
                and package is None
                and self._store is not None
            ):
                # H3 / ADR-031 — aperturas nuevas fallan cerradas sin DecisionPackage
                # cuando el store está cableado (producción). Tests sin store = legado.
                reject_reason = "orphan_opening_blocked"
            if (
                reject_reason is None
                and _is_opening_action(rec.action)
                and self._ohlcv is not None
            ):
                last_close = await self._resolve_latest_close(intent.instrument_id)
                reject_reason = price_revalidation_reason(price, last_close)
            if price <= 0 and reject_reason is None:
                result["trade"] = {
                    "status": "skipped",
                    "reason": "suggestedPrice requerido para ejecutar",
                }
            elif reject_reason is not None:
                # Identidad D2 (apertura vs tesis) + Bug 2 (side de cierre fail-closed).
                # El intent refleja el rechazo para que la UI no trate el ítem como
                # ejecutado/aprobado y lo retire de la cola (mismo patrón que D2/Esc.3).
                result["trade"] = {
                    "status": "rejected_by_gate",
                    "reason": reject_reason,
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
                        base={"reason": reject_reason, "status": "rejected_by_gate"},
                    ),
                )
            elif (
                _is_opening_action(rec.action)
                and self._portfolio_summary is not None
                and not await self._risk_allows_opening(
                    rec=rec,
                    intent=intent,
                    price=price,
                    account_id=account_id,
                )
            ):
                # Escalón 3/D1 — re-evaluación VETO de cesta en SEMI (fail-closed).
                # Solo aperturas (recommend_long/recommend_short); exit_hint/reduce no
                # abren cesta y quedan fuera de esta rebanada. El intent refleja el
                # rechazo para que la UI retire el ítem de la cola (mismo patrón que D2).
                result["trade"] = {
                    "status": "rejected_by_gate",
                    "reason": "risk_veto",
                }
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
            elif (
                _is_opening_action(rec.action)
                and risk_signature_reject_reason(
                    trade_plan=trade_plan_dict if isinstance(trade_plan_dict, dict) else None,
                    signed_qty=float(intent.quantity),
                    signed_price=price,
                    override_reason=risk_override_reason,
                )
                is not None
            ):
                # P2 — sizing vs TradePlan (≠ check_opening / risk_veto).
                result["trade"] = {
                    "status": "rejected_by_gate",
                    "reason": "risk_signature",
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
                        base={"reason": "risk_signature", "status": "rejected_by_gate"},
                    ),
                )
            elif (
                _is_closing_action(rec.action)
                and (exit_perm := await self._semi_exit_permission(
                    rec=rec,
                    intent=intent,
                    price=price,
                    account_id=account_id,
                ))
                is not None
                and not exit_perm.allowed
            ):
                # P3 — ExitPlan + ExitPermission (≠ check_opening / risk_signature).
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
            elif self._broker_adapter is None and self._execute_trade is None:
                result["trade"] = {"status": "skipped", "reason": "execute_trade no configurado"}
            else:
                idem_key = (rec.decision_id or "").strip()
                if not idem_key:
                    # OR-1 D1 — sin decision_id no hay identidad de intento (fail-closed).
                    result["trade"] = {
                        "status": "error",
                        "reason": "decision_id_required",
                    }
                    result["intent"] = {
                        **intent.to_dict(),
                        "status": "error",
                        "contract": contract_status,
                    }
                else:
                    existing_fill = await self._find_existing_fill(
                        account_id=account_id,
                        idempotency_key=idem_key,
                    )
                    if existing_fill is not None:
                        # OR-1 D4 — short-circuit: fill local → replay sin adapter.submit.
                        await self._apply_idempotent_replay(
                            result=result,
                            intent=intent,
                            contract_status=contract_status,
                            trade=existing_fill,
                            order_id=stable_order_id_from_decision(idem_key),
                        )
                    elif await self._try_recover_in_flight(
                        result=result,
                        intent=intent,
                        contract_status=contract_status,
                        decision_id=idem_key,
                    ):
                        pass
                    else:
                        trade = None
                        durable = None
                        try:
                            if _is_opening_action(rec.action) and self._portfolio_summary is not None:
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
                        else:
                            durable = await self._record_before_submit(
                                result=result,
                                intent=intent,
                                contract_status=contract_status,
                                decision_id=idem_key,
                                account_id=account_id,
                            )
                            if durable is None:
                                pass
                            else:
                                adapter = await self._resolve_broker_adapter_for_account(account_id)
                                pb = await adapter.submit(
                                    instrument_id=intent.instrument_id,
                                    side=intent.side,
                                    quantity=float(intent.quantity),
                                    price=price,
                                    account_id=account_id,
                                    idempotency_key=idem_key,
                                    order_id=stable_order_id_from_decision(idem_key),
                                    intent_id=intent.intent_id,
                                )
                                result["brokerAdapter"] = pb.receipt().to_dict()
                                if pb.paper_order is not None:
                                    result["paperOrder"] = pb.paper_order.to_dict()
                                if pb.paper_receipt is not None:
                                    result["paperBroker"] = pb.paper_receipt.to_dict()
                                if pb.status == "not_wired":
                                    result["trade"] = {
                                        "status": "skipped",
                                        "reason": pb.reason or "live_not_wired",
                                    }
                                elif pb.status == "rejected":
                                    result["trade"] = {
                                        "status": "skipped",
                                        "reason": pb.reason or "live_rejected",
                                    }
                                elif pb.status == "submitted":
                                    # Venue aceptó; sin ledger en XL-1 → unknown (≠ executed).
                                    # OR-1/D6: sin fill local no hay short-circuit; mapeo
                                    # durable intent↔venue = OR-2 (no re-POST ciego ahí).
                                    trade_payload: dict[str, Any] = {
                                        "status": "unknown",
                                        "reason": pb.reason or "live_submitted_no_fill",
                                    }
                                    if pb.venue_order_id:
                                        trade_payload["venueOrderId"] = pb.venue_order_id
                                    result["trade"] = trade_payload
                                    result["intent"] = {
                                        **intent.to_dict(),
                                        "status": "unknown",
                                        "contract": contract_status,
                                    }
                                elif pb.status == "unknown":
                                    unknown_payload: dict[str, Any] = {
                                        "status": "unknown",
                                        "reason": pb.reason,
                                    }
                                    if pb.venue_order_id:
                                        unknown_payload["venueOrderId"] = pb.venue_order_id
                                    result["trade"] = unknown_payload
                                    result["intent"] = {
                                        **intent.to_dict(),
                                        "status": "unknown",
                                        "contract": contract_status,
                                    }
                                else:
                                    trade = pb.trade
                                    tx_id = pb.transaction_id
                                    result["trade"] = {
                                        "status": "executed",
                                        "transactionId": tx_id,
                                    }
                                    result["intent"] = {
                                        **intent.to_dict(),
                                        "status": "executed",
                                        "contract": contract_status,
                                    }
                                    position_persist = {"status": "applied"}
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
                                        if self._position_from_fill is not None and _is_opening_action(
                                            rec.action
                                        ):
                                            if isinstance(tx_id, str) and tx_id.strip():
                                                filled_at = getattr(
                                                    getattr(trade, "transaction", None),
                                                    "executed_at",
                                                    None,
                                                )
                                                await self._position_from_fill.persist(
                                                    PersistPositionFromFillInput(
                                                        account_id=account_id,
                                                        trade_plan=trade_plan_dict
                                                        if isinstance(trade_plan_dict, dict)
                                                        else None,
                                                        fill_price=price,
                                                        fill_quantity=float(intent.quantity),
                                                        filled_at=str(filled_at) if filled_at else None,
                                                        open_transaction_id=tx_id,
                                                        ledger_position_id=ledger_position_id_from_trade(
                                                            trade, intent.instrument_id
                                                        ),
                                                    )
                                                )
                                        if self._position_from_exit is not None and _is_closing_action(
                                            rec.action
                                        ):
                                            if isinstance(tx_id, str) and tx_id.strip():
                                                filled_at = getattr(
                                                    getattr(trade, "transaction", None),
                                                    "executed_at",
                                                    None,
                                                )
                                                await self._position_from_exit.persist(
                                                    PersistPositionFromExitInput(
                                                        account_id=account_id,
                                                        instrument_id=intent.instrument_id,
                                                        fill_quantity=float(intent.quantity),
                                                        fill_price=price,
                                                        exit_transaction_id=tx_id,
                                                        filled_at=str(filled_at) if filled_at else None,
                                                    )
                                                )
                                    except Exception as exc:  # noqa: BLE001
                                        position_persist = {"status": "error", "reason": str(exc)}
                                    result["positionPersist"] = position_persist
                                await self._persist_after_adapter(
                                    durable=durable,
                                    pb=pb,
                                    result=result,
                                )

        _attach_execution_record(result)

        execution = {
            "intent": result["intent"],
            "trade": result["trade"],
            "authorizedBy": "human",
        }

        if self._store is not None:
            try:
                session_payload = await self._persist_session(
                    session_id=session_id,
                    rec=rec,
                    account_id=account_id,
                    execution=execution,
                )
                result["decisionSession"] = session_payload
            except Exception:  # noqa: BLE001 — confirm no tumba por audit
                pass

        return result

    async def _find_existing_fill(
        self,
        *,
        account_id: str,
        idempotency_key: str,
    ) -> Any | None:
        """OR-1 — peek de fill local vía ExecuteTrade (o duck-type de tests)."""
        if not idempotency_key or self._execute_trade is None:
            return None
        finder = getattr(self._execute_trade, "find_existing_by_idempotency", None)
        if finder is None:
            return None
        try:
            trade = await finder(
                account_id=account_id,
                idempotency_key=idempotency_key,
            )
        except Exception:  # noqa: BLE001 — peek best-effort; fallo → primer envío
            return None
        if trade is None:
            return None
        tx_id = open_transaction_id_from_trade(trade)
        if not isinstance(tx_id, str) or not tx_id.strip():
            return None
        return trade

    async def _try_recover_in_flight(
        self,
        *,
        result: dict[str, Any],
        intent: Any,
        contract_status: str,
        decision_id: str,
    ) -> bool:
        """OR-2 — intento durable sin fill local → UNKNOWN, no adapter.submit."""
        store = self._submit_intent_store
        if store is None or not decision_id:
            return False
        getter = getattr(store, "get", None)
        if getter is None:
            return False
        try:
            durable = await getter(decision_id)
        except Exception:  # noqa: BLE001 — peek fallido → primer envío
            return False
        if not send_attempted_durable(durable):
            return False
        rec = reconstruct_unknown(durable)
        trade_payload: dict[str, Any] = {
            "status": "unknown",
            "reason": rec.reason or "crash_before_venue_ack",
            "crashRecovery": True,
        }
        if durable.venue_order_id:
            trade_payload["venueOrderId"] = durable.venue_order_id
        result["trade"] = trade_payload
        result["intent"] = {
            **intent.to_dict(),
            "status": "unknown",
            "contract": contract_status,
        }
        result["submitIntent"] = durable.to_dict()
        if durable.venue_order_id is None:
            # OR-3 D6 — crash sin venue ack → UNKNOWN (no CREATED «como si no enviada»).
            result["paperOrder"] = transition_paper_order(
                build_paper_order(
                    instrument_id=intent.instrument_id,
                    side=intent.side,
                    quantity=float(intent.quantity),
                    order_id=durable.order_id,
                    intent_id=durable.intent_id,
                ),
                "UNKNOWN",
            ).to_dict()
        return True

    async def _record_before_submit(
        self,
        *,
        result: dict[str, Any],
        intent: Any,
        contract_status: str,
        decision_id: str,
        account_id: str,
    ) -> Any | None:
        """OR-2 D2 — persist recorded *antes* de adapter.submit. put falla → error pre-send."""
        durable = record_submit_intent(
            decision_id=decision_id,
            intent_id=intent.intent_id,
            order_id=stable_order_id_from_decision(decision_id),
            account_id=account_id,
        )
        store = self._submit_intent_store
        if store is None:
            return durable
        try:
            await store.put(durable)
        except Exception as exc:  # noqa: BLE001 — no enviar si no hay rastro
            result["trade"] = {"status": "error", "reason": str(exc) or "submit_intent_persist_failed"}
            result["intent"] = {
                **intent.to_dict(),
                "status": "error",
                "contract": contract_status,
            }
            return None
        result["submitIntent"] = durable.to_dict()
        return durable

    async def _persist_after_adapter(
        self,
        *,
        durable: Any,
        pb: Any,
        result: dict[str, Any],
    ) -> None:
        """OR-2 D4 — bind venue / mark filled / borrar si never-sent (not_wired|rejected)."""
        store = self._submit_intent_store
        if store is None or durable is None:
            return
        status = getattr(pb, "status", None)
        try:
            if status in {"not_wired", "rejected"}:
                deleter = getattr(store, "delete", None)
                if deleter is not None:
                    await deleter(durable.decision_id)
                result.pop("submitIntent", None)
                return
            if status == "executed":
                updated = mark_submit_filled(
                    bind_venue_order(
                        durable,
                        venue_order_id=getattr(pb, "venue_order_id", None),
                    )
                )
            else:
                updated = bind_venue_order(
                    durable,
                    venue_order_id=getattr(pb, "venue_order_id", None),
                    reason=getattr(pb, "reason", None),
                )
            await store.put(updated)
            result["submitIntent"] = updated.to_dict()
        except Exception:  # noqa: BLE001 — post-send; no tumbar el fill/unknown
            pass

    async def _apply_idempotent_replay(
        self,
        *,
        result: dict[str, Any],
        intent: Any,
        contract_status: str,
        trade: Any,
        order_id: str,
    ) -> None:
        """OR-1 D4 — mismo trade/ids sin adapter.submit ni journal executed duplicado."""
        tx_id = open_transaction_id_from_trade(trade)
        paper = apply_paper_order_fill(
            build_paper_order(
                instrument_id=intent.instrument_id,
                side=intent.side,
                quantity=float(intent.quantity),
                order_id=order_id,
                intent_id=intent.intent_id,
            ),
            transaction_id=tx_id,
        )
        result["trade"] = {
            "status": "executed",
            "transactionId": tx_id,
            "idempotentReplay": True,
        }
        result["intent"] = {
            **intent.to_dict(),
            "status": "executed",
            "contract": contract_status,
        }
        result["paperOrder"] = paper.to_dict()
        result["positionPersist"] = {"status": "applied", "idempotentReplay": True}

    async def _effective_package_for_side(
        self,
        *,
        rec: Recommendation,
        account_id: str,
        package: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Package de sesión o, en cierres P4, dirección desde Position persistida."""
        if package is not None:
            return package
        if not _is_closing_action(rec.action) or self._position_from_exit is None:
            return None
        row = await self._position_from_exit.get_open(
            account_id, str(rec.instrument_id or "")
        )
        if row is None:
            return None
        state = row_position_state(row)
        if state is None:
            return None
        return _package_action_from_position_direction(
            state.get("direction"),
            instrument_id=str(rec.instrument_id or ""),
        )

    async def _semi_exit_permission(
        self,
        *,
        rec: Recommendation,
        intent: Any,
        price: float,
        account_id: str,
    ) -> Any | None:
        """P3 — None = sin cadena (sin Position). Objeto = ExitPermission."""
        if self._position_from_exit is None:
            return None
        row = await self._position_from_exit.get_open(
            account_id, str(intent.instrument_id or rec.instrument_id)
        )
        if row is None:
            return None
        return semi_exit_permission(
            row_position_state(row),
            mark_price=price,
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
        if not _is_closing_action(rec.action):
            return base
        perm = await self._semi_exit_permission(
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

    async def _risk_allows_opening(
        self,
        *,
        rec: Recommendation,
        intent: Any,
        price: float,
        account_id: str,
    ) -> bool:
        """Escalón 3/D1 — re-evaluación VETO de cesta en SEMI (fail-closed).

        Re-ejecuta el risk de cesta (`check_opening`, el mismo que AUTO en
        `execution_router._execute_paper_trade`) para una apertura validada antes de
        tocar `ExecuteTrade`. Devuelve True si la cesta/kill-switch permiten el fill.
        `exit_hint`/`reduce` quedan fuera (no abren cesta).

        H2 / D1: si el summary está inyectado y lanza, se VETA (fail-closed).
        `portfolio_summary=None` no aplica cesta (comportamiento Escalón 3).
        H1: `proposal_sector` se resuelve desde `instruments.sector` cuando hay
        lookup inyectado (mismo dato que AUTO `hit.sector`).
        H5: `profile` se resuelve desde `active_profile_id` (mismo SoT que AUTO);
        fallo de resolución → `None` (defaults moderate; no tumba cesta/kill-switch).
        DS-05: con `ohlcv` inyectado, última barra + `require_fresh_data=True`;
        lookup que lanza → veto (fail-closed).
        DS-03: con `mandates` inyectado, tenure abierto + `require_account_mandate=True`;
        lookup que lanza → veto (fail-closed).
        OR-4: con `portfolio_recon` / `live_recon` inyectados, drift / live unavailable
        (venue live) → veto; lookup que lanza → veto (fail-closed).
        """
        venue = await self._resolve_broker_venue_for_account(account_id)
        return await allow_opening_fill(
            portfolio_summary=self._portfolio_summary,
            instruments=self._instruments,
            profile_store=self._profile_store,
            accounts=self._accounts,
            ohlcv=self._ohlcv,
            mandates=self._mandates,
            portfolio_recon=self._portfolio_recon,
            live_recon=self._live_recon,
            broker_venue=venue,
            account_id=account_id,
            instrument_id=intent.instrument_id,
            symbol=str(rec.symbol or intent.instrument_id),
            trade_type=str(intent.side),
            quantity=float(intent.quantity),
            price=float(price),
            signal_kind=str(rec.action),
        )

    async def _resolve_latest_close(self, instrument_id: str) -> float | None:
        """Último close D1 para revalidar ``suggestedPrice`` (ADR-031).

        Lookup que lanza o no expone ``get_latest_close`` → None (la banda no veta;
        DS-05 sigue cubriendo frescura por fecha). Close presente se evalúa en
        ``price_revalidation_reason``.
        """
        if self._ohlcv is None or not instrument_id:
            return None
        getter = getattr(self._ohlcv, "get_latest_close", None)
        if getter is None:
            return None
        try:
            close = await getter(instrument_id)
        except Exception:  # noqa: BLE001 — precio opcional; DS-05 cubre disponibilidad
            return None
        if close is None:
            return None
        try:
            value = float(close)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    async def _persist_session(
        self,
        *,
        session_id: str | None,
        rec: Recommendation,
        account_id: str,
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        assert self._store is not None
        from datetime import datetime

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
