"""V2.25 / A10 — fase FINALISTA + Promotion Gate (anti strategy-chasing).

Convierte una candidata aprobada en una ``StrategyVersion`` **inmutable** (hash estable
de su definición) y aplica el Promotion Gate completo (seis gates cuantitativos +
COACH + shadow/paper) antes de permitir que sea ACTIVE.

Regla anti strategy-chasing (auditoría V2.24 §20): una candidata del LAB **nunca**
sustituye a la estrategia activa sin Promotion Gate + validación shadow/paper. El LAB
no cambia la activa: propone; el gate decide.

Sin DB ni red: cálculo determinista. La persistencia la hace el store del lifecycle.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import (
    PROMOTION_GATES,
    CoachAssessment,
    GateResult,
    ShadowValidationResult,
    StrategyCandidate,
    StrategyFinalist,
    StrategyPromotion,
    StrategyValidation,
    evaluate_admin_promotion,
    evaluate_promotion,
)

__all__ = [
    "ActiveStrategyRef",
    "PromotionDecision",
    "build_strategy_version",
    "decide_admin_promotion",
    "decide_promotion",
    "definition_hash",
]


def definition_hash(definition: Mapping[str, Any]) -> str:
    """Hash estable de una definición de estrategia (orden-insensible, estable)."""
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:32]}"


def build_strategy_version(
    *,
    candidate: StrategyCandidate,
    name: str,
    definition: Mapping[str, Any] | None = None,
) -> StrategyFinalist:
    """Fase FINALISTA: materializa la ``StrategyVersion`` inmutable de una candidata.

    La definición incluye la familia, los params y el ``data_snapshot_id`` (si existe)
    para que la versión sea reproducible. El hash es su identidad inmutable.
    """
    effective: dict[str, Any] = {
        "family": candidate.strategy_family,
        "params": dict(candidate.params),
        "instrument_id": candidate.instrument_id,
    }
    if definition is not None:
        effective.update(dict(definition))
    if candidate.data_snapshot_id:
        effective["data_snapshot_id"] = candidate.data_snapshot_id
    return StrategyFinalist(
        candidate_id=candidate.id,
        version_id=f"ver-{candidate.id}-{definition_hash(effective)[7:19]}",
        name=name,
        definition_hash=definition_hash(effective),
        definition=effective,
    )


@dataclass(frozen=True, slots=True)
class ActiveStrategyRef:
    """Referencia mínima a la estrategia activa actual de un instrumento."""

    version_id: str
    candidate_id: str
    instrument_id: str


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """Resultado del Promotion Gate: promocionar o no, con motivos auditables."""

    promotion: StrategyPromotion
    finalist: StrategyFinalist
    replaces: ActiveStrategyRef | None = None
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def promoted(self) -> bool:
        return self.promotion.promoted


def decide_promotion(
    *,
    finalist: StrategyFinalist,
    gates: Sequence[GateResult],
    coach: CoachAssessment,
    shadow: ShadowValidationResult | None = None,
    active: ActiveStrategyRef | None = None,
    require_gate_for_active: bool = True,
) -> PromotionDecision:
    """Promotion Gate AUTOMÁTICO: seis gates + COACH + evidencia shadow.

    V2.32 / A12: la autoridad shadow es la **evidencia ejecutada** (``shadow``). Esta
    es la compuerta de la ruta autónoma y NO acepta override humano (V2.35.1, auditoría
    P2-01): sin evidencia que pase, no hay promoción. El override administrativo vive
    exclusivamente en :func:`decide_admin_promotion`.

    Si ya hay una estrategia ``active`` y ``require_gate_for_active`` (default), el
    reemplazo exige que TODOS los gates estén PASS, que el COACH no vete y que haya
    shadow/paper validado. Además, si el candidato es el MISMO que la activa, no hay
    nada que promover (no se re-promociona a sí mismo).
    """
    return _decide_promotion(
        finalist=finalist,
        gates=gates,
        coach=coach,
        promotion=evaluate_promotion(
            finalist=finalist,
            validation=StrategyValidation(finalist_id=finalist.version_id, gates=tuple(gates)),
            coach=coach,
            shadow=shadow,
        ),
        active=active,
        require_gate_for_active=require_gate_for_active,
    )


def decide_admin_promotion(
    *,
    finalist: StrategyFinalist,
    gates: Sequence[GateResult],
    coach: CoachAssessment,
    shadow_validated: bool,
    active: ActiveStrategyRef | None = None,
    require_gate_for_active: bool = True,
) -> PromotionDecision:
    """Promotion Gate ADMIN/MANUAL: única vía que acepta el override ``shadow_validated``.

    V2.35.1 (auditoría P2-01): separada de la compuerta automática para que la frontera
    de seguridad sea explícita. Pensada para herramientas administrativas puntuales
    (rollout/operación), nunca para el hot path AUTO. Comparte el núcleo de decisión con
    :func:`decide_promotion`; solo cambia la resolución de la evidencia shadow.

    Fail-closed: el override es un ``bool`` explícito; ``False`` no promociona y ``True``
    queda auditado como ``shadow_override_operador``.
    """
    return _decide_promotion(
        finalist=finalist,
        gates=gates,
        coach=coach,
        promotion=evaluate_admin_promotion(
            finalist=finalist,
            validation=StrategyValidation(finalist_id=finalist.version_id, gates=tuple(gates)),
            coach=coach,
            shadow_validated=shadow_validated,
        ),
        active=active,
        require_gate_for_active=require_gate_for_active,
    )


def _decide_promotion(
    *,
    finalist: StrategyFinalist,
    gates: Sequence[GateResult],
    coach: CoachAssessment,
    promotion: StrategyPromotion,
    active: ActiveStrategyRef | None,
    require_gate_for_active: bool,
) -> PromotionDecision:
    """Núcleo compartido: aplica la promoción ya evaluada a la política de reemplazo.

    Único punto donde se decide si se sustituye la activa (anti strategy-chasing), para
    que la compuerta automática y la administrativa no dupliquen esta lógica.
    """
    reasons = list(promotion.reasons)

    replaces: ActiveStrategyRef | None = None
    if active is not None:
        if active.candidate_id == finalist.candidate_id:
            reasons.append("ya_activa")
        elif require_gate_for_active:
            replaces = active
        else:
            replaces = active

    promoted = promotion.promoted and not reasons
    return PromotionDecision(
        promotion=StrategyPromotion(
            finalist_id=promotion.finalist_id,
            promoted=promoted,
            reasons=tuple(reasons),
            shadow_validated=promotion.shadow_validated,
            shadow_validation_id=promotion.shadow_validation_id,
        ),
        finalist=finalist,
        replaces=replaces if promoted else None,
        reasons=tuple(reasons),
    )


def promotion_gate_names() -> tuple[str, ...]:
    """Nombres de los gates exigidos (para mensajes/telemetría)."""
    return PROMOTION_GATES
