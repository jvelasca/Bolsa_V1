"""ART-ORDER-INTENT — voluntad autorizada (F3/F4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from bolsa_analytics.cognitive.recommendation import Recommendation

OrderIntentSide = Literal["buy", "sell"]
OrderIntentSource = Literal["human_supervised", "paper_auto", "policy_gate", "manual"]
OrderIntentStatus = Literal[
    "authorized",
    "executed",
    "cancelled",
    "rejected_by_gate",
    "expired",
]


@dataclass(frozen=True, slots=True)
class OrderIntent:
    intent_id: str
    account_id: str
    instrument_id: str
    side: OrderIntentSide
    quantity: float
    source: OrderIntentSource
    status: OrderIntentStatus
    authorized_by: Literal["human", "system"]
    authorized_at: str
    artifact_type: str = "ART-ORDER-INTENT"
    schema_version: str = "1.0.0"
    symbol: str | None = None
    limit_price: float | None = None
    recommendation_id: str | None = None
    decision_id: str | None = None
    policy_id: str | None = None
    policy_version: str | None = None
    gate_memory_id: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifactType": self.artifact_type,
            "schemaVersion": self.schema_version,
            "intentId": self.intent_id,
            "accountId": self.account_id,
            "instrumentId": self.instrument_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "limitPrice": self.limit_price,
            "recommendationId": self.recommendation_id,
            "decisionId": self.decision_id,
            "source": self.source,
            "status": self.status,
            "authorizedBy": self.authorized_by,
            "authorizedAt": self.authorized_at,
            "policyId": self.policy_id,
            "policyVersion": self.policy_version,
            "gateMemoryId": self.gate_memory_id,
            "notes": list(self.notes),
        }


def intent_from_recommendation(
    recommendation: Recommendation,
    *,
    account_id: str,
    authorized_by: Literal["human", "system"] = "human",
    source: OrderIntentSource = "human_supervised",
) -> OrderIntent:
    """Human/system confirma Recommendation → Intent (aún no Order)."""
    side: OrderIntentSide = "sell"
    if recommendation.action in {"recommend_long"}:
        side = "buy"
    elif recommendation.action in {"recommend_short", "exit_hint", "reduce"}:
        side = "sell"
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return OrderIntent(
        intent_id=f"INT-{uuid4().hex[:12]}",
        account_id=account_id,
        instrument_id=recommendation.instrument_id,
        side=side,
        quantity=recommendation.suggested_quantity,
        source=source,
        status="authorized",
        authorized_by=authorized_by,
        authorized_at=now,
        symbol=recommendation.symbol,
        limit_price=recommendation.suggested_price,
        recommendation_id=recommendation.recommendation_id,
        decision_id=recommendation.decision_id,
        policy_version=recommendation.policy_version,
        notes=("Confirmado desde Recommendation",),
    )
