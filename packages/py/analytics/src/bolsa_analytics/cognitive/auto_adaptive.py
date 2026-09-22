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
  riesgo entre las estrategias activas, proporcional a la expectancy positiva **de las
  que YA demostraron con muestra decisoria** y neutral (``unknown_multiplier``, por
  defecto ``1.0``) para las que no. El resultado es un **multiplicador** acotado a
  ``[0, 1]``: la asignación SOLO estrecha el riesgo por operación, nunca lo ensancha.

**Eje de evidencia de la asignación (AUTO-9).** El reparto pesa con el **R neto medido**
(``net_expectancy_r`` con ``net_r_measurement == COMPLETE``) cuando ese eje está medido
para TODO el grupo que compite; si no, cae a la moneda bruta (``expectancy_currency``),
que es el comportamiento histórico. El eje se declara en ``AllocationPlan.evidence_axis``
y viaja en ``as_dict()``: sin esa declaración, dos planes con los mismos multiplicadores
podrían venir de ejes distintos. Nunca se MEZCLAN ejes en el mismo reparto (los pesos
serían incomparables: R es adimensional y la moneda absoluta) y nunca se cambia QUIÉN
compite por un hueco de medición — con el R no medido, el reparto no cambia en nada.

Disciplina de medición (la del repo): todo lo que no se pudo medir se DECLARA, no se
rellena. Una estrategia sin muestra no es "mala", es desconocida; una pausa exige
evidencia, no ausencia de evidencia.

**Semántica explícita de "sin evidencia" (AUTO-8.1).** Que una estrategia no aparezca
en el mapa de asignación, o que su muestra no sea decisoria, NO significa riesgo cero:
significa que no hay evidencia para estrecharle el techo. El comportamiento se
materializa como una entrada del mapa con el multiplicador de la POLÍTICA
(``AdaptivePolicy.unknown_multiplier``, por defecto ``1.0`` neutral y configurable),
nunca como una consecuencia implícita de la ausencia de una clave.

**Hysteresis y cooldown (AUTO-8.1).** La pausa y la reactivación usan umbrales
DISTINTOS (zona muerta) y una pausa mínima en ciclos: una métrica que oscila alrededor
del umbral no debe producir un sistema nervioso (pausa/activa/pausa). El estado previo
entra como DATO (``paused_cycles``), nunca como estado interno del módulo.

**Read-only por contrato**: ``AdaptivePlan.read_only`` es ``True`` y su ``decisive`` de
origen NO es un permiso (lo decide el motor determinista).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from bolsa_analytics.cognitive.auto_self_evaluation import (
    StrategyRegimeEvaluation,
    StrategySelfEvaluation,
    declared_regime,
)
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
    is_complete,
)

