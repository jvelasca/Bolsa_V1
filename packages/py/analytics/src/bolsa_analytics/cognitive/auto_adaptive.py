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

**Reparto por CELDA de régimen (AUTO-14, §20).** Cuando el grupo compite en el eje del R **neto
medido**, el peso de cada versión admitida sale de su **celda** ``strategy × regime`` del régimen del
tick en vez de su fila agregada (que mezcla regímenes que no se parecen). La celda **afina el peso,
nunca la composición**: quién entra al numerador lo sigue decidiendo la FILA, así que la fase no puede
añadir ni quitar competidores. Sin muestra suficiente (celda no ``decisive``), sin el neto medido, sin
celda para ese régimen o con el régimen ilegible, esa versión conserva su número **global** y el hueco
se **declara** (``cell_fallback`` + ``cell_axis``). Con el eje de **moneda** el reparto queda global y
lo declara: la celda mide R, no moneda, y no se deriva un cociente paralelo para fabricarla. El
encogimiento por confianza de ``AUTO-12`` usa la banda de la **celda** cuando el peso salió de ella.

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

**Confianza estadística (AUTO-12).** El reparto deja de pesar igual una muestra de ``N = 12``
y una de ``N = 180``: cuando el llamante aporta la lectura de confianza
(``auto_adaptive_confidence``), el peso de cada estrategia **decisoria positiva** se encoge
por su muestra efectiva (``n / (n + confidence_prior)``) y, si el deterioro reciente es
``SEVERE``, por un factor adicional declarado. El encogimiento solo **redistribuye** dentro
del presupuesto: sigue acotado a ``[0, 1]``, nunca elimina a nadie del reparto y **no**
actúa sobre las estrategias sin edge decisorio (el desconocido no es un defecto). Sin
``confidence`` el comportamiento es **byte-idéntico** al histórico: la confianza es un
**eje de evidencia opcional**, nunca un requisito para recomendar.

**Read-only por contrato**: ``AdaptivePlan.read_only`` es ``True`` y su ``decisive`` de
origen NO es un permiso (lo decide el motor determinista).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_DECAY_SEVERE,
    AdaptiveConfidence,
    RegimeConfidence,
    StrategyConfidence,
)
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
    "ADAPTIVE_CONFIDENCE_PRIOR_DEFAULT",
    "ADAPTIVE_KEY",
    "ADAPTIVE_MIN_PAUSE_CYCLES_DEFAULT",
    "ADAPTIVE_POLICY_VERSION",
    "ADAPTIVE_PROFIT_FACTOR_PAUSE_DEFAULT",
    "ADAPTIVE_PROFIT_FACTOR_REACTIVATE_DEFAULT",
    "ADAPTIVE_RECOVERY_NOTE_NOT_POSITIVE",
    "ADAPTIVE_RECOVERY_NOTE_SEVERE",
    "ADAPTIVE_RECOVERY_NOTE_UNMEASURED",
    "ADAPTIVE_RECOVERY_STEPS_DEFAULT",
    "ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT",
    "ADAPTIVE_REGIME_UNKNOWN",
    "ADAPTIVE_SEVERE_DECAY_FACTOR_DEFAULT",
    "ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL",
    "ADAPTIVE_CELL_NOTE_NET_UNMEASURED",
    "ADAPTIVE_CELL_NOTE_NOT_DECISIVE",
    "ADAPTIVE_CELL_NOTE_NOT_FOUND",
    "ADAPTIVE_CELL_NOTE_NOT_POSITIVE",
    "ADAPTIVE_CELL_NOTE_REGIME_ABSENT",
    "ADAPTIVE_STATE_ACTIVE",
    "ADAPTIVE_STATE_PAUSED",
    "ADAPTIVE_STATE_RECOVERING",
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
    "RecoveryEvidence",
    "RecoveryReading",
    "RotationDecision",
    "RotationPlan",
    "StrategyHealth",
    "build_adaptive_plan",
    "build_strategy_health",
    "recommend_allocation",
    "recommend_rotation",
    "recovery_reading",
    "regime_cell_for",
]

ADAPTIVE_KEY = "adaptive"

#: Versión de la POLÍTICA adaptativa (rotación + asignación). Es el sello que hace
#: reproducible una recomendación: dos planes con la misma evidencia, el mismo régimen y
#: la misma ``policy_version`` deben ser idénticos. Cambiar umbrales, la regla de
#: asignación o el suelo de régimen EXIGE subir esta versión (dentro de seis meses, dos
#: operaciones aparentemente iguales no pueden haber sido decididas por reglas distintas
#: sin que se note).
#:
#: ``auto12-v1`` (AUTO-12): la regla de asignación cambia al encogerse por muestra efectiva
#: cuando el llamante aporta la confianza estadística.
#:
#: ``auto13-v1`` (AUTO-13): la regla de asignación cambia otra vez — el multiplicador pasa por el
#: **techo de la rampa de reincorporación** (``m_final = min(m_reparto, escalón)``) cuando una
#: versión vuelve de una pausa, de modo que dos planes iguales con la misma evidencia NO son
#: idénticos si uno viene de una pausa cumplida y el otro no.
#:
#: ``auto14-v1`` (AUTO-14): el reparto deja de pesar solo con la evidencia **global** de la
#: estrategia cuando el grupo compite en el eje del R **neto medido**: cada versión admitida pesa con
#: el R neto de su **celda** ``strategy × regime`` para el régimen del tick, y cae al global —con el
#: motivo declarado— cuando esa celda no está medida. La composición del numerador NO cambia (la
#: decide la fila, como en ``v2.50``–``v2.54``), pero los pesos relativos sí: dos planes iguales con
#: la misma evidencia y el mismo régimen no son idénticos si uno se midió por celda y el otro no.
#:
#: ``auto16-v1`` (AUTO-16): la REGLA no cambia —sigue siendo la de ``AUTO-14``, y ninguna condición
#: de ``_allocation_weights`` se toca—, pero cambia la **procedencia de un input** del eje del R
#: neto: el coste que descuenta ese neto deja de ser siempre el **supuesto** por el decisor y pasa a
#: ser, cuando está medido, el que el **simulador aplicó** (``costApplied``, sello por ciclo en
#: ``costBasis``). Dos planes con la misma evidencia pueden entonces diferir en los pesos porque el
#: neto se midió contra otro modelo de coste; sin subir el sello, esa diferencia sería invisible.
ADAPTIVE_POLICY_VERSION = "auto16-v1"

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

