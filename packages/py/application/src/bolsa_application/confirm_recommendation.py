"""F3 — Confirm Recommendation → OrderIntent (+ opcional trade) + DecisionSession.

Escalón 3/D1 — re-evaluación VETO de cesta al confirmar en SEMI: si el use-case
recibe `portfolio_summary`, y la recommendation es una **apertura**
(`recommend_long`/`recommend_short`), se re-ejecuta el risk de cesta
(`check_opening` + kill-switch) antes de tocar `ExecuteTrade`. Si veta → el fill
se bloquea (`rejected_by_gate`, `risk_veto`), replicando en SEMI el mismo Risk de
cesta que AUTO (`execution_router.py:560-581`). `exit_hint`/`reduce` NO se someten
al VETO (no abren cesta). Perfil de risk no se re-evalúa en esta rebanada
(`profile=None`); `portfolio_summary=None` conserva el comportamiento previo.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any
from uuid import uuid4

from bolsa_analytics.cognitive.decision_session import (
    attach_execution_to_payload,
    build_auto_session,
)
from bolsa_analytics.cognitive.order_intent import intent_from_recommendation
from bolsa_analytics.cognitive.portfolio_fit import BasketPosition
from bolsa_analytics.cognitive.recommendation import Recommendation
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord

from bolsa_application.accounts import GetPortfolioSummary
from bolsa_application.cognitive_persistence import CognitiveStore, decision_session_to_record
from bolsa_application.risk_engine import check_opening
from bolsa_application.risk_runtime import effective_kill_switch

_OPENING_ACTIONS = {"recommend_long", "recommend_short"}


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


def _intent_side_matches_package_side(intent_side: str, package_action: str | None) -> bool:
    """¿La dirección del intent es coherente con la `action` del DecisionPackage?"""
    if package_action == "recommend_long":
        return intent_side == "buy"
    if package_action in {"recommend_short", "exit_hint", "reduce"}:
        return intent_side == "sell"
    # wait / desconocida: la tesis no abre posición en esa dirección.
    return False


def _identity_reconciles(intent: Any, package: dict[str, Any]) -> bool:
    """El intent respeta la identidad de la tesis del DecisionPackage.

    Solo se concilia la identidad (dirección + instrumento). El sizing/notional
    NO se concilia: `suggested_quantity`/`suggested_price` son decisión operativa
    del humano, externos al paquete (edición legítima en el front).
    """
    if not _intent_side_matches_package_side(intent.side, package.get("action")):
        return False
    pkg_instrument = package.get("instrumentId")
    return pkg_instrument is None or pkg_instrument == intent.instrument_id


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
    ) -> None:
        self._store = cognitive_store
        self._execute_trade = execute_trade
        self._portfolio_summary = portfolio_summary

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

        if execute and intent.side in {"buy", "sell"} and intent.quantity > 0:
            price = float(rec.suggested_price or 0)
            if price <= 0:
                result["trade"] = {
                    "status": "skipped",
                    "reason": "suggestedPrice requerido para ejecutar",
                }
            elif package is not None and not _identity_reconciles(intent, package):
                # La identidad de la tesis debe coincidir con el contrato de la sesión.
                result["trade"] = {
                    "status": "rejected_by_gate",
                    "reason": "decision_package_conflict",
                }
                # El intent debe reflejar el rechazo para que la UI no trate el
                # ítem como ejecutado/aprobado y lo retire de la cola.
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
        tocar `ExecuteTrade`. Devuelve True si la cesta/kill-switch permiten el fill. El perfil de risk NO se re-evalúa en esta
        rebanada (`profile=None`); `exit_hint`/`reduce` quedan fuera (no abren cesta).
        Si el summary o la evaluación fallan de forma recuperable, se mantiene
        fail-open a la lógica de D2 (no es el gate de identidad): el fill NO se
        bloquea por una indisponibilidad del summary.
        """
        if self._portfolio_summary is None:
            return True
        try:
            summary = await self._portfolio_summary.execute(account_id=account_id)
        except Exception:  # noqa: BLE001 — indisponibilidad de summary no es gate
            return True
        equity = float(getattr(summary, "total_equity", 0) or 0)
        positions = getattr(summary, "positions", None)
        open_positions_count = len(positions) if positions is not None else 0
        decision = check_opening(
            profile=None,
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
            # El sector de la posición propuesta no está resuelto en el confirm; cae
            # a "unknown" en el agregado por sector (coherente con el summary sin sector).
            proposal_sector=None,
        )
        return bool(decision.allowed)

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
