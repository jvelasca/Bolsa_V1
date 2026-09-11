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
    """Umbrales de degradación de la estrategia activa (fail-safe: conservadores).

    Los cuatro primeros son *predictivos* (del LAB). Los cuatro últimos son *observados*
    (ejecución SIM real; V2.28 / A10): su semántica es distinta y **nunca** degradan por
    debajo de ``min_observed_trades`` round-trips cerrados (guarda de muestra mínima).

    V2.32.1 (auditoría): los umbrales *predictivos* usan ``None`` = "sin configurar",
    igual que los observados. Un ``0.0`` real fingiría una decisión que nadie tomó
    (una estrategia con ``credibility=0.02`` no debería pasar como sana por defecto);
    con ``None`` ese indicador no degrada por su ausencia, pero tampoco inventa un cero.

    Nota sobre el drawdown observado: se expresa en magnitud positiva (p. ej. ``20`` = 20%
    de caída) y su umbral es un TECHO. La comparación con signo correcto la resuelve
    ``StrategyHealth._observed_degraded``; aquí solo se declara el valor.
    """

    min_edge: float | None = None
    min_wfe: float | None = None
    min_dsr: float | None = None
    min_credibility: float | None = None
    # --- Umbrales observados (V2.28 / A10) ---
    min_observed_trades: int = 10
    min_observed_return_pct: float | None = None
    max_observed_drawdown_pct: float | None = None
    min_observed_win_rate: float | None = None
    min_observed_profit_factor: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float]:
        """Umbrales persistibles en el snapshot de salud.

        Los ``None`` se omiten: un umbral no configurado no debe viajar como 0 (que
        activaría una degradación por defecto no intencionada). Aplica a predictivos y
        observados por igual (V2.32.1: misma filosofía en ambos bloques).
        """
        out: dict[str, float] = {
            "min_observed_trades": float(self.min_observed_trades),
        }
        if self.min_edge is not None:
            out["edge"] = self.min_edge
        if self.min_wfe is not None:
            out["walk_forward_efficiency"] = self.min_wfe
        if self.min_dsr is not None:
            out["dsr"] = self.min_dsr
        if self.min_credibility is not None:
            out["credibility"] = self.min_credibility
        if self.min_observed_return_pct is not None:
            out["observed_return_pct"] = self.min_observed_return_pct
        if self.max_observed_drawdown_pct is not None:
            out["observed_max_drawdown_pct"] = self.max_observed_drawdown_pct
        if self.min_observed_win_rate is not None:
            out["observed_win_rate"] = self.min_observed_win_rate
        if self.min_observed_profit_factor is not None:
            out["observed_profit_factor"] = self.min_observed_profit_factor
        return out


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
    observed_trades = _int(metrics.get("observed_trades"))

    health = StrategyHealth(
        version_id=version_id,
        as_of=as_of,
        edge=edge,
        walk_forward_efficiency=wfe,
        dsr=dsr,
        credibility=credibility,
        thresholds=th.as_dict(),
        # V2.28 / A10: bloque observado (ejecución SIM real atribuida a la versión).
        observed_return_pct=_num(metrics.get("observed_return_pct")),
        observed_max_drawdown_pct=_num(metrics.get("observed_max_drawdown_pct")),
        observed_win_rate=_num(metrics.get("observed_win_rate")),
        observed_profit_factor=_num(metrics.get("observed_profit_factor")),
        observed_trades=observed_trades,
    )

    breaches: list[str] = []
    if th.min_edge is not None and edge is not None and edge < th.min_edge:
        breaches.append("edge")
    if th.min_wfe is not None and wfe is not None and wfe < th.min_wfe:
        breaches.append("walk_forward_efficiency")
    if th.min_dsr is not None and dsr is not None and dsr < th.min_dsr:
        breaches.append("dsr")
    if (
        th.min_credibility is not None
        and credibility is not None
        and credibility < th.min_credibility
    ):
        breaches.append("credibility")
    # Degradación observada: se delega en la entidad, que aplica la guarda de muestra
    # mínima y la semántica de techo del drawdown. Si degrada por observado, se registran
    # los motivos concretos para que el snapshot sea auditable.
    if health.observed_degraded:
        breaches.extend(_observed_breaches(health, th))

    degraded = bool(breaches)
    return VigilanceDecision(
        version_id=version_id,
        decision=DECISION_RELAB if degraded else DECISION_CONTINUE,
        degraded=degraded,
        breaches=tuple(breaches),
        health=health,
    )


def _observed_breaches(health: StrategyHealth, th: HealthThresholds) -> list[str]:
    """Motivos concretos de la degradación observada (auditoría del snapshot)."""
    out: list[str] = []
    if (
        th.min_observed_return_pct is not None
        and health.observed_return_pct is not None
        and health.observed_return_pct < th.min_observed_return_pct
    ):
        out.append("observed_return_pct")
    if (
        th.max_observed_drawdown_pct is not None
        and health.observed_max_drawdown_pct is not None
        and health.observed_max_drawdown_pct > th.max_observed_drawdown_pct
    ):
        out.append("observed_max_drawdown_pct")
    if (
        th.min_observed_win_rate is not None
        and health.observed_win_rate is not None
        and health.observed_win_rate < th.min_observed_win_rate
    ):
        out.append("observed_win_rate")
    if (
        th.min_observed_profit_factor is not None
        and health.observed_profit_factor is not None
        and health.observed_profit_factor < th.min_observed_profit_factor
    ):
        out.append("observed_profit_factor")
    return out


def _num(raw: Any) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _int(raw: Any) -> int | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    return None
