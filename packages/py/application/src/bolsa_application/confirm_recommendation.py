"""F3 — Confirm Recommendation → OrderIntent (+ opcional trade) + DecisionSession."""

from __future__ import annotations

from datetime import UTC
from typing import Any

from bolsa_analytics.cognitive.decision_session import (
    attach_execution_to_payload,
    build_auto_session,
)
from bolsa_analytics.cognitive.order_intent import intent_from_recommendation
from bolsa_analytics.cognitive.recommendation import Recommendation
from bolsa_application.cognitive_persistence import CognitiveStore, decision_session_to_record
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord


class ConfirmRecommendationIntent:
    """Humano confirma Recommendation; audita Session (update o append confirm)."""

    def __init__(
        self,
        *,
        cognitive_store: CognitiveStore | None = None,
        execute_trade: Any | None = None,
    ) -> None:
        self._store = cognitive_store
        self._execute_trade = execute_trade

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
            "intent": intent.to_dict(),
            "trade": None,
            "decisionSession": None,
        }

        if execute and intent.side in {"buy", "sell"} and intent.quantity > 0:
            price = float(rec.suggested_price or 0)
            if price <= 0:
                result["trade"] = {
                    "status": "skipped",
                    "reason": "suggestedPrice requerido para ejecutar",
                }
            elif self._execute_trade is None:
                result["trade"] = {"status": "skipped", "reason": "execute_trade no configurado"}
            else:
                try:
                    # B-4: la clave de idempotencia es la identidad lógica de la decisión
                    # (decision_id, con fallback a session_id). Un doble confirm de la misma
                    # decisión rejuega el trade original en vez de duplicarlo (guard DB de
                    # ExecuteTrade.find_transaction_by_idempotency).
                    trade = await self._execute_trade.execute(
                        instrument_id=intent.instrument_id,
                        trade_type=intent.side,
                        quantity=intent.quantity,
                        price=price,
                        account_id=account_id,
                        idempotency_key=rec.decision_id or session_id,
                    )
                    result["trade"] = {
                        "status": "executed",
                        "transactionId": getattr(trade, "transaction_id", None)
                        or getattr(getattr(trade, "transaction", None), "id", None),
                    }
                    result["intent"] = {**intent.to_dict(), "status": "executed"}
                except Exception as exc:  # noqa: BLE001
                    result["trade"] = {"status": "error", "reason": str(exc)}
                    result["intent"] = {**intent.to_dict(), "status": "rejected_by_gate"}

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
