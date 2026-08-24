"""Proyección decision_session (kind=propose) → OrderProposalV1 (refs-only)."""

from __future__ import annotations

from typing import Any, Literal

from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord

OrderProposalStatus = Literal["open", "confirmed", "rejected", "superseded", "expired"]

_REC_TO_PROPOSAL: dict[str, OrderProposalStatus] = {
    "approved": "confirmed",
    "rejected": "rejected",
    "expired": "expired",
    "superseded": "superseded",
}


def _derive_proposal_status(session: DecisionSessionRecord) -> OrderProposalStatus:
    payload = session.payload or {}
    rec = payload.get("recommendation")
    rec_status = ""
    if isinstance(rec, dict):
        rec_status = str(rec.get("status") or "")
    mapped = _REC_TO_PROPOSAL.get(rec_status)
    if mapped is not None:
        return mapped
    if session.status == "closed":
        return "confirmed"
    return "open"


def session_to_order_proposal(session: DecisionSessionRecord) -> dict[str, Any] | None:
    """Maps a propose session row to OrderProposalV1 dict; None if not mappable."""
    if session.kind != "propose":
        return None

    payload = session.payload or {}
    decision_id = session.decision_id or payload.get("decisionId")
    recommendation_id = session.recommendation_id
    if recommendation_id is None and isinstance(payload.get("recommendation"), dict):
        recommendation_id = payload["recommendation"].get("recommendationId")

    if not decision_id or not recommendation_id:
        return None

    status = _derive_proposal_status(session)
    closed_at: str | None = None
    if status != "open" and session.status == "closed":
        closed_at = session.created_at

    return {
        "artifactType": "ART-ORDER-PROPOSAL",
        "schemaVersion": "1.0.0",
        "proposalId": session.id,
        "decisionId": str(decision_id),
        "recommendationId": str(recommendation_id),
        "sessionId": session.id,
        "accountId": session.account_id,
        "instrumentId": session.instrument_id,
        "status": status,
        "createdAt": session.created_at,
        "closedAt": closed_at,
    }
