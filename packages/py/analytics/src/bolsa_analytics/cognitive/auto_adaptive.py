"""AUTO-8 — Adaptive AUTO (slice 1): recomendación por estrategia, PURA y READ-ONLY.

Cumple la mitad del invariante del roadmap §10: _Adaptive recomienda, el motor
determinista decide._ Este módulo **no** decide nada ni produce órdenes; produce un
``AdaptivePlan`` (rotación + asignación) que el motor ``auto_v2_entry.plan_v2_tick``
consume como **entradas** — pausando candidatas antes del ranking y estrechando el
techo de riesgo por estrategia — sin tocar jamás los gates duros (gobernador, kill
switch, RiskGate/Simulation Gate, sizing).

Qué recomienda, a partir de la self-evaluation de AUTO-7 (``StrategySelfEvaluation``):

* **Rotación** (``recommend_rotation``): pausa una versión de estrategia cuando su
  salud es **probadamente negativa** (muestra decisoria y expectancy <= 0 o profit
  factor < 1) o cuando, en un régimen adverso (``TREND_DOWN``/``HIGH_VOL``), su muestra
  no es confiable (no decisoria) y su win rate cae por debajo del suelo declarado.
  Sin dato ⇒ NO se rota (se declara ``unknown``), nunca se pausa a ciegas.
* **Asignación** (``recommend_allocation``): reparte el presupuesto **relativo** de
  riesgo entre las estrategias activas, proporcional a su expectancy positiva si hay al
  menos una decisoria con expectancy > 0, y uniforme (``1/n``) en caso contrario. El
  resultado es un **multiplicador** ``share * n`` acotado a ``[0, 1]``: la asignación
  SOLO estrecha el riesgo por operación, nunca lo ensancha.

Disciplina de medición (la del repo): todo lo que no se pudo medir se DECLARA, no se
rellena. Una estrategia sin muestra no es "mala", es desconocida; una pausa exige
evidencia, no ausencia de evidencia.

Read-only por contrato: ``AdaptivePlan.read_only`` es ``True`` y su ``decisive`` de
origen NO es un permiso (la decide el motor determinista).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from bolsa_analytics.cognitive.auto_self_evaluation import StrategySelfEvaluation

__all__ = [
    "ADAPTIVE_KEY",
    "ADAPTIVE_STRATEGY_PAUSED",
    "ADAPTIVE_STRATEGY_REGIME_RISK",
    "ADAPTIVE_STRATEGY_UNHEALTHY",
    "ADAPTIVE_ADVERSE_REGIMES",
    "ADAPTIVE_WIN_RATE_FLOOR_DEFAULT",
    "AdaptivePlan",
    "AllocationPlan",
    "RotationDecision",
    "RotationPlan",
    "StrategyHealth",
    "build_adaptive_plan",
    "build_strategy_health",
    "recommend_allocation",
    "recommend_rotation",
]

ADAPTIVE_KEY = "adaptive"

#: Motivos de rotación (vocabulario PROPIO de este módulo; el journal de la capa de
#: aplicación los lleva en el detalle de ``adaptive_strategy_paused``). La casa única
#: del literal de pausa en el journal es ``bolsa_application.auto_reason_codes``; aquí
#: se re-declara el motivo de pausa para que este módulo puro no dependa de application.
ADAPTIVE_STRATEGY_UNHEALTHY = "adaptive_strategy_unhealthy"
ADAPTIVE_STRATEGY_REGIME_RISK = "adaptive_strategy_regime_risk"
ADAPTIVE_STRATEGY_PAUSED = "adaptive_strategy_paused"

#: Regímenes de mercado (``MarketRegime`` del gobernador) adversos para la rotación:
#: una estrategia SIN muestra confiable no se activa a ciegas cuando el mercado baja
#: confirmado o está revuelto.
ADAPTIVE_ADVERSE_REGIMES: frozenset[str] = frozenset({"TREND_DOWN", "HIGH_VOL"})

#: Suelo de win rate (0..1) para la regla de régimen adverso. Por debajo, una estrategia
#: no decisoria se pausa en régimen adverso (nunca se pausa una muestra anecdótica buena).
ADAPTIVE_WIN_RATE_FLOOR_DEFAULT = 0.35


def _clamp_unit(value: float) -> float:
    """Multiplicador acotado a ``[0, 1]`` (un no-número o no-finito colapsa a ``0.0``)."""
    if value != value or value in (float("inf"), float("-inf")):
        return 0.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


@dataclass(frozen=True, slots=True)
class StrategyHealth:
    """Vista derivada de ``StrategySelfEvaluation`` con SOLO lo que Adaptive consume.

    Es un contrato explícito (frozen): Adaptive no lee el informe entero, lee estos
    campos. ``from_evaluation`` es la única forma de construirlo, para que la semántica
    de "salud" no se disperse entre dos shapes.
    """

    strategy_version: str
    trades: int
    decisive: bool
    expectancy_currency: Decimal | None
    profit_factor: float | None
    win_rate: float | None

    @classmethod
    def from_evaluation(cls, row: StrategySelfEvaluation) -> StrategyHealth:
        return cls(
            strategy_version=row.strategy_version,
            trades=row.trades,
            decisive=row.decisive,
            expectancy_currency=row.expectancy_currency,
            profit_factor=row.profit_factor,
            win_rate=row.win_rate,
        )


def build_strategy_health(
    by_strategy: Sequence[StrategySelfEvaluation],
) -> tuple[StrategyHealth, ...]:
    """Proyección read-only de las filas de self-evaluation al contrato de Adaptive."""
    return tuple(StrategyHealth.from_evaluation(row) for row in by_strategy)


@dataclass(frozen=True, slots=True)
class RotationDecision:
    """Veredicto de rotación para UNA versión de estrategia."""

    strategy_version: str
    active: bool
    reason: str | None = None  # motivo de pausa; ``None`` si activa


@dataclass(frozen=True, slots=True)
class RotationPlan:
    """Recomendación de rotación del tick: qué estrategias pausar y por qué."""

    decisions: tuple[RotationDecision, ...]

    @property
    def paused(self) -> frozenset[str]:
        return frozenset(
            d.strategy_version for d in self.decisions if not d.active
        )

    def reason_for(self, strategy_version: str) -> str | None:
        for d in self.decisions:
            if d.strategy_version == strategy_version and not d.active:
                return d.reason
        return None

    def is_paused(self, strategy_version: str) -> bool:
        return str(strategy_version or "") in self.paused

    def as_dict(self) -> dict[str, Any]:
        return {
            "paused": sorted(self.paused),
            "byStrategy": [
                {
                    "strategyVersion": d.strategy_version,
                    "active": d.active,
                    "reason": d.reason,
                }
                for d in self.decisions
            ],
        }


@dataclass(frozen=True, slots=True)
class AllocationPlan:
    """Multiplicadores de riesgo por estrategia (solo estrechan: cada valor en ``[0, 1]``).

    Una versión ausente del mapa equivale a ``1.0`` (sin estrechamiento): la ausencia no
    es una pausa, es "no hubo nada que estrechar".
    """

    multipliers: dict[str, float]

    def multiplier_for(self, strategy_version: str) -> float:
        return self.multipliers.get(str(strategy_version or ""), 1.0)

    def as_dict(self) -> dict[str, Any]:
        return {"riskMultipliers": dict(sorted(self.multipliers.items()))}


@dataclass(frozen=True, slots=True)
class AdaptivePlan:
    """Recomendación Adaptive completa del tick (rotación + asignación + régimen)."""

    rotation: RotationPlan
    allocation: AllocationPlan
    regime: str | None = None
    read_only: bool = True

    def is_paused(self, strategy_version: str) -> bool:
        return self.rotation.is_paused(strategy_version)

    def risk_multiplier_for(self, strategy_version: str) -> float:
        return self.allocation.multiplier_for(strategy_version)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": ADAPTIVE_KEY,
            "readOnly": self.read_only,
            "regime": self.regime,
            "rotation": self.rotation.as_dict(),
            "allocation": self.allocation.as_dict(),
        }


def recommend_rotation(
    by_strategy: Sequence[StrategySelfEvaluation],
    regime: str | None,
    *,
    win_rate_floor: float = ADAPTIVE_WIN_RATE_FLOOR_DEFAULT,
) -> RotationPlan:
    """(PURA) decide qué versiones pausar, con reglas deterministas y declarativas.

    Orden de evaluación (la primera que aplica gana el motivo):

    1. ``adaptive_strategy_unhealthy`` — salud **probadamente** negativa: muestra
       decisoria y (expectancy <= 0 o profit factor < 1).
    2. ``adaptive_strategy_regime_risk`` — régimen adverso (``TREND_DOWN``/``HIGH_VOL``)
       y muestra NO decisoria y win rate por debajo del suelo: no se activa a ciegas en
       un mercado que castiga.

    El resto queda ACTIVE. Sin dato ⇒ no se rota (el desconocido no es un defecto).
    """
    adverse = (str(regime or "").strip().upper() in ADAPTIVE_ADVERSE_REGIMES)
    decisions: list[RotationDecision] = []
    for row in by_strategy:
        health = StrategyHealth.from_evaluation(row)
        reason: str | None = None
        if health.decisive:
            expectancy_bad = (
                health.expectancy_currency is not None
                and health.expectancy_currency <= Decimal("0")
            )
            pf_bad = (
                health.profit_factor is not None and health.profit_factor < 1.0
            )
            if expectancy_bad or pf_bad:
                reason = ADAPTIVE_STRATEGY_UNHEALTHY
        if reason is None and adverse and not health.decisive:
            if health.win_rate is not None and health.win_rate < win_rate_floor:
                reason = ADAPTIVE_STRATEGY_REGIME_RISK
        decisions.append(
            RotationDecision(
                strategy_version=health.strategy_version,
                active=reason is None,
                reason=reason,
            )
        )
    return RotationPlan(tuple(decisions))


def recommend_allocation(
    active: Iterable[str],
    by_strategy: Sequence[StrategySelfEvaluation],
) -> AllocationPlan:
    """(PURA) multiplicador de riesgo por estrategia activa (solo estrecha, ``[0, 1]``).

    ``active`` son las versiones NO pausadas (la rotación ya decidió quién compite).
    Reparto:

    * Si hay al menos una activa **decisoria** con expectancy > 0, el presupuesto se
      reparte proporcional a la expectancy **positiva** de cada fila (``no negativa``:
      una expectancy ``None`` o ``<= 0`` pesa 0 y su multiplicador cae a 0).
    * Si no hay ninguna decisoria positiva, reparto UNIFORME ``1/n`` (fail-safe: sin
      evidencia de quién es mejor, no se favorece a nadie).

    El multiplicador final es ``share * n`` acotado a ``[0, 1]``: una estrategia que
    recibe su parte justa queda en ``1.0``, una con más que su parte no se ensancha
    (el techo es ``1.0``) y una sin expectancy positiva queda en ``0``.
    """
    active_set = {str(v or "") for v in active}
    rows = [row for row in by_strategy if row.strategy_version in active_set]
    if not rows:
        return AllocationPlan({})
    n = len(rows)

    positive: dict[str, float] = {}
    for row in rows:
        if row.expectancy_currency is not None and row.expectancy_currency > 0:
            positive[row.strategy_version] = float(row.expectancy_currency)
    decisive_positive = any(
        row.decisive and row.strategy_version in positive for row in rows
    )

    if decisive_positive and positive:
        total = sum(positive.values())
        shares = {version: weight / total for version, weight in positive.items()}
    else:
        shares = {row.strategy_version: 1.0 / n for row in rows}

    multipliers: dict[str, float] = {}
    for row in rows:
        share = shares.get(row.strategy_version, 0.0)
        multipliers[row.strategy_version] = _clamp_unit(share * n)
    return AllocationPlan(multipliers)


def build_adaptive_plan(
    by_strategy: Sequence[StrategySelfEvaluation],
    regime: str | None,
    *,
    win_rate_floor: float = ADAPTIVE_WIN_RATE_FLOOR_DEFAULT,
) -> AdaptivePlan:
    """(PURA) plan Adaptive completo: rotación + asignación sobre las mismas filas.

    ``regime`` es el ``MarketRegime`` del gobernador (``TREND_UP``/``TREND_DOWN``/
    ``RANGE``/``HIGH_VOL``/``LOW_VOL``/``UNKNOWN``), no el eje operativo.
    """
    rotation = recommend_rotation(by_strategy, regime, win_rate_floor=win_rate_floor)
    active_versions = [
        row.strategy_version for row in by_strategy if not rotation.is_paused(row.strategy_version)
    ]
    allocation = recommend_allocation(active_versions, by_strategy)
    return AdaptivePlan(rotation=rotation, allocation=allocation, regime=regime)