#: Prior del encogimiento por muestra (AUTO-12): ``shrink = n / (n + prior)``. Con un prior
#: de 20, una muestra efectiva de 20 conserva la mitad del peso, 180 conserva el 90 % y una
#: racha de 12 conserva el 37,5 % frente a la misma expectancy con historia larga. Es la
#: protección contra el *winner chasing*: un edge medido pero fino NO pesa como uno medido
#: con base amplia.
ADAPTIVE_CONFIDENCE_PRIOR_DEFAULT = 20.0
#: Factor adicional de reparto cuando la ventana reciente se deterioró (``decay == SEVERE``).
#: Es una modulación DECLARADA, no una pausa: la pausa sigue siendo de la rotación.
ADAPTIVE_SEVERE_DECAY_FACTOR_DEFAULT = 0.5

#: Eje de evidencia del reparto: la MONEDA bruta (``expectancy_currency``). Es el
#: comportamiento histórico y el fallback DECLARADO cuando el R neto no está medido.
ALLOCATION_AXIS_CURRENCY = "expectancy_currency"
#: Eje de evidencia del reparto: el **R neto medido** (``net_expectancy_r``). Se adopta
#: SOLO si todo el grupo que compite lo tiene medido (``AUTO-9``, §5.4): así el cambio de
#: eje puede mover los pesos relativos, nunca la composición del numerador.
ALLOCATION_AXIS_NET_R = "net_expectancy_r"

# ── AUTO-14 — el reparto por CELDA de régimen (§20) ──────────────────────────────────
#
# El cruce ``strategy × regime`` de ``AUTO-9`` ya está MEDIDO y ya llega al plan (rotación y salud),
# pero el reparto pesaba solo con la evidencia **global** de la fila. ``AUTO-14`` deja que la celda
# afine el PESO de una versión que ya competía.
#
# Dos reglas duras que hacen la fase honesta:
#
# * **La celda afina el peso, nunca la composición.** Quién entra al numerador lo decide la FILA
#   (``decisive`` + expectancy positiva), igual que en ``v2.50``–``v2.54``: la celda solo puede cambiar
#   el NÚMERO con el que compite una versión ya admitida. Ni añade ni quita competidores.
# * **El hueco se declara.** Sin muestra, sin medición del eje o sin régimen legible, esa versión
#   conserva su número **global** y el motivo viaja en el plan.

#: Motivos DECLARADOS de por qué el reparto de una versión **no** usó su celda de régimen y cayó a la
#: evidencia **global** de su fila. Nunca se elige otra celda, ni la de otra versión, ni la de otro
#: ciclo. Vocabulario propio del eje del reparto (no se mezcla con los motivos de rotación ni con los
#: del gate de datos).
#: El régimen del tick no se pudo leer (``None``, cadena vacía o ``UNKNOWN``): sin régimen no hay juicio.
ADAPTIVE_CELL_NOTE_REGIME_ABSENT = "cell_regime_absent"
#: No existe celda para el par ``(versión, régimen)``: el cruce no la midió (o no se aportaron celdas).
ADAPTIVE_CELL_NOTE_NOT_FOUND = "cell_not_found"
#: La celda existe pero no es ``decisive``: su muestra no alcanza ``min_trades`` o no tiene el R medido
#: en todos sus ciclos. Una muestra fina NO mueve el reparto.
ADAPTIVE_CELL_NOTE_NOT_DECISIVE = "cell_not_decisive"
#: La celda tiene muestra, pero su R **neto** no está ``COMPLETE``: falta el coste de alguno de sus
#: ciclos, así que un ``PARTIAL`` no habilita decidir con ella (§6.3 de ``AUTO-9``). AUTO-16 no
#: cambia la condición —sigue siendo ``net_r_measurement == COMPLETE``—, solo de qué coste sale el
#: número cuando sí lo está (``netRBasis``).
ADAPTIVE_CELL_NOTE_NET_UNMEASURED = "cell_net_unmeasured"
#: La celda está medida pero su R neto **no es positivo**: solo una celda medida y positiva afina.
ADAPTIVE_CELL_NOTE_NOT_POSITIVE = "cell_not_positive"
#: El eje del grupo es la MONEDA bruta: la celda mide R, no moneda, así que no puede afinar el peso y
#: el reparto se queda en la evidencia global (no se deriva un cociente paralelo para fabricarla).
ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL = "cell_axis_without_cell"

#: Régimen por estrategia: el cruce ``strategy × regime`` ya tiene productor (``AUTO-9``),
#: así que ``StrategyHealth.regime`` se puebla con el régimen **determinado** de la
#: estrategia (una única celda decisiva con régimen). Si opera en dos regímenes —o solo en
#: el cubo ``UNKNOWN``— NO se elige uno: queda ``UNKNOWN`` y la política lo IGNORA, como
#: hoy. El detalle por régimen vive en ``by_regime``.
ADAPTIVE_REGIME_UNKNOWN = "UNKNOWN"

