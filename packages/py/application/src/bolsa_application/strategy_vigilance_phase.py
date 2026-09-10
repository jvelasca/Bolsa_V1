"""V2.25 / A10 — vigilancia de la estrategia ACTIVA (StrategyHealth).

Evalúa la salud de una estrategia ACTIVE a partir de sus métricas de edge/robustez
(``edge``, ``walk_forward_efficiency``, ``dsr``, ``credibility``) contra umbrales y
decide:

* **healthy** → la estrategia sigue en AUTO.
* **degraded** → se dispara re-LABORATORIO; **nunca** un swap directo de la activa
  por otra del LAB (regla anti strategy-chasing, auditoría V2.24 §20).

Determinista y sin DB/red: el orquestador (V2.26) persiste los snapshots y arranca
el re-LAB cuando esta fase lo pide.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import (
    StrategyHealth,
    StrategyLifecycleState,
)

__all__ = [
    "DECISION_CONTINUE",
    "DECISION_RELAB",
    "HealthThresholds",
    "VigilanceDecision",
    "evaluate_active_health",
]


DECISION_CONTINUE = "continue"
DECISION_RELAB = "relab"


@dataclass(frozen=True, slots=True)
class HealthThresholds:
    """Umbrales de degradación de la estrategia activa (fail-safe: conservadores)."""

    min_edge: float = 0.0
    min_wfe: float = 0.0
    min_dsr: float = 0.0
    min_credibility: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float]:
        return {
            "edge": self.min_edge,
            "walk_forward_efficiency": self.min_wfe,
            "dsr": self.min_dsr,
            "credibility": self.min_credibility,
        }


@dataclass(frozen=True, slots=True)
class VigilanceDecision:
    """Decisión de vigilancia: seguir en AUTO o disparar re-LAB (nunca swap directo)."""

    version_id: str
    decision: str
    degraded: bool
    breaches: tuple[str, ...] = ()
    health: StrategyHealth | None = None

    @property
    def relab(self) -> bool:
        return self.decision == DECISION_RELAB

    @property
    def target_state(self) -> StrategyLifecycleState | None:
        """Estado al que transiciona la estrategia activa (DEGRADED ⇒ vuelve al LAB)."""
        return StrategyLifecycleState.DEGRADED if self.degraded else None


def evaluate_active_health(
    *,
    version_id: str,
    as_of: str,
    metrics: Mapping[str, Any],
    thresholds: HealthThresholds | None = None,
) -> VigilanceDecision:
    """Evalúa la salud de la activa y decide continuar o re-LAB.

    Cualquier indicador conocido por debajo de su umbral ⇒ ``degraded`` ⇒ re-LAB.
    Falta de un indicador NO es degradación por sí sola (no se inventa evidencia),
    pero el snapshot resultante solo contiene los indicadores disponibles.
    """
    th = thresholds or HealthThresholds()
    edge = _num(metrics.get("edge"))
    wfe = _num(metrics.get("walk_forward_efficiency") or metrics.get("wfe"))
    dsr = _num(metrics.get("dsr"))
    credibility = _num(metrics.get("credibility"))

    health = StrategyHealth(
        version_id=version_id,
        as_of=as_of,
        edge=edge,
        walk_forward_efficiency=wfe,
        dsr=dsr,
        credibility=credibility,
        thresholds=th.as_dict(),
    )

    breaches: list[str] = []
    if edge is not None and edge < th.min_edge:
        breaches.append("edge")
    if wfe is not None and wfe < th.min_wfe:
        breaches.append("walk_forward_efficiency")
    if dsr is not None and dsr < th.min_dsr:
        breaches.append("dsr")
    if credibility is not None and credibility < th.min_credibility:
        breaches.append("credibility")

    degraded = bool(breaches)
    return VigilanceDecision(
        version_id=version_id,
        decision=DECISION_RELAB if degraded else DECISION_CONTINUE,
        degraded=degraded,
        breaches=tuple(breaches),
        health=health,
    )


def _num(raw: Any) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    return None
