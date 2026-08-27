"""V1.18 L2a — Origin DecisionPackage snapshot write-once (ADR-038).

Se anida en ``position_state`` JSONB. No Alembic. No inventa Package.
"""

from __future__ import annotations

from typing import Any

ORIGIN_DECISION_PACKAGE_KEY = "originDecisionPackage"


def _finite(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _trim(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def extract_decision_package_from_session_payload(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    runtime = payload.get("runtime")
    if isinstance(runtime, dict):
        raw = runtime.get("decisionPackage") or runtime.get("decision_package")
        if isinstance(raw, dict) and raw:
            return dict(raw)
    top = payload.get("decisionPackage") or payload.get("decision_package")
    return dict(top) if isinstance(top, dict) and top else None


def freeze_origin_decision_package(
    *,
    package: dict[str, Any] | None,
    trade_plan: dict[str, Any],
    decision_id: str,
    instrument_id: str,
) -> dict[str, Any] | None:
    """Copia slim write-once. Sin package → None (fail-closed; no inventar)."""
    if not isinstance(package, dict) or not package:
        return None
    pkg_inst = _trim(package.get("instrumentId") or package.get("instrument_id"))
    if pkg_inst and pkg_inst != instrument_id:
        return None

    action = package.get("action")
    action_s = str(action) if action is not None else None
    confidence = package.get("overallConfidence") or package.get("overall_confidence")
    strength: float | None
    try:
        strength = float(confidence) if confidence is not None else None
        if strength is not None and strength != strength:
            strength = None
    except (TypeError, ValueError):
        strength = None

    direction = trade_plan.get("direction")
    direction_s = (
        direction
        if direction in ("long", "short")
        else (_trim(package.get("direction")) or "long")
    )

    return {
        "decisionId": decision_id,
        "instrumentId": instrument_id,
        "source": "fill_snapshot_v1",
        "action": action_s,
        "status": "active",
        "opinion": None,
        "strength": strength,
        "entry": _finite(trade_plan.get("entry"))
        or _finite(package.get("entry") or package.get("suggestedPrice")),
        "stop": _finite(trade_plan.get("structuralStop"))
        or _finite(package.get("stop")),
        "target1": _finite(trade_plan.get("target1")),
        "target2": _finite(trade_plan.get("target2")),
        "expectedRR": _finite(trade_plan.get("expectedRR") or trade_plan.get("expected_rr")),
        "riskAmount": _finite(trade_plan.get("riskAmount") or trade_plan.get("risk_amount")),
        "direction": direction_s,
        "tradePlanStatus": trade_plan.get("status")
        if isinstance(trade_plan.get("status"), str)
        else None,
        "hasOperationalPlan": True,
    }


def preserve_origin_decision_package(
    previous_blob: dict[str, Any] | None,
    next_blob: dict[str, Any],
) -> dict[str, Any]:
    """Protect/exit no deben borrar el snapshot de nacimiento."""
    if not isinstance(previous_blob, dict):
        return next_blob
    existing = previous_blob.get(ORIGIN_DECISION_PACKAGE_KEY)
    if isinstance(existing, dict) and existing:
        next_blob[ORIGIN_DECISION_PACKAGE_KEY] = dict(existing)
    return next_blob


def origin_thesis_from_position_state(
    state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Slice HTTP / aggregate — sin mega-blob DecisionPackage."""
    if not isinstance(state, dict):
        return None
    raw = state.get(ORIGIN_DECISION_PACKAGE_KEY)
    if not isinstance(raw, dict) or not raw:
        return None
    decision_id = _trim(raw.get("decisionId") or raw.get("decision_id"))
    if not decision_id:
        return None
    return {
        "decisionId": decision_id,
        "instrumentId": _trim(raw.get("instrumentId") or raw.get("instrument_id")),
        "status": raw.get("status") if isinstance(raw.get("status"), str) else "active",
        "opinion": raw.get("opinion") if isinstance(raw.get("opinion"), str) else None,
        "tradePlanStatus": raw.get("tradePlanStatus")
        if isinstance(raw.get("tradePlanStatus"), str)
        else None,
        "hasOperationalPlan": bool(raw.get("hasOperationalPlan", True)),
        "strength": _finite(raw.get("strength")),
        "entry": _finite(raw.get("entry")),
        "stop": _finite(raw.get("stop")),
        "target1": _finite(raw.get("target1")),
        "target2": _finite(raw.get("target2")),
        "expectedRR": _finite(raw.get("expectedRR")),
        "riskAmount": _finite(raw.get("riskAmount")),
        "direction": raw.get("direction")
        if raw.get("direction") in ("long", "short")
        else "long",
    }