#: Estados operativos por estrategia (§23/§29). Eje PROPIO: no es el estado de los DATOS
#: (``auto_adaptive_data_gate``) ni la calidad estadística (``auto_adaptive_confidence``), y los
#: tres no comparten campo. El estado se **deriva** de la rotación + la rampa; no es un modo nuevo
#: de la rotación — quien pausa y reactiva sigue siendo ``recommend_rotation``.
ADAPTIVE_STATE_ACTIVE = "active"
ADAPTIVE_STATE_PAUSED = "paused"
#: Dejó de estar pausada y vuelve **por la rampa**: no recupera el peso pleno de golpe (§24).
ADAPTIVE_STATE_RECOVERING = "recovering"

#: Escalones DECLARADOS de la rampa de reincorporación (§24: ``0.25 → 0.50 → 0.75 → 1.00``). El
#: primero es el SUELO: la rampa nunca deja a nadie en ``0`` (no es una pausa encubierta) y, como
#: es un TECHO del reparto, nunca ensancha.
ADAPTIVE_RECOVERY_STEPS_DEFAULT: tuple[float, ...] = (0.25, 0.50, 0.75, 1.00)
#: Ciclos de evaluación CON EVIDENCIA MEDIDA POSITIVA que hacen subir un escalón. La rampa sube
#: por **evidencia, nunca por reloj**: sin un ciclo positivo que lo confirme, no sube.
ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT = 3

#: Motivos DECLARADOS del hueco de la rampa (viajan en la lectura, no solo en el log).
ADAPTIVE_RECOVERY_NOTE_NOT_POSITIVE = "recovery_not_positive"
ADAPTIVE_RECOVERY_NOTE_SEVERE = "recovery_severe_decay"
ADAPTIVE_RECOVERY_NOTE_UNMEASURED = "recovery_unmeasured"


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
    # AUTO-12: encogimiento por muestra efectiva (protección contra el *winner chasing*) y
    # factor adicional cuando el deterioro reciente es ``SEVERE``. Declarados para que la
    # versión de política selle la regla de asignación completa.
    confidence_prior: float = ADAPTIVE_CONFIDENCE_PRIOR_DEFAULT
    severe_decay_factor: float = ADAPTIVE_SEVERE_DECAY_FACTOR_DEFAULT
    # AUTO-13: escalones de la RAMPA de reincorporación (§24) y ciclos de evidencia medida
    # positiva que hacen subir un escalón. Declarados para que la versión selle también la regla
    # de reincorporación: dos planes iguales no pueden venir de rampas distintas sin que se note.
    recovery_steps: tuple[float, ...] = ADAPTIVE_RECOVERY_STEPS_DEFAULT
    recovery_step_cycles: int = ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT

    def __post_init__(self) -> None:
        """Valida la rampa: escalones en ``(0, 1]``, estrictamente crecientes y paso ``>= 1``.

        Un escalón fuera de ``(0, 1]`` rompería el invariante del reparto (solo estrecha, y nunca
        a ``0``); uno no creciente haría que la rampa no subiera o bajara sola; un paso ``< 1``
        afirmaría una subida por ciclo que la regla no declara.
        """
        previous = 0.0
        steps = tuple(float(step) for step in self.recovery_steps)
        if not steps:
            raise ValueError("recovery_steps must not be empty")
        for step in steps:
            if not 0.0 < step <= 1.0:
                raise ValueError("recovery_steps must be within (0, 1]")
            if step <= previous:
                raise ValueError("recovery_steps must be strictly increasing")
            previous = step
        if int(self.recovery_step_cycles) < 1:
            raise ValueError("recovery_step_cycles must be >= 1")


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
    # AUTO-13 (§20) — el MOTIVO por el que ``regime`` no se pudo determinar (``regime_undetermined``)
    # viaja CON la fila, no se pierde en el cruce: el par ``(regime, motivo)`` que publica
    # ``declared_regime`` se conserva entero. Sin él, un ``UNKNOWN`` legítimo (el cruce no tiene una
    # celda decisiva) sería indistinguible de un régimen mal medido. La rotación NO usa el cruce
    # cuando no está determinado: decide con la evidencia **global** de la estrategia (esta fila), y
    # eso es exactamente lo que este campo permite declarar.
    regime_undetermined: bool = False
    # AUTO-12 — confianza estadística de la evidencia (``auto_adaptive_confidence``). ``None``
    # cuando el llamante no aportó la lectura: la AUSENCIA se declara, nunca se disfraza de
    # confianza alta. La banda es evidencia publicada; el encogimiento del reparto vive en
    # ``recommend_allocation`` y sale de ``effective_n``/``decay``.
    confidence: str | None = None
    recent_expectancy_r: float | None = None
    long_expectancy_r: float | None = None
    decay: str | None = None

    @classmethod
    def from_evaluation(
        cls,
        row: StrategySelfEvaluation,
        *,
        regime_cells: Sequence[StrategyRegimeEvaluation] = (),
        confidence: StrategyConfidence | None = None,
    ) -> StrategyHealth:
        """Proyecta la fila de self-evaluation y, si se aportan, sus celdas y su confianza.

        El régimen sale del cruce ``strategy × regime`` del mismo informe: la fila sola no
        lo sabe. Sin celdas (o con el régimen no determinado) queda ``UNKNOWN``. La confianza
        (AUTO-12) se adjunta por ``strategyVersion``; sin ella los campos quedan ``None``.
        """
        regime, undetermined = declared_regime(regime_cells, row.strategy_version)
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
            # AUTO-13 (§20): el motivo del hueco se conserva junto al régimen (el par completo).
            regime_undetermined=undetermined is not None,
            confidence=confidence.confidence if confidence is not None else None,
            recent_expectancy_r=(
                confidence.recent_expectancy_r if confidence is not None else None
            ),
            long_expectancy_r=(
                confidence.long_expectancy_r if confidence is not None else None
            ),
            decay=confidence.decay if confidence is not None else None,
        )