__all__ = [
    "ADAPTIVE_ADVERSE_REGIMES",
    "ADAPTIVE_KEY",
    "ADAPTIVE_MIN_PAUSE_CYCLES_DEFAULT",
    "ADAPTIVE_POLICY_VERSION",
    "ADAPTIVE_PROFIT_FACTOR_PAUSE_DEFAULT",
    "ADAPTIVE_PROFIT_FACTOR_REACTIVATE_DEFAULT",
    "ADAPTIVE_REGIME_UNKNOWN",
    "ADAPTIVE_STRATEGY_COOLDOWN",
    "ADAPTIVE_STRATEGY_PAUSED",
    "ADAPTIVE_STRATEGY_REGIME_RISK",
    "ADAPTIVE_STRATEGY_UNHEALTHY",
    "ADAPTIVE_UNKNOWN_MULTIPLIER_DEFAULT",
    "ADAPTIVE_WIN_RATE_FLOOR_DEFAULT",
    "ADAPTIVE_WIN_RATE_REACTIVATE_DEFAULT",
    "ALLOCATION_AXIS_CURRENCY",
    "ALLOCATION_AXIS_NET_R",
    "AdaptivePlan",
    "AdaptivePolicy",
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

#: Versión de la POLÍTICA adaptativa (rotación + asignación). Es el sello que hace
#: reproducible una recomendación: dos planes con la misma evidencia, el mismo régimen y
#: la misma ``policy_version`` deben ser idénticos. Cambiar umbrales, la regla de
#: asignación o el suelo de régimen EXIGE subir esta versión (dentro de seis meses, dos
#: operaciones aparentemente iguales no pueden haber sido decididas por reglas distintas
#: sin que se note).
ADAPTIVE_POLICY_VERSION = "auto9-v1"

#: Motivos de rotación (vocabulario PROPIO de este módulo; el journal de la capa de
#: aplicación los lleva en el detalle de ``adaptive_strategy_paused``). La casa única
#: del literal de pausa en el journal es ``bolsa_application.auto_reason_codes``; aquí
#: se re-declara el motivo de pausa para que este módulo puro no dependa de application.
ADAPTIVE_STRATEGY_UNHEALTHY = "adaptive_strategy_unhealthy"
ADAPTIVE_STRATEGY_REGIME_RISK = "adaptive_strategy_regime_risk"
#: La pausa sigue vigente por la ventana mínima (cooldown) aunque el motivo de salud ya
#: no se dispare: evita el parpadeo pausa/activa/pausa de una métrica que oscila.
ADAPTIVE_STRATEGY_COOLDOWN = "adaptive_strategy_cooldown"
ADAPTIVE_STRATEGY_PAUSED = "adaptive_strategy_paused"

#: Regímenes de mercado (``MarketRegime`` del gobernador) adversos para la rotación:
#: una estrategia SIN muestra confiable no se activa a ciegas cuando el mercado baja
#: confirmado o está revuelto.
ADAPTIVE_ADVERSE_REGIMES: frozenset[str] = frozenset({"TREND_DOWN", "HIGH_VOL"})

#: Suelo de win rate (0..1) para la regla de régimen adverso. Por debajo, una estrategia
#: no decisoria se pausa en régimen adverso (nunca se pausa una muestra anecdótica buena).
ADAPTIVE_WIN_RATE_FLOOR_DEFAULT = 0.35
#: Suelo de REACTIVACIÓN (hysteresis): una estrategia ya pausada por régimen no vuelve a
#: competir hasta que su win rate recupera este nivel. El hueco entre ``0.35`` y ``0.45``
#: es la zona muerta: dentro de ella el veredicto anterior se mantiene.
ADAPTIVE_WIN_RATE_REACTIVATE_DEFAULT = 0.45
#: Profit factor de PAUSA (por debajo, salud probadamente negativa).
ADAPTIVE_PROFIT_FACTOR_PAUSE_DEFAULT = 1.0
#: Profit factor de REACTIVACIÓN (hysteresis): una pausa por salud no se levanta hasta
#: que el profit factor recupera este nivel. El hueco ``[1.0, 1.10)`` es la zona muerta.
ADAPTIVE_PROFIT_FACTOR_REACTIVATE_DEFAULT = 1.10
#: Pausa mínima (en ciclos de evaluación) antes de poder reactivar: el cooldown duro.
ADAPTIVE_MIN_PAUSE_CYCLES_DEFAULT = 3
#: Multiplicador de asignación para una estrategia SIN evidencia decisoria. Neutral por
#: defecto ("sin dato no penalizo"); es una POLÍTICA declarada, no un accidente.
ADAPTIVE_UNKNOWN_MULTIPLIER_DEFAULT = 1.0

#: Eje de evidencia del reparto: la MONEDA bruta (``expectancy_currency``). Es el
#: comportamiento histórico y el fallback DECLARADO cuando el R neto no está medido.
ALLOCATION_AXIS_CURRENCY = "expectancy_currency"
#: Eje de evidencia del reparto: el **R neto medido** (``net_expectancy_r``). Se adopta
#: SOLO si todo el grupo que compite lo tiene medido (``AUTO-9``, §5.4): así el cambio de
#: eje puede mover los pesos relativos, nunca la composición del numerador.
ALLOCATION_AXIS_NET_R = "net_expectancy_r"

#: Régimen por estrategia: el cruce ``strategy × regime`` ya tiene productor (``AUTO-9``),
#: así que ``StrategyHealth.regime`` se puebla con el régimen **determinado** de la
#: estrategia (una única celda decisiva con régimen). Si opera en dos regímenes —o solo en
#: el cubo ``UNKNOWN``— NO se elige uno: queda ``UNKNOWN`` y la política lo IGNORA, como
#: hoy. El detalle por régimen vive en ``by_regime``.
ADAPTIVE_REGIME_UNKNOWN = "UNKNOWN"


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
class AdaptivePolicy:
    """Política adaptativa versionada: umbrales de rotación, hysteresis y asignación.

    Se declara explícitamente para que la versión viaje con la recomendación: sin ella,
    dos planes iguales podrían venir de reglas distintas y la reproducibilidad se pierde.
    """

    policy_version: str = ADAPTIVE_POLICY_VERSION
    # Asignación: multiplicador de una estrategia sin evidencia decisoria (neutral 1.0).
    unknown_multiplier: float = ADAPTIVE_UNKNOWN_MULTIPLIER_DEFAULT
    # Rotación por régimen adverso: suelo de PAUSA y suelo de REACTIVACIÓN (hysteresis).
    win_rate_floor: float = ADAPTIVE_WIN_RATE_FLOOR_DEFAULT
    win_rate_reactivate_floor: float = ADAPTIVE_WIN_RATE_REACTIVATE_DEFAULT
    # Rotación por salud: umbral de PAUSA y de REACTIVACIÓN (hysteresis).
    profit_factor_pause: float = ADAPTIVE_PROFIT_FACTOR_PAUSE_DEFAULT
    profit_factor_reactivate: float = ADAPTIVE_PROFIT_FACTOR_REACTIVATE_DEFAULT
    # Cooldown: ciclos mínimos que una pausa permanece antes de poder reactivarse.
    min_pause_cycles: int = ADAPTIVE_MIN_PAUSE_CYCLES_DEFAULT


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
    # R bruto realizado (adimensional), agregado de la estrategia. ``None`` cuando ningún
    # ciclo trae riesgo comprometido: se declara, no se rellena con 0.
    expectancy_r: float | None = None
    # R NETO (descontado el coste **estimado** ida y vuelta) agregado de la estrategia, con
    # su estado de medición. El neto depende de un coste estimado (§6.3): quien decida con
    # él exige ``net_r_measurement == COMPLETE`` — con ``PARTIAL`` el número es la media de
    # los ciclos que SÍ tenían coste, y ``cycle_without_cost`` dice cuántos faltan.
    net_expectancy_r: float | None = None
    net_r_measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
    # Régimen DETERMINADO de la estrategia (``strategy × regime``): solo se puebla si hay
    # exactamente una celda decisiva con régimen. Con dos regímenes decisivos —o con solo
    # el cubo ``UNKNOWN``— queda ``UNKNOWN``: nunca uno elegido a dedo.
    regime: str = ADAPTIVE_REGIME_UNKNOWN

    @classmethod
    def from_evaluation(
        cls,
        row: StrategySelfEvaluation,
        *,
        regime_cells: Sequence[StrategyRegimeEvaluation] = (),
    ) -> StrategyHealth:
        """Proyecta la fila de self-evaluation y, si se aportan, sus celdas por régimen.

        El régimen sale del cruce ``strategy × regime`` del mismo informe: la fila sola no
        lo sabe. Sin celdas (o con el régimen no determinado) queda ``UNKNOWN``.
        """
        regime, _undetermined = declared_regime(regime_cells, row.strategy_version)
        return cls(
            strategy_version=row.strategy_version,
            trades=row.trades,
            decisive=row.decisive,
            expectancy_currency=row.expectancy_currency,
            profit_factor=row.profit_factor,
            win_rate=row.win_rate,
            expectancy_r=row.expectancy_r,
            net_expectancy_r=row.net_expectancy_r,
            net_r_measurement=row.net_r_measurement,
            regime=regime or ADAPTIVE_REGIME_UNKNOWN,
        )


def build_strategy_health(
    by_strategy: Sequence[StrategySelfEvaluation],
    *,
    by_regime: Sequence[StrategyRegimeEvaluation] = (),
) -> tuple[StrategyHealth, ...]:
    """Proyección read-only de las filas de self-evaluation al contrato de Adaptive.

    ``by_regime`` son las celdas del cruce ``strategy × regime`` del MISMO informe: son la
    única fuente del régimen determinado (la fila de estrategia no lo lleva).
    """
    cells = tuple(by_regime)
    return tuple(StrategyHealth.from_evaluation(row, regime_cells=cells) for row in by_strategy)


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
        return frozenset(d.strategy_version for d in self.decisions if not d.active)

    def reason_for(self, strategy_version: str) -> str | None:
        for d in self.decisions:
            if d.strategy_version == strategy_version and not d.active:
                return d.reason
        return None

    def is_paused(self, strategy_version: str) -> bool:
        return str(strategy_version or "") in self.paused

    def as_dict(self) -> dict[str, Any]:
        # Orden canónico por versión: la reproducibilidad de la recomendación no puede
        # depender del orden de entrada de las filas.
        return {
            "paused": sorted(self.paused),
            "byStrategy": [
                {
                    "strategyVersion": d.strategy_version,
                    "active": d.active,
                    "reason": d.reason,
                }
                for d in sorted(self.decisions, key=lambda d: d.strategy_version)
            ],
        }


@dataclass(frozen=True, slots=True)
class AllocationPlan:
    """Multiplicadores de riesgo por estrategia (solo estrechan: cada valor en ``[0, 1]``).

    Una versión ausente del mapa equivale a ``1.0`` (sin estrechamiento): la ausencia no
    es una pausa, es "no hubo nada que estrechar". ``recommend_allocation`` materializa
    una entrada por CADA versión activa (con el multiplicador de la política cuando no
    hay evidencia), de modo que la semántica no dependa de este default.

    ``evidence_axis`` declara con QUÉ se pesó el reparto (``expectancy_currency`` o
    ``net_expectancy_r``): es parte de la recomendación, no un detalle interno. El default
    es el eje histórico, así que una construcción directa del plan (``AUTO-8``) sigue
    significando exactamente lo que significaba.
    """

    multipliers: dict[str, float]
    evidence_axis: str = ALLOCATION_AXIS_CURRENCY

    def multiplier_for(self, strategy_version: str) -> float:
        return self.multipliers.get(str(strategy_version or ""), 1.0)

    def as_dict(self) -> dict[str, Any]:
        return {
            "riskMultipliers": dict(sorted(self.multipliers.items())),
            "evidenceAxis": self.evidence_axis,
        }


@dataclass(frozen=True, slots=True)
class AdaptivePlan:
    """Recomendación Adaptive completa del tick (rotación + asignación + régimen)."""

    rotation: RotationPlan
    allocation: AllocationPlan
    regime: str | None = None
    read_only: bool = True
    #: Versión de la política que produjo este plan (reproducibilidad).
    policy_version: str = ADAPTIVE_POLICY_VERSION
    #: Salud por estrategia que sustentó la recomendación (evidencia del journal).
    health: tuple[StrategyHealth, ...] = ()

    def is_paused(self, strategy_version: str) -> bool:
        return self.rotation.is_paused(strategy_version)

    def risk_multiplier_for(self, strategy_version: str) -> float:
        return self.allocation.multiplier_for(strategy_version)

    def health_for(self, strategy_version: str) -> StrategyHealth | None:
        key = str(strategy_version or "")
        for row in self.health:
            if row.strategy_version == key:
                return row
        return None

    def evidence_for(self, strategy_version: str) -> dict[str, Any] | None:
        """Evidencia que sustentó la recomendación para UNA estrategia (o ``None``).

        Sin fila para esa versión se devuelve ``None``: la ausencia de evidencia es un
        hecho que el journal declara, nunca un cero disfrazado de medida.
        """
        row = self.health_for(strategy_version)
        if row is None:
            return None
        return {
            "decisive": row.decisive,
            "trades": row.trades,
            "expectancyCurrency": (
                None if row.expectancy_currency is None else str(row.expectancy_currency)
            ),
            "expectancyR": row.expectancy_r,
            "netExpectancyR": row.net_expectancy_r,
            "netRMeasurement": row.net_r_measurement,
            "profitFactor": row.profit_factor,
            "winRate": row.win_rate,
            "regime": row.regime,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": ADAPTIVE_KEY,
            "readOnly": self.read_only,
            "policyVersion": self.policy_version,
            "regime": self.regime,
            "rotation": self.rotation.as_dict(),
            "allocation": self.allocation.as_dict(),
        }


def _pause_reason(health: StrategyHealth, adverse: bool, policy: AdaptivePolicy) -> str | None:
    """Motivo de pausa con los umbrales de PAUSA (``None`` si no procede pausar)."""
    if health.decisive:
        expectancy_bad = (
            health.expectancy_currency is not None and health.expectancy_currency <= Decimal("0")
        )
        pf_bad = (
            health.profit_factor is not None and health.profit_factor < policy.profit_factor_pause
        )
        if expectancy_bad or pf_bad:
            return ADAPTIVE_STRATEGY_UNHEALTHY
    if adverse and not health.decisive:
        if health.win_rate is not None and health.win_rate < policy.win_rate_floor:
            return ADAPTIVE_STRATEGY_REGIME_RISK
    return None


def _still_unhealthy(health: StrategyHealth, policy: AdaptivePolicy) -> bool:
    """Para una pausa de SALUD ya vigente: True si NO se cumplen los umbrales de reactivación.

    Sin muestra decisoria se devuelve ``False``: una pausa de SALUD exige muestra decisoria
    para motivarse, así que sin ella no puede afirmarse que sigue vigente (el desconocido no
    es un defecto). La pausa de régimen adverso es la que cubre la muestra fina. Con muestra
    decisoria, la expectancy debe ser positiva y el profit factor debe recuperar el umbral
    de reactivación (hysteresis: el hueco hasta ``profit_factor_reactivate`` es zona muerta).
    """
    if not health.decisive:
        return False
    expectancy_ok = health.expectancy_currency is not None and health.expectancy_currency > Decimal(
        "0"
    )
    pf_ok = health.profit_factor is None or health.profit_factor >= policy.profit_factor_reactivate
    return not (expectancy_ok and pf_ok)


def _still_regime_risk(health: StrategyHealth, adverse: bool, policy: AdaptivePolicy) -> bool:
    """Para una pausa de RÉGIMEN ya vigente: True si sigue en zona muerta/riesgo."""
    if not adverse:
        return False
    if health.decisive:
        return False
    return health.win_rate is not None and health.win_rate < policy.win_rate_reactivate_floor


def recommend_rotation(
    by_strategy: Sequence[StrategySelfEvaluation],
    regime: str | None,
    *,
    policy: AdaptivePolicy | None = None,
    paused_cycles: Mapping[str, int] | None = None,
    by_regime: Sequence[StrategyRegimeEvaluation] = (),
) -> RotationPlan:
    """(PURA) decide qué versiones pausar, con reglas deterministas y declarativas.

    Orden de evaluación (la primera que aplica gana el motivo):

    1. ``adaptive_strategy_unhealthy`` — salud **probadamente** negativa: muestra
       decisoria y (expectancy <= 0 o profit factor < 1).
    2. ``adaptive_strategy_regime_risk`` — régimen adverso (``TREND_DOWN``/``HIGH_VOL``)
       y muestra NO decisoria y win rate por debajo del suelo: no se activa a ciegas en
       un mercado que castiga.
    3. ``adaptive_strategy_cooldown`` — la estrategia ya estaba pausada y aún no ha
       cumplido la pausa mínima (``min_pause_cycles``): la pausa se mantiene aunque los
       umbrales de pausa ya no se disparen.

    El resto queda ACTIVE. Sin dato ⇒ no se rota (el desconocido no es un defecto).

    ``paused_cycles`` es el DATO de estado que habilita hysteresis y cooldown: cuántos
    ciclos consecutivos lleva pausada cada versión (``0``/ausente = no estaba pausada).
    Sin él, el módulo aplica solo los umbrales de pausa (comportamiento histórico) y
    sigue siendo puro: no guarda estado entre llamadas.
    """
    resolved = policy or AdaptivePolicy()
    counts = paused_cycles or {}
    cells = tuple(by_regime)
    adverse = str(regime or "").strip().upper() in ADAPTIVE_ADVERSE_REGIMES
    decisions: list[RotationDecision] = []
    for row in by_strategy:
        health = StrategyHealth.from_evaluation(row, regime_cells=cells)
        version = health.strategy_version
        count = int(counts.get(version, 0) or 0)
        reason = _pause_reason(health, adverse, resolved)
        if count <= 0:
            # No estaba pausada: mandan los umbrales de pausa.
            decisions.append(
                RotationDecision(strategy_version=version, active=reason is None, reason=reason)
            )
            continue
        # Ya pausada: hysteresis (umbrales de reactivación) + cooldown mínimo.
        if count < max(0, int(resolved.min_pause_cycles)):
            reason = reason or ADAPTIVE_STRATEGY_COOLDOWN
        elif reason is None:
            if _still_unhealthy(health, resolved):
                reason = ADAPTIVE_STRATEGY_UNHEALTHY
            elif _still_regime_risk(health, adverse, resolved):
                reason = ADAPTIVE_STRATEGY_REGIME_RISK
        decisions.append(
            RotationDecision(strategy_version=version, active=reason is None, reason=reason)
        )
    return RotationPlan(tuple(decisions))


def _allocation_weights(
    rows_by_version: Mapping[str, StrategySelfEvaluation],
    active_versions: Sequence[str],
) -> tuple[str, dict[str, float]]:
    """(PURA) eje de evidencia del reparto y los pesos que compiten en él.

    Los dos ejes NO son comparables entre sí: ``expectancy_currency`` es absoluta
    (moneda) y ``net_expectancy_r`` es adimensional (múltiplos de R), así que un reparto
    que mezclase pesos de ambos sería aritmética sin sentido. Por eso el eje se elige
    para el GRUPO —nunca por fila— y el R neto solo se adopta cuando los dos ejes
    coinciden en QUIÉN compite: así el cambio de eje puede mover los pesos relativos pero
    jamás la composición del numerador, y una estrategia con R no medido no queda fuera
    del reparto por un hueco de medición (el desconocido no es un defecto).

    El gate de decisividad es POR FILA en los dos ejes: una expectativa no validada por
    su muestra no entra al numerador, aunque otra estrategia del grupo sí sea decisoria.
    El R neto exige además ``net_r_measurement == COMPLETE`` (§6.3: el coste es
    **estimado**, así que un ``PARTIAL`` no habilita decidir contra el agregado).
    """
    currency: dict[str, float] = {}
    net_r: dict[str, float] = {}
    for version in active_versions:
        row = rows_by_version.get(version)
        if row is None or not row.decisive:
            continue
        if row.expectancy_currency is not None and row.expectancy_currency > 0:
            currency[version] = float(row.expectancy_currency)
        if (
            is_complete(row.net_r_measurement)
            and row.net_expectancy_r is not None
            and row.net_expectancy_r > 0
        ):
            net_r[version] = float(row.net_expectancy_r)
    if net_r and net_r.keys() == currency.keys():
        return ALLOCATION_AXIS_NET_R, net_r
    return ALLOCATION_AXIS_CURRENCY, currency


def recommend_allocation(
    active: Iterable[str],
    by_strategy: Sequence[StrategySelfEvaluation],
    *,
    policy: AdaptivePolicy | None = None,
) -> AllocationPlan:
    """(PURA) multiplicador de riesgo por estrategia activa (solo estrecha, ``[0, 1]``).

    ``active`` son las versiones NO pausadas (la rotación ya decidió quién compite).
    Reparto:

    * Solo entran al reparto proporcional las estrategias **decisorias** con expectancy
      positiva: una muestra fina, por favorable que sea su racha, NO mueve el reparto
      (su número no está validado).
    * Si hay al menos una decisoria positiva, el presupuesto se reparte entre ELLAS
      proporcional a su expectancy (``share * m``, con ``m`` su número); el resto de
      activas recibe el multiplicador de la política para "sin evidencia decisoria"
      (``unknown_multiplier``, neutral ``1.0`` por defecto).
    * Sin ninguna decisoria positiva, TODAS reciben ese mismo multiplicador neutral.
    * El **eje** de esos pesos es el R neto MEDIDO cuando está medido para todo el grupo
      que compite; si no, la moneda bruta, que es el comportamiento histórico. El eje se
      declara en ``AllocationPlan.evidence_axis`` y nunca se mezclan los dos.

    Se materializa una entrada por CADA versión activa: la semántica de "sin evidencia"
    queda en la política, nunca en el default de ``AllocationPlan.multiplier_for``.
    """
    resolved = policy or AdaptivePolicy()
    active_versions: list[str] = []
    seen: set[str] = set()
    for raw in active:
        version = str(raw or "")
        if version and version not in seen:
            seen.add(version)
            active_versions.append(version)
    if not active_versions:
        return AllocationPlan({})

    rows_by_version = {row.strategy_version: row for row in by_strategy}
    axis, positive = _allocation_weights(rows_by_version, active_versions)

    neutral = _clamp_unit(resolved.unknown_multiplier)
    multipliers: dict[str, float] = {}
    if positive:
        count = len(positive)
        total = sum(positive.values())
        for version in active_versions:
            weight = positive.get(version)
            if weight is None:
                multipliers[version] = neutral
            else:
                multipliers[version] = _clamp_unit((weight / total) * count)
    else:
        for version in active_versions:
            multipliers[version] = neutral
    return AllocationPlan(multipliers, evidence_axis=axis)


def build_adaptive_plan(
    by_strategy: Sequence[StrategySelfEvaluation],
    regime: str | None,
    *,
    policy: AdaptivePolicy | None = None,
    paused_cycles: Mapping[str, int] | None = None,
    by_regime: Sequence[StrategyRegimeEvaluation] = (),
) -> AdaptivePlan:
    """(PURA) plan Adaptive completo: rotación + asignación sobre las mismas filas.

    ``regime`` es el ``MarketRegime`` del gobernador (``TREND_UP``/``TREND_DOWN``/
    ``RANGE``/``HIGH_VOL``/``LOW_VOL``/``UNKNOWN``), no el eje operativo.
    """
    resolved = policy or AdaptivePolicy()
    cells = tuple(by_regime)
    rotation = recommend_rotation(
        by_strategy,
        regime,
        policy=resolved,
        paused_cycles=paused_cycles,
        by_regime=cells,
    )
    active_versions = [
        row.strategy_version for row in by_strategy if not rotation.is_paused(row.strategy_version)
    ]
    allocation = recommend_allocation(active_versions, by_strategy, policy=resolved)
    return AdaptivePlan(
        rotation=rotation,
        allocation=allocation,
        regime=regime,
        policy_version=resolved.policy_version,
        health=build_strategy_health(by_strategy, by_regime=cells),
    )
