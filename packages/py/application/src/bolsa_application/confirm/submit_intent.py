"""DEX-4 — SubmitIntent coordinator (OR-2 + DEX-1 durable lifecycle)."""

from __future__ import annotations

from typing import Any

from bolsa_analytics.cognitive.paper_order import (
    build_paper_order,
    stable_order_id_from_decision,
    transition_paper_order,
)
from bolsa_analytics.cognitive.order_intent import stable_intent_id_from_decision
from bolsa_analytics.cognitive.submit_intent import (
    bind_venue_order,
    mark_send_attempted,
    mark_submit_filled,
    reconstruct_unknown,
    record_submit_intent,
)


class SubmitIntentCoordinator:
    """record → send_attempted → recover UNKNOWN → persist-after-adapter."""

    def __init__(
        self,
        *,
        submit_intent_store: Any | None = None,
        resolve_broker_venue: Any | None = None,
    ) -> None:
        self._store = submit_intent_store
        self._resolve_broker_venue = resolve_broker_venue

    async def try_recover_in_flight(
        self,
        *,
        result: dict[str, Any],
        intent: Any,
        contract_status: str,
        decision_id: str,
    ) -> bool:
        store = self._store
        if store is None or not decision_id:
            return False
        getter = getattr(store, "get", None)
        if getter is None:
            return False
        try:
            durable = await getter(decision_id)
        except Exception:  # noqa: BLE001
            return False
        if durable is None:
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

    async def record_before_submit(
        self,
        *,
        result: dict[str, Any],
        intent: Any,
        contract_status: str,
        decision_id: str,
        account_id: str,
    ) -> Any | None:
        venue = "paper"
        if self._resolve_broker_venue is not None:
            venue = await self._resolve_broker_venue(account_id)
        durable = record_submit_intent(
            decision_id=decision_id,
            # V1.91: decision_id may be composite (decision|action|side) so OPEN/T1/EXIT
            # each get a unique intent_id under submit_intents_intent_id_key.
            intent_id=stable_intent_id_from_decision(decision_id),
            order_id=stable_order_id_from_decision(decision_id),
            account_id=account_id,
            venue=venue,
        )
        store = self._store
        if store is None:
            return mark_send_attempted(durable)
        try:
            await store.put(durable)
            durable = mark_send_attempted(durable)
            await store.put(durable)
        except Exception as exc:  # noqa: BLE001
            result["trade"] = {
                "status": "error",
                "reason": str(exc) or "submit_intent_persist_failed",
            }
            result["intent"] = {
                **intent.to_dict(),
                "status": "error",
                "contract": contract_status,
            }
            return None
        result["submitIntent"] = durable.to_dict()
        return durable

    async def persist_after_adapter(
        self,
        *,
        durable: Any,
        pb: Any,
        result: dict[str, Any],
    ) -> None:
        store = self._store
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
        except Exception:  # noqa: BLE001
            pass