def build_strategy_health(
    by_strategy: Sequence[StrategySelfEvaluation],
    *,
    by_regime: Sequence[StrategyRegimeEvaluation] = (),
    confidence: AdaptiveConfidence | None = None,
) -> tuple[StrategyHealth, ...]:
    """Proyección read-only de las filas de self-evaluation al contrato de Adaptive.

    ``by_regime`` son las celdas del cruce ``strategy × regime`` del MISMO informe: son la
    única fuente del régimen determinado (la fila de estrategia no lo lleva). ``confidence``
    (AUTO-12) adjunta la confianza estadística por versión; sin ella el plan es idéntico al
    histórico.
    """
    cells = tuple(by_regime)
    return tuple(
        StrategyHealth.from_evaluation(
            row,
            regime_cells=cells,
            confidence=(
                confidence.confidence_for(row.strategy_version)
                if confidence is not None
                else None
            ),
        )
        for row in by_strategy
    )


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

    **AUTO-14 — la base de celda, declarada aparte del eje.** ``cell_axis`` es el eje en el que las
    celdas ``strategy × regime`` afinaron el peso (``net_expectancy_r``), o ``None`` si no se
    aplicaron (eje de moneda, o sin celdas). ``cell_used`` dice, por versión, el **régimen de la celda
    que aportó su peso**; ``cell_fallback`` dice, por versión, el **motivo** por el que su peso salió
    del global (vocabulario ``ADAPTIVE_CELL_NOTE_*``). Son ejes propios: no se mezclan con el eje de
    evidencia —el eje sigue siendo el mismo y conserva sus dos literales— ni con la calidad medida.
    """

    multipliers: dict[str, float]
    evidence_axis: str = ALLOCATION_AXIS_CURRENCY
    #: AUTO-14 — el eje en el que las celdas afinaron el reparto, o ``None`` (no se aplicaron).
    cell_axis: str | None = None
    #: AUTO-14 — versión → régimen de la celda que aportó su peso (solo las que compiten por celda).
    cell_used: Mapping[str, str] = field(default_factory=dict)
    #: AUTO-14 — versión → motivo del hueco (su peso salió del global). Nunca vacío "por accidente":
    #: si el eje no admite celdas, TODAS las que compiten declaran ``cell_axis_without_cell``.
    cell_fallback: Mapping[str, str] = field(default_factory=dict)

    def multiplier_for(self, strategy_version: str) -> float:
        return self.multipliers.get(str(strategy_version or ""), 1.0)

    def cell_for(self, strategy_version: str) -> str | None:
        """Régimen de la celda que aportó el peso de una versión (``None`` si no se usó celda)."""
        return self.cell_used.get(str(strategy_version or ""))

    def cell_note_for(self, strategy_version: str) -> str | None:
        """Motivo declarado del hueco de celda de una versión (``None`` si su celda se usó)."""
        return self.cell_fallback.get(str(strategy_version or ""))

    def as_dict(self) -> dict[str, Any]:
        # FASE INTACTA: el frame de ``allocation`` sigue siendo ``riskMultipliers`` + ``evidenceAxis``
        # (lo fijó el sello de ``AUTO-13``). La base de CELDA es un eje propio y se publica en el plan
        # (``AdaptivePlan.as_dict()['allocationCells']``), no se cuela en el frame sellado.
        return {
            "riskMultipliers": dict(sorted(self.multipliers.items())),
            "evidenceAxis": self.evidence_axis,
        }


@dataclass(frozen=True, slots=True)
class RecoveryEvidence:
    """Evidencia medida con la que se juzga la RAMPA de una versión que dejó de estar pausada.

    La rampa **sube por evidencia, no por reloj**: ``measured_cycles`` cuenta los ciclos CERRADOS
    con resultado medido **positivo** posteriores a ``reactivated_at``. ``measured_positive`` y
    ``severe_decay`` son los dos hechos que **reinician** la rampa (el deterioro manda), y
    ``window_available`` declara el hueco de fechas: sin instantes legibles no se puede contar
    —la misma ausencia que ``AUTO-12`` declara como ``recent_unavailable``— y la rampa no sube.
    Nunca se inventa una recuperación que no se pudo medir.
    """

    strategy_version: str
    measured_cycles: int = 0
    window_available: bool = True
    measured_positive: bool = True
    severe_decay: bool = False

    @property
    def note(self) -> str | None:
        """Motivo declarado de que la rampa no avance (``None`` si no hay hueco que declarar)."""
        if self.severe_decay:
            return ADAPTIVE_RECOVERY_NOTE_SEVERE
        if not self.measured_positive:
            return ADAPTIVE_RECOVERY_NOTE_NOT_POSITIVE
        if not self.window_available:
            return ADAPTIVE_RECOVERY_NOTE_UNMEASURED
        return None


@dataclass(frozen=True, slots=True)
class RecoveryReading:
    """El escalón de la rampa de UNA versión ``RECOVERING`` + los hechos que lo motivaron.

    ``step`` es el valor **aplicado** como techo del reparto, y ``note`` declara por qué no subió
    cuando el hueco existe: sin esa declaración, un ``0.25`` congelado no se distinguiría de una
    rampa que avanza despacio.
    """

    strategy_version: str
    step: float
    step_index: int
    evidence_cycles: int = 0
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategyVersion": self.strategy_version,
            "step": self.step,
            "stepIndex": self.step_index,
            "evidenceCycles": self.evidence_cycles,
            "note": self.note,
        }


def recovery_reading(
    evidence: RecoveryEvidence, policy: AdaptivePolicy | None = None
) -> RecoveryReading:
    """(PURA) escalón de la rampa: avanza SOLO con evidencia positiva medida; el deterioro la reinicia.

    ``escalón = escalones[min(último, ciclos_positivos // recovery_step_cycles)]``. Con deterioro
    declarado (``decay == SEVERE``), con evidencia reciente no positiva, o sin fechas legibles, el
    escalón es el **inicial** (el suelo): la rampa no sube por tiempo ni por ausencia de datos.
    """
    resolved = policy or AdaptivePolicy()
    steps = tuple(float(step) for step in resolved.recovery_steps)
    cycles = max(0, int(evidence.measured_cycles))
    note = evidence.note
    if note is not None:
        return RecoveryReading(
            strategy_version=evidence.strategy_version,
            step=steps[0],
            step_index=0,
            evidence_cycles=cycles,
            note=note,
        )
    per = max(1, int(resolved.recovery_step_cycles))
    index = min(len(steps) - 1, cycles // per)
    return RecoveryReading(
        strategy_version=evidence.strategy_version,
        step=steps[index],
        step_index=index,
        evidence_cycles=cycles,
        note=None,
    )


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
    #: AUTO-13 — estado OPERATIVO por estrategia (§23/§29): ``active`` / ``paused`` /
    #: ``recovering``. Es un eje propio y se **deriva**; no vive en la rotación.
    operational_states: Mapping[str, str] = field(default_factory=dict)
    #: AUTO-13 — la rampa por versión ``RECOVERING`` (escalón aplicado + hechos + motivo). Vacía
    #: cuando el llamante no aportó evidencia de recuperación: entonces no hay rampa (§24) y el
    #: plan es el histórico.
    recovery: Mapping[str, RecoveryReading] = field(default_factory=dict)
    #: AUTO-13 (§20) — versiones cuyo régimen del cruce **no se pudo determinar**. Con el cruce
    #: indeterminado la rotación por régimen NO aplica y decide la evidencia **global** (la fila de
    #: la estrategia); esta tupla es la DECLARACIÓN de ese hueco, con campo propio para que nadie
    #: la lea como un régimen ni se mezcle con el eje operativo o el de datos.
    regime_undetermined: tuple[str, ...] = ()
    #: AUTO-13 (§29) — si el reparto USÓ la confianza estadística. ``False`` cuando el gate limitó la
    #: adaptación (``DEGRADED``/``STALE``): el encogimiento por evidencia fina queda desactivado. Es
    #: un eje propio y **no** se mezcla con la calidad MEDIDA: ``shrinkage=False`` con
    #: ``health.confidence = LOW`` es un estado legal y perfectamente legible
    #: (``ACTIVE`` + datos ``DEGRADED`` + calidad ``LOW``, el ejemplo del §29).
    shrinkage: bool = True

    def is_paused(self, strategy_version: str) -> bool:
        return self.rotation.is_paused(strategy_version)

    def state_for(self, strategy_version: str) -> str:
        """Estado operativo derivado de una versión (``PAUSED`` si no se declaró otra cosa)."""
        key = str(strategy_version or "")
        if key in self.operational_states:
            return self.operational_states[key]
        return ADAPTIVE_STATE_PAUSED if self.rotation.is_paused(key) else ADAPTIVE_STATE_ACTIVE

    def recovery_for(self, strategy_version: str) -> RecoveryReading | None:
        return self.recovery.get(str(strategy_version or ""))

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
            # AUTO-12 — la confianza estadística viaja con la evidencia: sin ella, el
            # operador no puede distinguir un edge medido sobre 12 ciclos de uno sobre 180.
            "confidence": row.confidence,
            "recentExpectancyR": row.recent_expectancy_r,
            "longExpectancyR": row.long_expectancy_r,
            "decay": row.decay,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": ADAPTIVE_KEY,
            "readOnly": self.read_only,
            "policyVersion": self.policy_version,
            "regime": self.regime,
            "rotation": self.rotation.as_dict(),
            "allocation": self.allocation.as_dict(),
            "operationalStates": dict(sorted(self.operational_states.items())),
            "recovery": {
                version: reading.as_dict()
                for version, reading in sorted(self.recovery.items())
            },
            # §20: el hueco del cruce se publica con campo PROPIO (no se mezcla con el régimen del
            # tick, ni con el estado operativo, ni con el estado de datos del gate).
            "regimeUndetermined": list(self.regime_undetermined),
            # §29: si el reparto PUDO usar la confianza fina. Campo propio: la calidad medida sigue
            # en ``healthByStrategy[version].confidence`` aunque el encogimiento esté desactivado.
            "shrinkage": self.shrinkage,
            # AUTO-14 (§20): la base de CELDA del reparto, con campo propio y en el nivel del plan
            # (el sub-frame de ``allocation`` queda sellado como lo dejó ``AUTO-13``). ``axis`` es el
            # eje en que las celdas afinaron —``None`` si no se aplicaron—, ``used`` el régimen de la
            # celda que aportó el peso de cada versión y ``fallback`` el motivo del hueco. Sin esto,
            # un multiplicador no dice si se midió en el régimen del tick o en el agregado global.
            "allocationCells": {
                "axis": self.allocation.cell_axis,
                "used": dict(sorted(self.allocation.cell_used.items())),
                "fallback": dict(sorted(self.allocation.cell_fallback.items())),
            },
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


def _cell_key(value: Any) -> str:
    """Normalización DECLARADA del régimen para cruzar celdas: caja y espacios, nada más.

    El plan recibe el régimen **canónico** de mercado (el worker ya lo traduce con
    ``to_market_regime``) y las celdas guardan el régimen del ciclo en ese MISMO eje. Aquí no se
    traduce otra vez: un segundo mapa de alias podría divergir del que usó la rotación. Solo se
    normaliza la FORMA (``strip`` + ``upper``).
    """
    return str(value or "").strip().upper()


def regime_cell_for(
    cells: Sequence[StrategyRegimeEvaluation],
    strategy_version: str,
    regime: str | None,
) -> tuple[StrategyRegimeEvaluation | None, str | None]:
    """(PURA) la celda **utilizable** de ``(versión, régimen)``, o ``(None, motivo)``.

    Utilizable = existe, es ``decisive`` (su muestra alcanza ``min_trades`` y tiene el R medido en
    todos sus ciclos), su **R neto** está ``COMPLETE`` y es **positivo**. Cualquier otro caso devuelve
    el motivo DECLARADO con el que el reparto caerá a la evidencia global de la fila.

    Nunca se elige otra celda, ni la de otra versión, ni la de otro ciclo, ni se hereda el régimen de
    otro turno: sin coincidencia, el hueco se declara (la lección del §20/``M81``). Y sin régimen
    legible (``None``, vacío o ``UNKNOWN``) no hay juicio de régimen en absoluto.
    """
    version = str(strategy_version or "")
    key = _cell_key(regime)
    if not key or key == ADAPTIVE_REGIME_UNKNOWN:
        return None, ADAPTIVE_CELL_NOTE_REGIME_ABSENT
    found = next(
        (
            cell
            for cell in cells
            if str(cell.strategy_version or "") == version and _cell_key(cell.regime) == key
        ),
        None,
    )
    if found is None:
        return None, ADAPTIVE_CELL_NOTE_NOT_FOUND
    if not found.decisive:
        return None, ADAPTIVE_CELL_NOTE_NOT_DECISIVE
    if not is_complete(found.net_r_measurement):
        return None, ADAPTIVE_CELL_NOTE_NET_UNMEASURED
    if found.net_expectancy_r is None or found.net_expectancy_r <= 0:
        return None, ADAPTIVE_CELL_NOTE_NOT_POSITIVE
    return found, None


@dataclass(frozen=True, slots=True)
class _AllocationSources:
    """La base del reparto: eje, pesos que compiten y la DECLARACIÓN de la celda (AUTO-14)."""

    axis: str
    positive: dict[str, float]
    #: El eje en el que las celdas afinaron el peso, o ``None`` (no se aplicaron).
    cell_axis: str | None = None
    #: Versión → régimen de la celda que aportó su peso.
    cell_used: Mapping[str, str] = field(default_factory=dict)
    #: Versión → motivo por el que su peso salió del global.
    cell_fallback: Mapping[str, str] = field(default_factory=dict)


def _allocation_weights(
    rows_by_version: Mapping[str, StrategySelfEvaluation],
    active_versions: Sequence[str],
    *,
    cells_by_version: Mapping[str, Sequence[StrategyRegimeEvaluation]] | None = None,
    regime: str | None = None,
) -> _AllocationSources:
    """(PURA) eje del reparto, pesos que compiten en él y de dónde salió cada peso.

    Los dos ejes NO son comparables entre sí: ``expectancy_currency`` es absoluta
    (moneda) y ``net_expectancy_r`` es adimensional (múltiplos de R), así que un reparto
    que mezclase pesos de ambos sería aritmética sin sentido. Por eso el eje se elige
    para el GRUPO —nunca por fila— y el R neto solo se adopta cuando los dos ejes
    coinciden en QUIÉN compite: así el cambio de eje puede mover los pesos relativos pero
    jamás la composición del numerador, y una estrategia con R no medido no queda fuera
    del reparto por un hueco de medición (el desconocido no es un defecto).

    El gate de decisividad es POR FILA en los dos ejes: una expectativa no validada por
    su muestra no entra al numerador, aunque otra estrategia del grupo sí sea decisoria.
    El R neto exige además ``net_r_measurement == COMPLETE`` (§6.3: un ``PARTIAL`` —algún ciclo sin
    coste— no habilita decidir contra el agregado). AUTO-16 no cambia la condición: cambia de dónde
    sale el coste que el neto descuenta (``netRBasis``, ``applied`` o ``estimated``).

    **AUTO-14 — la celda afina el PESO, nunca la composición.** Quién compite en el eje del R
    neto lo decide la FILA (``decisive`` + neto medido y positivo), igual que en ``v2.50``–``v2.54``.
    Para cada versión que YA competía, su número se toma de su **celda** ``strategy × regime`` del
    régimen del tick cuando la celda es utilizable; si no, se queda con el **global** y el motivo se
    declara. Con el eje de **moneda** no se aplica celda alguna (la celda mide R, no moneda: no se
    fabrica un cociente paralelo) y TODAS las que compiten lo declaran.
    """
    currency: dict[str, float] = {}
    net_r: dict[str, float] = {}
    cell_used: dict[str, str] = {}
    cell_fallback: dict[str, str] = {}
    cells = cells_by_version or {}
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
            # La versión COMPITE en el eje del R neto (lo decide la FILA, no la celda).
            net_r[version] = float(row.net_expectancy_r)
            cell, note = regime_cell_for(cells.get(version, ()), version, regime)
            if cell is not None:
                # La celda solo puede mover el NÚMERO de quien ya competía.
                net_r[version] = float(cell.net_expectancy_r)
                cell_used[version] = cell.regime
            else:
                # Nace un motivo por construcción, pero nunca se silencia un ``None``.
                cell_fallback[version] = note or ADAPTIVE_CELL_NOTE_NOT_FOUND
    if net_r and net_r.keys() == currency.keys():
        return _AllocationSources(
            axis=ALLOCATION_AXIS_NET_R,
            positive=net_r,
            cell_axis=ALLOCATION_AXIS_NET_R,
            cell_used=cell_used,
            cell_fallback=cell_fallback,
        )
    # Eje de MONEDA: el reparto sigue siendo el histórico (global) y se declara por qué la celda no
    # pudo afinar: la celda mide R y R neto, no moneda por régimen.
    return _AllocationSources(
        axis=ALLOCATION_AXIS_CURRENCY,
        positive=currency,
        cell_axis=None,
        cell_used={},
        cell_fallback={
            version: ADAPTIVE_CELL_NOTE_AXIS_WITHOUT_CELL for version in sorted(currency)
        },
    )


def _cell_confidence(
    confidence: StrategyConfidence | None,
    regime: str | None,
) -> RegimeConfidence | None:
    """(PURA) la banda de confianza de UNA celda, o ``None`` (el reparto usa entonces la fila).

    ``AUTO-12`` ya publica la confianza **por celda** (``StrategyConfidence.by_regime``): si el peso
    de la versión salió de su celda, el encogimiento se mide con la muestra efectiva y el deterioro
    de ESA celda, no con los agregados de la estrategia (que mezclan regímenes que no se parecen).
    """
    if confidence is None or not _cell_key(regime):
        return None
    key = _cell_key(regime)
    for cell in confidence.by_regime:
        if _cell_key(cell.regime) == key:
            return cell
    return None


def _confidence_factor(
    confidence: StrategyConfidence | None,
    *,
    prior: float,
    policy: AdaptivePolicy,
) -> float:
    """(PURA) factor de encogimiento por muestra efectiva (y deterioro severo), o ``1.0``.

    ``shrink = effective_n / (effective_n + prior)``. Sin lectura de confianza el factor es
    ``1.0``: el comportamiento histórico se conserva. Con ``decay == SEVERE`` se aplica el
    factor declarado por la política — nunca una pausa, solo menos peso.
    """
    if confidence is None:
        return 1.0
    effective_n = max(0, int(getattr(confidence, "effective_n", 0) or 0))
    denominator = effective_n + max(0.0, prior)
    shrink = (effective_n / denominator) if denominator > 0 else 1.0
    if getattr(confidence, "decay", None) == ADAPTIVE_DECAY_SEVERE:
        shrink *= max(0.0, float(policy.severe_decay_factor))
    return shrink


def recommend_allocation(
    active: Iterable[str],
    by_strategy: Sequence[StrategySelfEvaluation],
    *,
    policy: AdaptivePolicy | None = None,
    confidence: AdaptiveConfidence | None = None,
    recovery: Mapping[str, RecoveryReading] | None = None,
    by_regime: Sequence[StrategyRegimeEvaluation] = (),
    regime: str | None = None,
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
    * **AUTO-12** — con ``confidence``, el peso de cada decisoria positiva se encoge por su
      muestra efectiva antes de normalizar, de modo que un edge medido sobre pocos ciclos no
      desplace a otro con base amplia (*winner chasing*). El encogimiento solo redistribuye:
      el reparto sigue sumando-preservando, acotado a ``[0, 1]`` y sin eliminar a nadie.
    * **AUTO-13** — con ``recovery``, el multiplicador de una versión que vuelve de una pausa pasa
      por el **techo de la rampa** (``m_final = min(m_reparto, escalón)``, §24). Es un techo, así que
      solo estrecha, nunca ensancha, y el suelo de la política (> 0) impide dejar a nadie en ``0``:
      la reincorporación es gradual, no una pausa encubierta. Se aplica **después** del reparto
      para que el valor publicado sea el aplicado.
    * **AUTO-14** — con ``by_regime``/``regime``, el peso de una versión que YA competía se toma de su
      **celda** ``strategy × regime`` del régimen del tick cuando la celda está medida; si no, del
      global, y el hueco se declara (``cell_used``/``cell_fallback``). La celda afina el **peso**,
      nunca la composición, y con el eje de moneda no se aplica (se declara). El encogimiento de
      ``AUTO-12`` usa entonces la banda de la **celda**, no la de la estrategia.

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
    cells_by_version: dict[str, list[StrategyRegimeEvaluation]] = {}
    for cell in by_regime:
        cells_by_version.setdefault(str(cell.strategy_version or ""), []).append(cell)
    sources = _allocation_weights(
        rows_by_version,
        active_versions,
        cells_by_version=cells_by_version,
        regime=regime,
    )
    axis = sources.axis
    positive = sources.positive
    if positive and confidence is not None:
        prior = max(0.0, float(resolved.confidence_prior))
        adjusted: dict[str, float] = {}
        for version, weight in positive.items():
            # AUTO-14: si el peso salió de la CELDA, el encogimiento se mide con la banda de ESA
            # celda (su muestra efectiva y su deterioro), no con los agregados de la estrategia.
            basis: StrategyConfidence | RegimeConfidence | None = _cell_confidence(
                confidence.confidence_for(version), sources.cell_used.get(version)
            )
            if basis is None:
                basis = confidence.confidence_for(version)
            factor = _confidence_factor(basis, prior=prior, policy=resolved)
            shrunk = weight * factor
            # El encogimiento NUNCA elimina a nadie del reparto: si un factor degenerara a 0
            # se conserva el peso original (quitar a una estrategia es una DECISIÓN, y
            # Adaptive solo recomienda).
            adjusted[version] = shrunk if shrunk > 0.0 else weight
        positive = adjusted

    neutral = _clamp_unit(resolved.unknown_multiplier)
    multipliers: dict[str, float] = {}
    if positive:
        count = len(positive)
        total = sum(positive.values())
        for version in active_versions:
            share = positive.get(version)
            if share is None:
                multipliers[version] = neutral
            else:
                multipliers[version] = _clamp_unit((share / total) * count)
    else:
        for version in active_versions:
            multipliers[version] = neutral
    if recovery:
        # AUTO-13: la rampa es un TECHO del reparto (§24). ``min`` con el escalón declarado, que ya
        # vive en ``(0, 1]``: nunca ensancha y nunca deja a nadie en 0. Aplicado después del reparto
        # y antes de publicar, para que la evidencia durable lleve el valor que de verdad se aplicó.
        for version in active_versions:
            reading = recovery.get(version)
            if reading is None:
                continue
            multipliers[version] = _clamp_unit(min(multipliers[version], float(reading.step)))
    return AllocationPlan(
        multipliers,
        evidence_axis=axis,
        cell_axis=sources.cell_axis,
        cell_used=sources.cell_used,
        cell_fallback=sources.cell_fallback,
    )


def build_adaptive_plan(
    by_strategy: Sequence[StrategySelfEvaluation],
    regime: str | None,
    *,
    policy: AdaptivePolicy | None = None,
    paused_cycles: Mapping[str, int] | None = None,
    by_regime: Sequence[StrategyRegimeEvaluation] = (),
    confidence: AdaptiveConfidence | None = None,
    recovery: Mapping[str, RecoveryEvidence] | None = None,
    shrink: bool = True,
) -> AdaptivePlan:
    """(PURA) plan Adaptive completo: rotación + asignación sobre las mismas filas.

    ``regime`` es el ``MarketRegime`` del gobernador (``TREND_UP``/``TREND_DOWN``/
    ``RANGE``/``HIGH_VOL``/``LOW_VOL``/``UNKNOWN``), no el eje operativo. ``confidence``
    (AUTO-12) es OPCIONAL: sin ella el plan es byte-idéntico al histórico y la rotación no
    cambia (la confianza solo modula el reparto, nunca quién compite).

    ``shrink`` (AUTO-13 §29) separa **medir** la confianza de **usarla para repartir**: con
    ``shrink=False`` (el efecto ``LIMITS``/``FREEZES`` del gate) el reparto cae a su eje histórico
    —no se estrecha por evidencia fina que no es de fiar— pero la banda MEDIDA sigue publicándose
    en la evidencia. Ocultarla sería mezclar los ejes: la calidad estadística es un hecho medido,
    no un permiso de uso.

    ``recovery`` (AUTO-13) es OPCIONAL y **declarado**: solo debe traer las versiones que
    vuelven de una pausa cumplida (§24). Sin él no hay rampa y el plan es el histórico — la
    trampa de ``AUTO-12`` con ``confidence=None``, repetida. Quien pausa y reactiva sigue
    siendo ``recommend_rotation``: el estado operativo (``RECOVERING``) es **derivado**, no un
    cuarto modo de la rotación.
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
    # La rampa se materializa por versión, pero solo COMPITE la que no está pausada: si el
    # deterioro devuelve a pausa, la rotación manda y el escalón se DESCARTA (§24) — no se
    # publica una rampa que no se aplicó.
    readings: dict[str, RecoveryReading] = {}
    if recovery:
        for raw_version, evidence in recovery.items():
            version = str(raw_version or "")
            if version and not rotation.is_paused(version):
                readings[version] = recovery_reading(evidence, resolved)
    operational: dict[str, str] = {}
    for row in by_strategy:
        version = row.strategy_version
        if rotation.is_paused(version):
            operational[version] = ADAPTIVE_STATE_PAUSED
        else:
            reading = readings.get(version)
            # El escalón tope (1.00) es la recuperación CUMPLIDA: vuelve a ``ACTIVE``.
            if reading is not None and reading.step < 1.0:
                operational[version] = ADAPTIVE_STATE_RECOVERING
            else:
                operational[version] = ADAPTIVE_STATE_ACTIVE
    active_versions = [
        row.strategy_version for row in by_strategy if not rotation.is_paused(row.strategy_version)
    ]
    allocation = recommend_allocation(
        active_versions,
        by_strategy,
        policy=resolved,
        # §29: la confianza se ENCUENTRA medida, pero solo se usa para repartir si el llamante lo
        # permite (``shrink``). Lo que el gate retira es el uso, nunca el hecho medido.
        confidence=confidence if shrink else None,
        recovery=readings or None,
        # AUTO-14 (§20): el reparto por CELDA de régimen. Las celdas son MATERIAL del reparto (como
        # ``by_regime`` en la rotación y la salud), no un uso de la confianza: se pasan siempre, y
        # sin régimen legible la celda no se elige (el hueco se declara). El gate las gobierna
        # indirectamente —sin régimen no hay celda— sin mezclar los ejes.
        by_regime=cells,
        regime=regime,
    )
    health = build_strategy_health(by_strategy, by_regime=cells, confidence=confidence)
    return AdaptivePlan(
        rotation=rotation,
        allocation=allocation,
        regime=regime,
        policy_version=resolved.policy_version,
        health=health,
        operational_states=operational,
        recovery=readings,
        shrinkage=shrink,
        # §20: quién NO tiene régimen de cruce determinado. Se DERIVA de la salud —el par
        # ``(regime, motivo)`` se conserva en ``StrategyHealth``— en vez de recalcular el cruce
        # aquí: un segundo cálculo podría divergir del que usó la rotación. Ordenada por versión:
        # la reproducibilidad del plan no puede depender del orden de entrada de las filas.
        regime_undetermined=tuple(
            sorted(row.strategy_version for row in health if row.regime_undetermined)
        ),
    )
