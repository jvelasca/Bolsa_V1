"""
Alarmas B1 — auto-ruta de hits de rastreador vía política inform_only / alert.

No ejecuta paper_auto ni live (eso es Camino B paper / D). Solo vigila entrada/salida.
@see docs/engineering/research-radar-unification-2026-07-31.md
"""

from __future__ import annotations

import logging
from typing import Any

from bolsa_application.execution_router import ExecutionRouter, ExecutionRouteResult
from bolsa_application.scans import ScanHit
from bolsa_domain.entities.tracker_definition import TrackerDefinitionRecord
from bolsa_domain.repositories.execution_policy_repository import ExecutionPolicyRepository

logger = logging.getLogger(__name__)

# Solo modos seguros de alarma (B1). paper_auto / live_auto requieren CTA humano.
ALARM_SAFE_MODES = frozenset({"inform_only", "alert"})


def execution_route_to_dict(route: ExecutionRouteResult) -> dict[str, Any]:
    return {
        "policyId": route.policy_id,
        "mode": route.mode,
        "actions": [
            {
                "instrumentId": a.instrument_id,
                "signalKind": a.signal_kind,
                "status": a.status,
                "reason": a.reason,
                "transactionId": a.transaction_id,
                "dispatches": [
                    {
                        "channel": d.channel,
                        "ok": d.ok,
                        "error": d.error,
                    }
                    for d in (a.dispatches or [])
                ],
            }
            for a in route.actions
        ],
    }


def hits_as_route_payload(hits: list[ScanHit]) -> list[dict[str, Any]]:
    """Convierte hits tipados al dict camelCase que espera ExecutionRouter."""
    out: list[dict[str, Any]] = []
    for hit in hits:
        signal = hit.signal
        out.append(
            {
                "instrumentId": hit.instrument_id,
                "symbol": hit.symbol,
                "name": hit.name,
                "signal": {
                    "id": signal.id,
                    "instrumentId": signal.instrument_id,
                    "timestamp": signal.timestamp,
                    "kind": signal.kind,
                    "strategyDefinitionId": signal.strategy_definition_id,
                    "strategyVersion": signal.strategy_version,
                    "barIndex": signal.bar_index,
                    "price": signal.price,
                    "dataVersion": signal.data_version,
                    "indicatorSnapshotHash": signal.indicator_snapshot_hash,
                    "presetKey": signal.preset_key,
                },
            }
        )
    return out


async def route_tracker_alarms(
    *,
    tracker: TrackerDefinitionRecord,
    hits: list[ScanHit] | list[dict[str, Any]],
    policies: ExecutionPolicyRepository,
    router: ExecutionRouter,
) -> ExecutionRouteResult | None:
    """
    Si el rastreador tiene defaultExecutionPolicyId y el modo es inform_only|alert,
    enruta los hits. Devuelve None si no aplica o no hay hits.
    """
    definition = tracker.definition or {}
    policy_id = definition.get("defaultExecutionPolicyId")
    if not policy_id or not isinstance(policy_id, str):
        return None
    if not hits:
        return None

    policy = await policies.get_policy(policy_id)
    if policy is None or not policy.enabled:
        logger.info(
            "Tracker %s: política %s ausente o deshabilitada — sin alarmas",
            tracker.id,
            policy_id,
        )
        return None
    if policy.mode not in ALARM_SAFE_MODES:
        logger.info(
            "Tracker %s: política %s modo=%s — auto-alarma omitida (solo inform/alert)",
            tracker.id,
            policy_id,
            policy.mode,
        )
        return None

    hit_payloads: list[dict[str, Any]]
    if hits and isinstance(hits[0], ScanHit):
        hit_payloads = hits_as_route_payload(hits)
    else:
        # Lista heterogénea: en la rama no-ScanHit solo hay dicts (payload ya serializado).
        hit_payloads = [payload for payload in hits if isinstance(payload, dict)]

    try:
        return await router.execute(policy_id, hit_payloads)
    except Exception:
        logger.exception("Tracker %s: falló auto-ruta de alarmas", tracker.id)
        return None
