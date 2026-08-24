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
"""

from __future__ import annotations

from datetime import UTC
from typing import Any, Protocol
from uuid import uuid4

from bolsa_analytics.cognitive.decision_session import (
    attach_execution_to_payload,
    build_auto_session,
)
from bolsa_analytics.cognitive.order_intent import intent_from_recommendation
from bolsa_analytics.cognitive.portfolio_fit import BasketPosition
from bolsa_analytics.cognitive.recommendation import Recommendation
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord
from bolsa_domain.entities.investor_profile import InvestorProfileRecord

from bolsa_application.account_mandate_gate import AccountMandateLookup
from bolsa_application.accounts import GetPortfolioSummary
from bolsa_application.cognitive_persistence import CognitiveStore, decision_session_to_record
from bolsa_application.investor_profiles import InvestorProfileStore
from bolsa_application.journal_writer import append_journal_event
from bolsa_application.risk_engine import check_opening
from bolsa_application.risk_runtime import effective_kill_switch

_OPENING_ACTIONS = {"recommend_long", "recommend_short"}
_CLOSING_ACTIONS = {"exit_hint", "reduce"}
# Acciones transaccionales que pueden llegar a `ExecuteTrade` (solo estas)
# `wait` NO está: una tesis `wait` no abre ni cierra posición (Bug 1).
_TRADE_ACTIONS = _OPENING_ACTIONS | _CLOSING_ACTIONS


class InstrumentSectorLookup(Protocol):
    """Puerto mínimo para resolver `instruments.sector` en el confirm SEMI (H1).

    `SqlAlchemyInstrumentRepository.get_by_id` cumple el contrato. El confirm
    no depende del Protocol gordo de instrumentos: solo necesita el sector
    del ticker que se va a abrir, el mismo dato que AUTO lee del scan hit.
    """

    async def get_by_id(self, instrument_id: str) -> Any | None: ...


class AccountScopeLookup(Protocol):
    """Puerto mínimo para resolver el scope de cuenta en el confirm SEMI (H5).

    `SqlAlchemyAccountRepository.resolve_scope` cumple el contrato. Solo se
    usa `scope.account.active_profile_id` (mismo patrón que AUTO
    `execution_router`).
    """

    async def resolve_scope(
        self, account_id: str, portfolio_id: str | None = None
    ) -> Any: ...


class LatestBarLookup(Protocol):
    """Puerto mínimo DS-05 — última barra OHLCV del instrumento (SEMI).

    `SqlAlchemyOhlcvRepository.get_latest_bar_date` cumple el contrato.
    """

    async def get_latest_bar_date(
        self,
        instrument_id: str,
        *,
        timeframe: Any = ...,
    ) -> str | None: ...


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


def _is_opening_action(action: str) -> bool:
    """¿La recommendation abre una posición (sujeta al VETO de cesta en SEMI)?"""
    return action in _OPENING_ACTIONS


def _basket_positions_from_summary(summary: Any) -> list[BasketPosition] | None:
    """Construye la cesta de posiciones del Risk de cesta desde un PortfolioSummary.

    Espejo de `execution_router._basket_positions_from_summary`: el `sector` viene
    resuelto desde `instruments.sector` en la capa de infraestructura (field
    `sector` de `Position`); si no está poblado, la posición entra su
    `market_value` como "unknown" en el agregado por sector.
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
        journal_writer: Any | None = None,
    ) -> None:
        self._store = cognitive_store
        self._execute_trade = execute_trade
        self._portfolio_summary = portfolio_summary
        self._instruments = instruments
        self._profile_store = profile_store
        self._accounts = accounts
        self._ohlcv = ohlcv
        self._mandates = mandates
        self._journal_writer = journal_writer

    async def execute(
        self,
        *,
        recommendation_raw: dict[str, Any],
        account_id: str,
        execute: bool = False,
        session_id: str | None = None,
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
        if self._store is not None and session_id:
            session_record = await self._store.get_decision_session(session_id)
            package = resolve_session_decision_package(session_record)
            if package is not None:
                contract_status = "present_verified"
        result["intent"]["contract"] = contract_status
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

        if (
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
                package=package,
            )
            if price <= 0:
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
                    event_type="risk_veto",
                    decision_id=rec.decision_id,
                    session_id=session_id,
                    account_id=account_id,
                    instrument_id=rec.instrument_id,
                    actor="human",
                    payload={"reason": "risk_veto", "status": "rejected_by_gate"},
                )
            elif self._execute_trade is None:
                result["trade"] = {"status": "skipped", "reason": "execute_trade no configurado"}
            else:
                try:
                    # B-4: la clave de idempotencia es la identidad lógica de la decisión
                    # (decision_id, con fallback a session_id). Un doble confirm de la misma
                    # decisión rejuega el trade original en vez de duplicarlo (guard DB de
                    # ExecuteTrade.find_transaction_by_idempotency).
                    # R-11 C2: el repo de trades exige clave NO vacía. Si ni decision_id ni
                    # session_id están, se genera una clave uuid4-siempre-no-vacía para que
                    # el fill nunca invoque execute_trade con ""/whitespace/Nones.
                    idem_key = rec.decision_id or session_id or f"confirm-{uuid4().hex}"
                    trade = await self._execute_trade.execute(
                        instrument_id=intent.instrument_id,
                        trade_type=intent.side,
                        quantity=intent.quantity,
                        price=price,
                        account_id=account_id,
                        idempotency_key=idem_key,
                    )
                    result["trade"] = {
                        "status": "executed",
                        "transactionId": getattr(trade, "transaction_id", None)
                        or getattr(getattr(trade, "transaction", None), "id", None),
                    }
                    result["intent"] = {
                        **intent.to_dict(),
                        "status": "executed",
                        "contract": contract_status,
                    }
                    await append_journal_event(
                        self._journal_writer,
                        event_type="executed",
                        decision_id=rec.decision_id,
                        session_id=session_id,
                        account_id=account_id,
                        instrument_id=rec.instrument_id,
                        actor="human",
                        payload={
                            "status": "executed",
                            "transactionId": result["trade"]["transactionId"],
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    result["trade"] = {"status": "error", "reason": str(exc)}
                    result["intent"] = {
                        **intent.to_dict(),
                        "status": "rejected_by_gate",
                        "contract": contract_status,
                    }

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
        """
        if self._portfolio_summary is None:
            return True
        try:
            summary = await self._portfolio_summary.execute(account_id=account_id)
        except Exception:  # noqa: BLE001 — H2: indisponibilidad = veto, no override
            return False
        equity = float(getattr(summary, "total_equity", 0) or 0)
        positions = getattr(summary, "positions", None)
        open_positions_count = len(positions) if positions is not None else 0
        last_bar_timestamp: str | None = None
        require_fresh_data = False
        if self._ohlcv is not None:
            require_fresh_data = True
            try:
                last_bar_timestamp = await self._ohlcv.get_latest_bar_date(
                    intent.instrument_id
                )
            except Exception:  # noqa: BLE001 — DS-05: indisponibilidad = veto
                return False
        has_open_mandate = False
        mandate_strategy_id: str | None = None
        require_account_mandate = False
        if self._mandates is not None:
            require_account_mandate = True
            try:
                has_open_mandate, mandate_strategy_id = (
                    await self._mandates.get_open_mandate_for_instrument(
                        account_id, intent.instrument_id
                    )
                )
            except Exception:  # noqa: BLE001 — DS-03: indisponibilidad = veto
                return False
        decision = check_opening(
            profile=await self._resolve_opening_profile(account_id),
            instrument_id=intent.instrument_id,
            symbol=str(rec.symbol or intent.instrument_id),
            trade_type=str(intent.side),
            quantity=float(intent.quantity),
            price=float(price),
            signal_kind=str(rec.action),
            equity=equity,
            open_positions_count=open_positions_count,
            auto_live=False,
            kill_switch=await effective_kill_switch(),
            portfolio_positions=_basket_positions_from_summary(summary),
            proposal_sector=await self._resolve_proposal_sector(intent.instrument_id),
            last_bar_timestamp=last_bar_timestamp,
            require_fresh_data=require_fresh_data,
            has_open_mandate=has_open_mandate,
            mandate_strategy_id=mandate_strategy_id,
            require_account_mandate=require_account_mandate,
        )
        return bool(decision.allowed)

    async def _resolve_opening_profile(
        self, account_id: str
    ) -> InvestorProfileRecord | None:
        """H5 — perfil activo de la cuenta (mismo SoT que AUTO execution_router).

        Fail-open solo en perfil: sin store/accounts, sin `active_profile_id`, o
        cualquier excepción → `None` (check_opening usa defaults moderate). La
        cesta y el kill-switch siguen evaluándose con el summary inyectado.
        """
        if self._profile_store is None or self._accounts is None or not account_id:
            return None
        try:
            scope = await self._accounts.resolve_scope(account_id)
            active_profile_id = getattr(
                getattr(scope, "account", None), "active_profile_id", None
            )
            if not active_profile_id:
                return None
            return await self._profile_store.get(active_profile_id)
        except Exception:  # noqa: BLE001 — perfil opcional; no tumba cesta/kill-switch
            return None

    async def _resolve_proposal_sector(self, instrument_id: str) -> str | None:
        """H1 — sector de la puesta nueva desde `instruments.sector` (SoT AUTO).

        Lookup best-effort: excepción o instrumento sin sector → `None` (Fit
        agrupa el notional nuevo bajo `<unknown>`; no se inventa sector).
        """
        if self._instruments is None or not instrument_id:
            return None
        try:
            inst = await self._instruments.get_by_id(instrument_id)
        except Exception:  # noqa: BLE001 — sin sector no bloquea el gate de cesta
            return None
        if inst is None:
            return None
        sector = getattr(inst, "sector", None)
        if isinstance(sector, str) and sector.strip():
            return sector.strip()
        return None

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
