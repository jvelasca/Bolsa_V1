"""DÍA-D retrospectivo **as-run** — núcleo puro de evaluación (ADR-049).

Qué responde
------------
Los métodos DÍA-D existentes (``v2_89``–``v2_97``) rejuegan **el motor** desde D y contestan
«qué habría decidido la estrategia». Este módulo contesta otra pregunta:

    Si en D hubiéramos seguido EXACTAMENTE la operativa que llevábamos —posiciones, stops,
    mandato—, ¿qué habría pasado hasta hoy, y qué aportó o costó cada decisión?

Para eso compara la operativa real (brazo ``as_run``) contra brazos contrafactuales
(``hold_structural``, ``cash``, ``engine_params``, ``market_bh`` y, si existe, ``candidate``)
sobre el mismo estado inicial y el mismo modelo de ejecución declarado.

Invariantes (ADR-049 §3.3)
--------------------------
* **Sin look-ahead**: en el paso ``t`` solo se leen barras ``<= t``. El futuro se usa para
  calcular PnL, nunca para decidir. Hay un test de invariancia por prefijo que lo demuestra.
* **Estado inicial real**: se recibe del ledger durable; no se reconstruye a ojo.
* **Ejecución realista**: comisión, deslizamiento, spread, política de gaps y cota de
  participación sobre el volumen. Un gap adverso se ejecuta al ``open`` de la barra, no al
  precio teórico del stop.
* **Determinismo**: orden canónico, redondeo fijo y hash estable (``sort_keys`` + separadores
  compactos). Misma entrada ⇒ mismo ``hash``.
* **Gaps declarados**: un hueco es ``NOT_MEASURED`` con motivo; nunca se rellena con ``0``.
* **Read-only**: función pura. No toca PostgreSQL, ni el motor, ni la configuración.

Este módulo **no** autoriza operaciones ni promociona estrategias: produce un artefacto de
medición que se lee, no que se ejecuta. La certificación del método vive en
``bolsa_application.dia_d_certification``.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

from bolsa_domain.entities.ohlcv_bar import OhlcvBar

__all__ = [
    "ARM_AS_RUN",
    "ARM_CANDIDATE",
    "ARM_CASH",
    "ARM_ENGINE_PARAMS",
    "ARM_HOLD_STRUCTURAL",
    "ARM_MARKET_BH",
    "AS_RUN_ARMS",
    "ARTIFACT_SCHEMA_VERSION",
    "AS_RUN_ENGINE",
    "AsRunArmResult",
    "AsRunExecutionModel",
    "AsRunFill",
    "AsRunLeg",
    "AsRunOpenPosition",
    "AsRunOperationRow",
    "AsRunRiskReference",
    "AsRunVerdict",
    "DECISION_QUALITIES",
    "GAP_POLICY_OPEN",
    "GAP_POLICY_THEORETICAL",
    "BENCHMARK_CAPITAL_INITIAL",
    "BENCHMARK_CAPITAL_UNIT",
    "OUTCOMES",
    "OUTCOME_BREAKEVEN",
    "OUTCOME_LOSS",
    "OUTCOME_OPEN",
    "OUTCOME_UNMEASURED",
    "OUTCOME_WIN",
    "QUALITY_CONSISTENT",
    "QUALITY_INCONSISTENT",
    "QUALITY_UNMEASURED",
    "REAL_FILLS_COST_EFFECTIVE",
    "REAL_FILLS_COST_QUOTED",
    "UNIVERSE_SOURCE_DECLARED",
    "UNIVERSE_SOURCE_DERIVED",
    "artifact_hash",
    "build_as_run_artifact",
    "evaluate_multi_day",
    "execution_model_for",
    "mark_open_positions",
    "run_as_run_arm",
    "run_candidate_arm",
    "run_cash_arm",
    "run_engine_params_arm",
    "run_hold_arm",
    "run_market_bh_arm",
    "verify_bars_manifest",
]

ARM_AS_RUN = "as_run"
ARM_HOLD_STRUCTURAL = "hold_structural"
ARM_CASH = "cash"
ARM_ENGINE_PARAMS = "engine_params"
ARM_CANDIDATE = "candidate"
#: Benchmark de mercado: comprar y mantener equiponderado el estado inicial.
ARM_MARKET_BH = "market_bh"

AS_RUN_ARMS: tuple[str, ...] = (
    ARM_AS_RUN,
    ARM_HOLD_STRUCTURAL,
    ARM_CASH,
    ARM_ENGINE_PARAMS,
    ARM_CANDIDATE,
    ARM_MARKET_BH,
)

#: Estados de veredicto por cohorte. ``insufficient_sample`` se declara, no se disfraza.
VERDICT_AS_RUN_BEATS = "as_run_beats_arms"
VERDICT_ARMS_BEAT = "arms_beat_as_run"
VERDICT_INSUFFICIENT = "insufficient_sample"

#: Muestra mínima por cohorte para emitir veredicto comparativo (ADR-049 §3.4).
DEFAULT_MIN_COHORT_SAMPLES = 12

#: Coste **round-trip** declarado por defecto del brazo AUTO medido en la línea base (32 bps).
DEFAULT_COST_BPS = 32.0

#: Cota de participación por defecto sobre el volumen de la barra (nunca liquidez infinita).
DEFAULT_MAX_PARTICIPATION_PCT = 0.10

#: Base de coste de los fills reales del brazo ``as_run``.
#: ``quoted``: el precio del fill es bruto y el coste se cobra en caja.
#: ``effective``: el precio del fill ya incorpora el coste y el modelo no cobra nada.
REAL_FILLS_COST_QUOTED: Literal["quoted"] = "quoted"
REAL_FILLS_COST_EFFECTIVE: Literal["effective"] = "effective"
_REAL_FILLS_COST_BASES = (REAL_FILLS_COST_QUOTED, REAL_FILLS_COST_EFFECTIVE)

#: Origen del universo de D declarado en el sobre de auditoría.
UNIVERSE_SOURCE_DECLARED = "declared"
UNIVERSE_SOURCE_DERIVED = "derived"

#: Base de capital del benchmark: notional inicial de las patas o una unidad por instrumento.
BENCHMARK_CAPITAL_INITIAL = "initial_notional"
BENCHMARK_CAPITAL_UNIT = "unit"

#: Un gap adverso se ejecuta al ``open`` real de la barra (comportamiento por defecto).
GAP_POLICY_OPEN = "open"
#: Un gap se ejecuta al precio teórico del stop/target (solo para comparar metodologías).
GAP_POLICY_THEORETICAL = "theoretical"

# ── ledger por operación ────────────────────────────────────────────────────
#: Desenlace **medido** de una operación. ``open`` es una posición viva al cierre de la
#: ventana (se marca, no se suma al realizado) y ``unmeasured`` un hueco declarado.
OUTCOME_WIN = "win"
OUTCOME_LOSS = "loss"
OUTCOME_BREAKEVEN = "breakeven"
OUTCOME_OPEN = "open"
OUTCOME_UNMEASURED = "unmeasured"
OUTCOMES: tuple[str, ...] = (
    OUTCOME_WIN,
    OUTCOME_LOSS,
    OUTCOME_BREAKEVEN,
    OUTCOME_OPEN,
    OUTCOME_UNMEASURED,
)

#: Calidad de la DECISIÓN, no del resultado. ``consistent`` = la salida se explica por una
#: regla declarada y tiene denominador de riesgo; un ciclo perdedor puede ser una decisión
#: consistente. ``inconsistent`` = el hecho no es reconstruible (venta sin inventario, sin
#: atribución); ``unmeasured`` = falta el dato para juzgarla.
QUALITY_CONSISTENT = "consistent"
QUALITY_INCONSISTENT = "inconsistent"
QUALITY_UNMEASURED = "unmeasured"
DECISION_QUALITIES: tuple[str, ...] = (
    QUALITY_CONSISTENT,
    QUALITY_INCONSISTENT,
    QUALITY_UNMEASURED,
)

#: Motivos de salida que corresponden a una regla declarada (no a una marca de fin de ventana).
_RULE_EXIT_REASONS = ("stop", "target", "trailing", "thesis_invalidation", "structural")

_GAP_POLICIES = (GAP_POLICY_OPEN, GAP_POLICY_THEORETICAL)
_DIRECTIONS = ("long", "short")

#: Motor y esquema del artefacto. v2 añade sobre de auditoría y certificación.
AS_RUN_ENGINE = "dia-d-as-run-v2"
ARTIFACT_SCHEMA_VERSION = "DiaDAsRunArtifactV2"


def _round(value: float, places: int = 6) -> float:
    """Redondeo fijo para que la aritmética sea reproducible entre ejecuciones."""
    return round(float(value), places)


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def artifact_hash(payload: Mapping[str, Any]) -> str:
    """Hash estable de un artefacto (claves ordenadas, separadores compactos)."""
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


# ── modelo de ejecución ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AsRunExecutionModel:
    """Costes y restricciones de ejecución **declarados** para todos los brazos.

    Convención (la misma de :class:`bolsa_application.baseline_arms.BaselineCosts`):

    * ``roundTripBps = 2 × (commissionBps + slippageBps) + spreadBps``. Es el número que se
      compara con ``minRoundTripCostBps`` y el que se publica como ``costBps``.
    * El **deslizamiento** se aplica al precio de ejecución (peor precio), no al coste en
      caja, para que el PnL y el R sean coherentes entre sí.
    * ``executionCostBps = 2 × commissionBps + spreadBps`` es lo que se cobra en caja por
      ida y vuelta, porque el deslizamiento ya está dentro del precio.

    ``maxParticipationPct`` limita la cantidad que una barra puede absorber
    (``volumen × pct``). ``None`` desactiva la cota; nunca se asume liquidez infinita por
    omisión cuando hay volumen declarado.

    ``real_fills_cost_basis`` declara qué representa el precio de un fill **real** del brazo
    ``as_run``: bruto (``quoted``, se cobra el coste en caja) o ya neto de coste
    (``effective``, no se cobra nada). Sin esta declaración el as-run podría estar cobrando
    dos veces, o ninguna, y el PnL seguiría pareciendo plausible.
    """

    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    spread_bps: float = 0.0
    max_participation_pct: float | None = DEFAULT_MAX_PARTICIPATION_PCT
    gap_policy: str = GAP_POLICY_OPEN
    real_fills_cost_basis: Literal["quoted", "effective"] = REAL_FILLS_COST_QUOTED

    def __post_init__(self) -> None:
        for name in ("commission_bps", "slippage_bps", "spread_bps"):
            value = _finite(getattr(self, name))
            if value is None or value < 0:
                raise ValueError(f"{name} debe ser un número finito >= 0")
        if self.gap_policy not in _GAP_POLICIES:
            raise ValueError(f"gap_policy no soportada: {self.gap_policy!r}")
        if self.max_participation_pct is not None:
            pct = _finite(self.max_participation_pct)
            if pct is None or not 0 < pct <= 1:
                raise ValueError("max_participation_pct debe estar en (0, 1] o ser None")
        if self.real_fills_cost_basis not in _REAL_FILLS_COST_BASES:
            raise ValueError(
                f"real_fills_cost_basis no soportada: {self.real_fills_cost_basis!r}"
            )
        if self.real_fills_cost_basis == REAL_FILLS_COST_EFFECTIVE and (
            self.commission_bps or self.spread_bps
        ):
            raise ValueError(
                "real_fills_cost_basis='effective' exige commission_bps=0 y spread_bps=0: "
                "el precio ya es neto de coste y cobrarlo otra vez lo duplicaría"
            )

    @property
    def round_trip_bps(self) -> float:
        """Coste declarado de ida y vuelta (comparable con los umbrales de línea base)."""
        return 2.0 * (self.commission_bps + self.slippage_bps) + self.spread_bps

    @property
    def execution_cost_bps(self) -> float:
        """Coste que se cobra en caja (sin deslizamiento: ya está en el precio)."""
        return 2.0 * self.commission_bps + self.spread_bps

    def to_dict(self) -> dict[str, Any]:
        return {
            "commissionBps": _round(self.commission_bps, 4),
            "slippageBps": _round(self.slippage_bps, 4),
            "spreadBps": _round(self.spread_bps, 4),
            "roundTripBps": _round(self.round_trip_bps, 4),
            "executionCostBps": _round(self.execution_cost_bps, 4),
            "maxParticipationPct": (
                None
                if self.max_participation_pct is None
                else _round(self.max_participation_pct, 4)
            ),
            "gapPolicy": self.gap_policy,
            "realFillsCostBasis": self.real_fills_cost_basis,
        }

    @classmethod
    def from_cost_bps(cls, cost_bps: float) -> AsRunExecutionModel:
        """Compatibilidad: ``cost_bps`` es el coste **round-trip** declarado.

        Sin deslizamiento declarado y sin spread: el reparto ``commission = cost/2`` hace que
        ``executionCostBps`` sea exactamente ``cost_bps``, que es lo que el contrato publica.
        """
        value = _finite(cost_bps)
        if value is None or value < 0:
            raise ValueError("cost_bps debe ser un número finito >= 0")
        return cls(commission_bps=value / 2.0)


def execution_model_for(
    execution: AsRunExecutionModel | None, cost_bps: float
) -> AsRunExecutionModel:
    """Modelo declarado si existe; si no, construido a partir del coste round-trip."""
    return execution if execution is not None else AsRunExecutionModel.from_cost_bps(cost_bps)


# ── tipos de entrada ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AsRunLeg:
    """Posición viva en el día D: lo que el libro tenía de verdad."""

    instrument_id: str
    direction: Literal["long", "short"]
    quantity: float
    entry: float
    structural_stop: float | None = None
    target1: float | None = None
    target2: float | None = None
    #: Ciclo canónico que abrió el lote, si se conoce. Sin él, una posición arrastrada se
    #: mide con el denominador **del instrumento** (el del último ciclo), que es una
    #: aproximación: con reentradas, el stop inicial del lote es el de SU ciclo. No se
    #: publica en ``to_dict`` para no alterar el contrato de las patas; el as-run sólo lo usa
    #: para resolver el denominador.
    cycle_id: str | None = None

    def __post_init__(self) -> None:
        if self.direction not in _DIRECTIONS:
            raise ValueError(f"dirección no soportada: {self.direction!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "quantity": _round(self.quantity),
            "entry": _round(self.entry),
            "structuralStop": None
            if self.structural_stop is None
            else _round(self.structural_stop),
            "target1": None if self.target1 is None else _round(self.target1),
            "target2": None if self.target2 is None else _round(self.target2),
        }


@dataclass(frozen=True, slots=True)
class AsRunRiskReference:
    """Denominador de R de un instrumento tomado de un **hecho durable** de entrada.

    El estado vivo (``sim_auto_positions``) sólo conserva las posiciones que **siguen
    abiertas**: una posición cerrada desaparece y con ella su stop, así que un día cuyos
    ciclos se abren y cierran dentro de la ventana se quedaba sin denominador
    (``no_risk_reference``). El journal durable sí conserva la entrada
    (``auto_position_materialized.entryPrice``) y el stop inicial
    (``auto_protection_event`` con ``kind=PROTECT_APPLIED`` y ``stopAfter``).

    Se usa para **normalizar** R, nunca para decidir: el P&L sigue saliendo de los fills
    reales. ``source`` se publica en el artefacto para que el lector sepa qué denominador
    se aplicó a cada instrumento.
    """

    instrument_id: str
    entry: float
    stop: float
    source: str = "durable_journal"
    #: Ciclo canónico al que pertenece el hecho. Con él, dos ciclos del MISMO instrumento
    #: (reentrada en la ventana) reciben cada uno su propio denominador, en vez de compartir
    #: el del último. ``None`` = referencia a nivel de instrumento (aproximación declarada).
    cycle_id: str | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("AsRunRiskReference sin instrument_id")
        if not math.isfinite(self.entry) or not math.isfinite(self.stop):
            raise ValueError(f"referencia de riesgo no finita: {self.instrument_id}")
        if self.entry == self.stop:
            raise ValueError(f"riesgo nulo (entry == stop): {self.instrument_id}")

    @property
    def risk_per_unit(self) -> float:
        """Distancia entrada→stop, en valor absoluto (largo o corto)."""
        return abs(self.entry - self.stop)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "entry": _round(self.entry),
            "stop": _round(self.stop),
            "riskPerUnit": _round(self.risk_per_unit),
            "source": self.source,
            "cycleId": self.cycle_id,
        }


@dataclass(frozen=True, slots=True)
class AsRunFill:
    """Fill real de la ventana (brazo ``as_run``).

    ``cycle_id`` es el ciclo canónico que el journal atribuyó a la orden de este fill
    (``auto_entry_order.orderId`` en las compras, ``auto_exit_orders.exit_order_id`` en las
    ventas). Un fill troceado comparte el ``cycle_id`` de su orden, así que sirve para agrupar
    por **posición** sin depender de cómo el bróker troceó la ejecución. ``None`` = la fila no
    tiene atribución durable (material anterior al sellado por fill): el llamante declara el
    hueco y el brazo agrupa por episodio de tenencia.
    """

    timestamp: str
    instrument_id: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    cycle_id: str | None = None

    def __post_init__(self) -> None:
        if self.side not in ("buy", "sell"):
            raise ValueError(f"lado no soportado: {self.side!r}")


# ── tipos de salida ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AsRunArmResult:
    """Resultado medido de un brazo. ``measured=False`` ⇒ hueco declarado con motivo."""

    arm: str
    measured: bool
    reason: str | None = None
    realized_r: float | None = None
    pnl_currency: float | None = None
    mae_r: float | None = None
    mfe_r: float | None = None
    capture: float | None = None
    return_pct: float | None = None
    exits: int = 0
    stops: int = 0
    targets: int = 0
    legs: int = 0
    reason_codes: tuple[str, ...] = ()
    decisions: tuple[dict[str, Any], ...] = ()
    #: Lotes sembrados desde ``legs`` (estado arrastrado al inicio de ``D``).
    carried_in_lots: int = 0
    #: Posiciones cerradas, contadas por **episodio de tenencia** (no por fill): una orden
    #: troceada en varios fills es una posición y una reentrada tras quedar plano es otra.
    #: ``exits`` cuenta tramos de venta.
    cycles: int = 0
    #: Riesgo en moneda de las posiciones medidas (``Σ riesgo_por_unidad × cantidad``).
    #: Es el denominador del R de cartera: ``pnlCurrency / riskCurrency``.
    risk_currency: float | None = None
    #: ``(instrumento, fuente)`` del denominador de R aplicado a cada ciclo cerrado.
    #: Fuentes: ``durable_journal`` (hecho durable de entrada), ``state_at_d`` (pata del
    #: estado) y ``missing`` (sin denominador declarado).
    risk_source: tuple[tuple[str, str], ...] = ()
    #: Ledger **por operación** (una fila por posición cerrada o hueco declarado). Es la
    #: fuente del historial «qué pasó y qué habría pasado»; los agregados de arriba se
    #: derivan de él y siguen siendo la referencia del veredicto.
    ledger: tuple[AsRunOperationRow, ...] = ()
    #: Posiciones **vivas** al cierre de la ventana, marcadas a mercado. Nunca se suman al
    #: realizado: ``unrealizedR`` se publica aparte para que un ciclo abierto no se lea como
    #: ganancia o pérdida cerrada.
    open_positions: tuple[AsRunOpenPosition, ...] = ()
    unrealized_r: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "measured": self.measured,
            "reason": self.reason,
            "realizedR": self.realized_r,
            "pnlCurrency": self.pnl_currency,
            "maeR": self.mae_r,
            "mfeR": self.mfe_r,
            "capture": self.capture,
            "returnPct": self.return_pct,
            "exits": self.exits,
            "stops": self.stops,
            "targets": self.targets,
            "legs": self.legs,
            "carriedInLots": self.carried_in_lots,
            "cycles": self.cycles,
            "riskCurrency": self.risk_currency,
            "riskSource": {instrument: source for instrument, source in self.risk_source},
            "unrealizedR": self.unrealized_r,
            "openPositions": [row.to_dict() for row in self.open_positions],
            "ledger": [row.to_dict() for row in self.ledger],
            "reasonCodes": list(self.reason_codes),
            "decisions": [dict(decision) for decision in self.decisions],
        }


@dataclass(frozen=True, slots=True)
class AsRunOperationRow:
    """Una operación del ledger: entrada, salida, resultado y **calidad de la decisión**.

    ``outcome`` describe el resultado (``win``/``loss``/``breakeven``/``open``/``unmeasured``)
    y ``decision_quality`` la reconstruibilidad de la decisión. Son ejes distintos a
    propósito: un ciclo perdedor ejecutado según la regla es una decisión ``consistent``;
    etiquetarlo como fallo enseñaría a juzgar por el resultado.
    """

    arm: str
    instrument_id: str
    direction: str
    quantity: float
    entry_price: float
    entry_day: str | None = None
    structural_stop: float | None = None
    target1: float | None = None
    target2: float | None = None
    risk_per_unit: float | None = None
    risk_source: str | None = None
    exit_day: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    deferred: bool = False
    days_held: int | None = None
    gross_r: float | None = None
    net_r: float | None = None
    pnl_currency: float | None = None
    fees_currency: float | None = None
    mae_r: float | None = None
    mfe_r: float | None = None
    capture: float | None = None
    outcome: str = OUTCOME_UNMEASURED
    decision_quality: str = QUALITY_UNMEASURED
    cycle_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    decisions: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "quantity": _round(self.quantity),
            "entryDay": self.entry_day,
            "entryPrice": _round(self.entry_price),
            "structuralStop": (
                None if self.structural_stop is None else _round(self.structural_stop)
            ),
            "target1": None if self.target1 is None else _round(self.target1),
            "target2": None if self.target2 is None else _round(self.target2),
            "riskPerUnit": None if self.risk_per_unit is None else _round(self.risk_per_unit),
            "riskSource": self.risk_source,
            "exitDay": self.exit_day,
            "exitPrice": None if self.exit_price is None else _round(self.exit_price),
            "exitReason": self.exit_reason,
            "deferred": bool(self.deferred),
            "daysHeld": self.days_held,
            "grossR": None if self.gross_r is None else _round(self.gross_r),
            "netR": None if self.net_r is None else _round(self.net_r),
            "pnlCurrency": (
                None if self.pnl_currency is None else _round(self.pnl_currency, 2)
            ),
            "feesCurrency": (
                None if self.fees_currency is None else _round(self.fees_currency, 2)
            ),
            "maeR": None if self.mae_r is None else _round(self.mae_r),
            "mfeR": None if self.mfe_r is None else _round(self.mfe_r),
            "capture": None if self.capture is None else _round(self.capture),
            "outcome": self.outcome,
            "decisionQuality": self.decision_quality,
            "cycleId": self.cycle_id,
            "reasonCodes": list(self.reason_codes),
            "decisions": [dict(decision) for decision in self.decisions],
        }


@dataclass(frozen=True, slots=True)
class AsRunOpenPosition:
    """Posición viva al cierre de la ventana, marcada a mercado (nunca suma al realizado)."""

    instrument_id: str
    direction: str
    quantity: float
    entry_price: float
    entry_day: str | None = None
    mark_day: str | None = None
    mark_price: float | None = None
    risk_per_unit: float | None = None
    unrealized_r: float | None = None
    unrealized_pnl_currency: float | None = None
    measured: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "direction": self.direction,
            "quantity": _round(self.quantity),
            "entryDay": self.entry_day,
            "entryPrice": _round(self.entry_price),
            "markDay": self.mark_day,
            "markPrice": None if self.mark_price is None else _round(self.mark_price),
            "riskPerUnit": None if self.risk_per_unit is None else _round(self.risk_per_unit),
            "unrealizedR": None if self.unrealized_r is None else _round(self.unrealized_r),
            "unrealizedPnlCurrency": (
                None
                if self.unrealized_pnl_currency is None
                else _round(self.unrealized_pnl_currency, 2)
            ),
            "measured": bool(self.measured),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class AsRunVerdict:
    """Veredicto de una cohorte. Descriptivo: no es causal ni predictivo."""

    verdict: str
    samples: int
    as_run_mean_r: float | None
    best_arm: str | None
    best_arm_mean_r: float | None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "samples": self.samples,
            "asRunMeanR": self.as_run_mean_r,
            "bestArm": self.best_arm,
            "bestArmMeanR": self.best_arm_mean_r,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class _ExitOutcome:
    """Salida de una pata: precio, recorrido y motivo (nunca un precio inventado).

    ``stop``/``target`` son los niveles **aplicados** (con sus multiplicadores): el ledger
    debe poder explicar contra qué se ejecutó el cierre, no solo que hubo un cierre.
    """

    price: float | None
    mae_r: float
    mfe_r: float
    kind: str
    reason: str | None = None
    exit_date: str | None = None
    deferred: bool = False
    stop: float | None = None
    target: float | None = None


# ── primitivas de medición ───────────────────────────────────────────────────


def _risk_per_unit(leg: AsRunLeg) -> float | None:
    """Distancia a stop en precio (el denominador de R). Sin stop no hay R."""
    stop = _finite(leg.structural_stop)
    entry = _finite(leg.entry)
    if stop is None or entry is None:
        return None
    distance = abs(entry - stop)
    return distance if distance > 0 else None


#: De más a menos fiable. Si un instrumento cerró posiciones con denominadores de distinta
#: calidad, `riskSource` publica la **más débil**: el resumen no debe parecer mejor de lo que
#: fue en el peor de sus ciclos.
_SOURCE_RANK: dict[str, int] = {
    "state_at_d": 0,
    "durable_journal": 1,
    "durable_journal_cycle": 2,
}


def _weakest_source(sources: Iterable[str]) -> str:
    """Fuente menos fiable entre las usadas por un instrumento (``missing`` si no hubo)."""
    seen = {str(source) for source in sources}
    if not seen:
        return "missing"
    return min(seen, key=lambda source: (_SOURCE_RANK.get(source, 3), source))


def _arm_bars(
    bars: Sequence[OhlcvBar],
    *,
    after: str | None = None,
) -> list[OhlcvBar]:
    """Barras posteriores a ``after`` en orden ascendente.

    **No look-ahead**: solo devuelve barras estrictamente posteriores a ``after`` (el día D),
    ordenadas por timestamp. La función no conoce el futuro del llamante: se le entrega lo que
    hay y se recorre hacia delante.
    """
    rows = list(bars)
    if after is not None:
        rows = [bar for bar in rows if str(bar.timestamp) > str(after)]
    return sorted(rows, key=lambda bar: str(bar.timestamp))


def _bar_day(bar: OhlcvBar) -> str:
    return str(bar.timestamp)[:10]


def _slip(price: float, model: AsRunExecutionModel, *, side: Literal["buy", "sell"]) -> float:
    """Precio con deslizamiento: comprar es peor más caro, vender es peor más barato."""
    fraction = model.slippage_bps / 10_000.0
    if fraction <= 0:
        return float(price)
    return float(price) * (1.0 + fraction) if side == "buy" else float(price) * (1.0 - fraction)


def _exit_side(leg: AsRunLeg) -> Literal["buy", "sell"]:
    """Cerrar un largo es vender; cerrar un corto es comprar."""
    return "sell" if leg.direction == "long" else "buy"


def _has_capacity(bar: OhlcvBar, quantity: float, model: AsRunExecutionModel) -> bool:
    """¿Puede esta barra absorber la cantidad sin superar la cota de participación?

    ``maxParticipationPct=None`` desactiva la cota (compatibilidad con mediciones antiguas).
    Una barra sin volumen declarado **no** absorbe: se declara el hueco, no se inventa liquidez.
    """
    if model.max_participation_pct is None:
        return True
    volume = _finite(getattr(bar, "volume", None))
    if volume is None or volume <= 0:
        return False
    return abs(float(quantity)) <= volume * float(model.max_participation_pct)


def _trigger(
    leg: AsRunLeg,
    bar: OhlcvBar,
    *,
    stop: float | None,
    target: float | None,
    gap_policy: str,
) -> tuple[float, str] | None:
    """Precio y motivo del cierre si la barra dispara stop o target.

    **Gap-aware**: si la barra abre más allá del stop (adverso) o del target (favorable), el
    fill real es el ``open``, no el precio teórico. Con ``gap_policy="theoretical"`` se
    reproduce la metodología antigua para poder comparar ambas.
    """
    opened = float(bar.open)
    high = float(bar.high)
    low = float(bar.low)
    if leg.direction == "long":
        if stop is not None and opened <= stop:
            return (opened if gap_policy == GAP_POLICY_OPEN else stop), "stop"
        if target is not None and opened >= target:
            return (opened if gap_policy == GAP_POLICY_OPEN else target), "target"
        if stop is not None and low <= stop:
            return stop, "stop"
        if target is not None and high >= target:
            return target, "target"
        return None
    if stop is not None and opened >= stop:
        return (opened if gap_policy == GAP_POLICY_OPEN else stop), "stop"
    if target is not None and opened <= target:
        return (opened if gap_policy == GAP_POLICY_OPEN else target), "target"
    if stop is not None and high >= stop:
        return stop, "stop"
    if target is not None and low <= target:
        return target, "target"
    return None


def _hold_exit(
    leg: AsRunLeg,
    bars: Sequence[OhlcvBar],
    *,
    model: AsRunExecutionModel,
    stop_multiplier: float = 1.0,
    target_multiplier: float = 1.0,
) -> _ExitOutcome:
    """Recorre las barras y devuelve el cierre con deslizamiento y cota de liquidez.

    El stop se comprueba **antes** que el target en la misma barra (política conservadora).
    Si la barra que dispara el cierre no tiene liquidez para absorber la cantidad, el cierre
    se **difiere** al ``open`` de la primera barra posterior que sí la tenga. Si no existe,
    se declara ``liquidity_insufficient``: nunca se rellena el hueco.
    """
    entry = _finite(leg.entry)
    if entry is None:
        return _ExitOutcome(None, 0.0, 0.0, "open", "no_entry")
    risk = _risk_per_unit(leg)
    if risk is None:
        return _ExitOutcome(None, 0.0, 0.0, "open", "no_risk_reference")

    structural = _finite(leg.structural_stop)
    if structural is None:
        stop: float | None = None
    elif leg.direction == "long":
        stop = entry - stop_multiplier * abs(entry - structural)
    else:
        stop = entry + stop_multiplier * abs(entry - structural)

    target1 = _finite(leg.target1)
    target2 = _finite(leg.target2)
    target = target2 if target2 is not None else target1
    if target is not None:
        delta = abs(target - entry) * target_multiplier
        target = entry + delta if leg.direction == "long" else entry - delta

    mae = 0.0
    mfe = 0.0
    last_close: float | None = None
    last_day: str | None = None
    side = _exit_side(leg)
    pending_trigger: str | None = None

    for bar in bars:
        opened = float(bar.open)
        high = float(bar.high)
        low = float(bar.low)
        last_close = float(bar.close)
        last_day = _bar_day(bar)

        if pending_trigger is not None:
            # Cierre diferido: se ejecuta al open de esta barra si puede absorber la cantidad.
            if _has_capacity(bar, leg.quantity, model):
                # La excursión se corta en el precio ejecutado: el rango posterior al open de
                # esta barra ocurre DESPUÉS de la salida y no puede contarse.
                mae, mfe = _touch(mae, mfe, leg, risk, opened)
                price = _slip(opened, model, side=side)
                return _ExitOutcome(
                    _round(price),
                    _round(mae),
                    _round(mfe),
                    pending_trigger,
                    None,
                    last_day,
                    True,
                    stop,
                    target,
                )
            # Sigue sin liquidez: la posición continúa viva y recorre la barra entera.
            mae, mfe = _touch(mae, mfe, leg, risk, high, low)
            continue

        triggered = _trigger(leg, bar, stop=stop, target=target, gap_policy=model.gap_policy)
        if triggered is None:
            mae, mfe = _touch(mae, mfe, leg, risk, high, low)
            continue
        raw_price, kind = triggered
        if not _has_capacity(bar, leg.quantity, model):
            # La barra disparó pero no tiene liquidez: se difiere al open siguiente. La
            # posición sigue viva, así que su rango completo sigue contando.
            pending_trigger = kind
            mae, mfe = _touch(mae, mfe, leg, risk, high, low)
            continue
        # La excursión de la barra de salida solo llega hasta el precio ejecutado: contar el
        # máximo/mínimo completo inflaría el MFE con un tramo que ya no se poseía.
        mae, mfe = _touch(mae, mfe, leg, risk, opened, raw_price)
        price = _slip(raw_price, model, side=side)
        return _ExitOutcome(
            _round(price), _round(mae), _round(mfe), kind, None, last_day, False, stop, target
        )

    if pending_trigger is not None:
        return _ExitOutcome(
            None,
            _round(mae),
            _round(mfe),
            pending_trigger,
            "liquidity_insufficient",
            last_day,
            False,
            stop,
            target,
        )
    if last_close is None:
        return _ExitOutcome(
            None, _round(mae), _round(mfe), "open", "no_bars", None, False, stop, target
        )
    price = _slip(last_close, model, side=side)
    return _ExitOutcome(
        _round(price), _round(mae), _round(mfe), "open", None, last_day, False, stop, target
    )


def _point_r(leg: AsRunLeg, price: float, risk: float) -> float:
    """Excursión en R hasta ``price`` (un punto concreto, no el rango de la barra)."""
    entry = float(leg.entry)
    delta = price - entry if leg.direction == "long" else entry - price
    return delta / risk


def _touch(
    mae: float, mfe: float, leg: AsRunLeg, risk: float, *prices: float
) -> tuple[float, float]:
    """Actualiza MAE/MFE con precios alcanzados **antes** de la salida."""
    for price in prices:
        r_value = _point_r(leg, float(price), risk)
        mae = min(mae, r_value)
        mfe = max(mfe, r_value)
    return mae, mfe


def _r_of(leg: AsRunLeg, exit_price: float) -> float | None:
    entry = _finite(leg.entry)
    risk = _risk_per_unit(leg)
    if entry is None or risk is None:
        return None
    delta = exit_price - entry if leg.direction == "long" else entry - exit_price
    return delta / risk


def _execution_cost_currency(
    exit_price: float, quantity: float, model: AsRunExecutionModel
) -> float:
    """Coste round-trip en caja: ``|qty × precio de salida| × executionCostBps/10⁴``.

    **Única fuente de coste del módulo.** Así el mismo ciclo paga lo mismo medido por
    ``as_run`` (fills reales) o por cualquier brazo contrafactual: el coste se imputa una vez
    sobre el notional de cierre y no por lado. Sin deslizamiento: ya está en el precio.
    """
    return abs(float(quantity)) * abs(float(exit_price)) * (model.execution_cost_bps / 10_000.0)


def _real_fill_cost_currency(
    exit_price: float, quantity: float, model: AsRunExecutionModel
) -> float:
    """Coste en caja de un fill real según la base declarada (``quoted``/``effective``)."""
    if model.real_fills_cost_basis == REAL_FILLS_COST_EFFECTIVE:
        return 0.0
    return _execution_cost_currency(exit_price, quantity, model)


def _r_after_cost(
    leg: AsRunLeg, gross_r: float, exit_price: float, model: AsRunExecutionModel
) -> float:
    """R neto de coste en caja. Sin referencia de riesgo se devuelve el bruto."""
    risk = _risk_per_unit(leg)
    qty = abs(float(leg.quantity))
    if risk is None or qty <= 0:
        return gross_r
    cost_r = _execution_cost_currency(exit_price, qty, model) / (risk * qty)
    return gross_r - cost_r


def _decision(
    date: str | None,
    instrument_id: str,
    action: str,
    price: float | None,
    reason: str,
) -> dict[str, Any]:
    return {
        "date": date,
        "instrument": instrument_id,
        "action": action,
        "price": None if price is None else _round(price),
        "reason": reason,
    }


def _sorted_decisions(decisions: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(
        sorted(decisions, key=lambda d: (str(d.get("date") or ""), str(d.get("instrument") or "")))
    )


def _outcome_of(net_r: float | None) -> str:
    """Resultado de un ciclo medido. Un casi-cero es ``breakeven``, no un ``win`` por ruido."""
    if net_r is None:
        return OUTCOME_UNMEASURED
    if net_r > 1e-9:
        return OUTCOME_WIN
    if net_r < -1e-9:
        return OUTCOME_LOSS
    return OUTCOME_BREAKEVEN


def _days_between(start: str | None, end: str | None) -> int | None:
    """Días naturales entre dos fechas ISO; ``None`` si alguna no es legible."""
    from datetime import date

    try:
        first = date.fromisoformat(str(start or "")[:10])
        last = date.fromisoformat(str(end or "")[:10])
    except ValueError:
        return None
    return (last - first).days


def mark_open_positions(
    legs: Sequence[AsRunLeg],
    fills: Sequence[AsRunFill],
    bars_by_instrument: Mapping[str, Sequence[OhlcvBar]],
    *,
    risk_references: Sequence[AsRunRiskReference] = (),
    to_day: str | None = None,
    execution: AsRunExecutionModel | None = None,
) -> tuple[AsRunOpenPosition, ...]:
    """Marca a mercado lo que el libro deja **abierto** al cierre de la ventana.

    El realizado solo cuenta ciclos cerrados; sin este bloque, un sistema que no vende nada
    parecería «no haber perdido». Se publica aparte y nunca se suma a ``realizedR``.

    La semántica FIFO es la misma del brazo ``as_run`` (sembrar ``legs`` y consumir los
    ``fills``), para que una posición abierta sea exactamente la que el brazo no cerró. El
    último precio se busca en la última barra ``<= to_day``; sin barras se declara el hueco.
    """
    model = execution_model_for(execution, DEFAULT_COST_BPS)
    risk_by_id: dict[str, float] = {}
    for leg in legs:
        risk = _risk_per_unit(leg)
        if risk is not None:
            risk_by_id[leg.instrument_id] = risk
    for reference in risk_references:
        if reference.risk_per_unit > 0:
            risk_by_id.setdefault(reference.instrument_id, reference.risk_per_unit)

    open_lots: dict[str, list[list[Any]]] = {}
    for leg in legs:
        if leg.direction != "long" or float(leg.quantity) <= 0:
            continue
        open_lots.setdefault(leg.instrument_id, []).append(
            [float(leg.quantity), float(leg.entry)]
        )
    for fill in sorted(fills, key=lambda f: str(f.timestamp)):
        instrument = fill.instrument_id
        qty = abs(float(fill.quantity))
        if qty <= 0:
            continue
        lots = open_lots.setdefault(instrument, [])
        if fill.side == "buy":
            lots.append([qty, float(fill.price)])
            continue
        remaining = qty
        while remaining > 1e-12 and lots:
            take = min(remaining, lots[0][0])
            lots[0][0] -= take
            remaining -= take
            if lots[0][0] <= 1e-12:
                lots.pop(0)

    rows: list[AsRunOpenPosition] = []
    for instrument in sorted(open_lots):
        bars = _arm_bars(bars_by_instrument.get(instrument, ()), after=None)
        if to_day is not None:
            bars = [bar for bar in bars if _bar_day(bar) <= str(to_day)]
        for lot in open_lots[instrument]:
            quantity, entry = lot[0], lot[1]
            if quantity <= 1e-12:
                continue
            risk = risk_by_id.get(instrument)
            if not bars:
                rows.append(
                    AsRunOpenPosition(
                        instrument_id=instrument,
                        direction="long",
                        quantity=quantity,
                        entry_price=entry,
                        risk_per_unit=risk,
                        measured=False,
                        reason="no_bars",
                    )
                )
                continue
            mark_day = _bar_day(bars[-1])
            mark_price = float(bars[-1].close)
            if risk is None or risk <= 0:
                rows.append(
                    AsRunOpenPosition(
                        instrument_id=instrument,
                        direction="long",
                        quantity=quantity,
                        entry_price=entry,
                        mark_day=mark_day,
                        mark_price=mark_price,
                        measured=False,
                        reason="no_risk_reference",
                    )
                )
                continue
            unrealized_r = (mark_price - entry) / risk
            pnl = (mark_price - entry) * quantity - _execution_cost_currency(
                mark_price, quantity, model
            )
            rows.append(
                AsRunOpenPosition(
                    instrument_id=instrument,
                    direction="long",
                    quantity=quantity,
                    entry_price=entry,
                    mark_day=mark_day,
                    mark_price=mark_price,
                    risk_per_unit=risk,
                    unrealized_r=_round(unrealized_r),
                    unrealized_pnl_currency=_round(pnl, 2),
                    measured=True,
                )
            )
    return tuple(rows)


def _sum_unrealized(rows: Iterable[AsRunOpenPosition]) -> float | None:
    """R no realizado de las posiciones marcadas; ``None`` si ninguna se pudo medir."""
    values = [row.unrealized_r for row in rows if row.unrealized_r is not None]
    if not values:
        return None
    return _round(sum(values))


# ── brazos ──────────────────────────────────────────────────────────────────


def run_cash_arm() -> AsRunArmResult:
    """Brazo de control: no operar. Siempre medible y siempre cero."""
    return AsRunArmResult(
        arm=ARM_CASH,
        measured=True,
        realized_r=0.0,
        pnl_currency=0.0,
        return_pct=0.0,
        decisions=(_decision(None, "", "cash", None, "no_exposure"),),
    )


def _run_hold_like(
    arm: str,
    legs: Sequence[AsRunLeg],
    bars_by_instrument: Mapping[str, Sequence[OhlcvBar]],
    *,
    after: str | None,
    model: AsRunExecutionModel,
    stop_multiplier: float = 1.0,
    target_multiplier: float = 1.0,
) -> AsRunArmResult:
    if not legs:
        return AsRunArmResult(arm=arm, measured=False, reason="no_open_legs")

    total_r = 0.0
    total_pnl = 0.0
    entry_notional = 0.0
    mae_min = 0.0
    mfe_max = 0.0
    exits = stops = targets = 0
    deferred_exits = 0
    reasons: list[str] = []
    decisions: list[dict[str, Any]] = []
    ledger: list[AsRunOperationRow] = []

    def _gap_row(leg: AsRunLeg, reason: str) -> AsRunOperationRow:
        """Fila declarada de una pata que no se pudo medir (nunca se omite en silencio)."""
        return AsRunOperationRow(
            arm=arm,
            instrument_id=leg.instrument_id,
            direction=leg.direction,
            quantity=float(leg.quantity),
            entry_day=after,
            entry_price=float(leg.entry),
            structural_stop=leg.structural_stop,
            target1=leg.target1,
            target2=leg.target2,
            risk_per_unit=_risk_per_unit(leg),
            outcome=OUTCOME_UNMEASURED,
            decision_quality=QUALITY_UNMEASURED,
            cycle_id=leg.cycle_id,
            reason_codes=(reason,),
        )

    for leg in legs:
        bars = _arm_bars(bars_by_instrument.get(leg.instrument_id, ()), after=after)
        if not bars:
            reasons.append(f"no_bars:{leg.instrument_id}")
            ledger.append(_gap_row(leg, "no_bars"))
            continue
        outcome = _hold_exit(
            leg,
            bars,
            model=model,
            stop_multiplier=stop_multiplier,
            target_multiplier=target_multiplier,
        )
        if outcome.reason is not None:
            reasons.append(f"{outcome.reason}:{leg.instrument_id}")
            ledger.append(_gap_row(leg, outcome.reason))
            continue
        if outcome.price is None:
            reasons.append(f"no_exit:{leg.instrument_id}")
            ledger.append(_gap_row(leg, "no_exit"))
            continue
        gross = _r_of(leg, outcome.price)
        if gross is None:
            reasons.append(f"no_risk_reference:{leg.instrument_id}")
            ledger.append(_gap_row(leg, "no_risk_reference"))
            continue
        net = _r_after_cost(leg, gross, outcome.price, model)
        total_r += net
        direction = 1.0 if leg.direction == "long" else -1.0
        gross_currency = direction * (outcome.price - float(leg.entry)) * abs(float(leg.quantity))
        fees = _execution_cost_currency(outcome.price, leg.quantity, model)
        total_pnl += gross_currency - fees
        entry_notional += abs(float(leg.quantity) * float(leg.entry))
        mae_min = min(mae_min, outcome.mae_r)
        mfe_max = max(mfe_max, outcome.mfe_r)
        exits += 1
        if outcome.kind == "stop":
            stops += 1
        elif outcome.kind == "target":
            targets += 1
        if outcome.deferred:
            deferred_exits += 1
        decisions.append(
            _decision(after, leg.instrument_id, "carried_in", float(leg.entry), "initial_state")
        )
        decisions.append(
            _decision(
                outcome.exit_date,
                leg.instrument_id,
                "exit",
                outcome.price,
                f"{outcome.kind}{'_deferred' if outcome.deferred else ''}",
            )
        )
        ledger.append(
            AsRunOperationRow(
                arm=arm,
                instrument_id=leg.instrument_id,
                direction=leg.direction,
                quantity=float(leg.quantity),
                entry_day=after,
                entry_price=float(leg.entry),
                structural_stop=outcome.stop if outcome.stop is not None else leg.structural_stop,
                target1=leg.target1,
                target2=leg.target2,
                risk_per_unit=_risk_per_unit(leg),
                risk_source="state_at_d",
                exit_day=outcome.exit_date,
                exit_price=outcome.price,
                exit_reason=outcome.kind,
                deferred=outcome.deferred,
                days_held=_days_between(after, outcome.exit_date),
                gross_r=_round(gross),
                net_r=_round(net),
                pnl_currency=_round(gross_currency - fees, 2),
                fees_currency=_round(fees, 2),
                mae_r=_round(outcome.mae_r),
                mfe_r=_round(outcome.mfe_r),
                capture=(
                    _round(net / outcome.mfe_r) if outcome.mfe_r and outcome.mfe_r > 0 else None
                ),
                outcome=_outcome_of(net),
                decision_quality=QUALITY_CONSISTENT,
                cycle_id=leg.cycle_id,
                decisions=(
                    _decision(after, leg.instrument_id, "carried_in", float(leg.entry), "initial_state"),
                    _decision(
                        outcome.exit_date,
                        leg.instrument_id,
                        "exit",
                        outcome.price,
                        f"{outcome.kind}{'_deferred' if outcome.deferred else ''}",
                    ),
                ),
            )
        )

    if exits == 0:
        return AsRunArmResult(
            arm=arm,
            measured=False,
            reason="no_measurable_legs",
            reason_codes=tuple(reasons),
            ledger=tuple(ledger),
        )
    capture = _round(total_r / mfe_max) if mfe_max > 0 else None
    return AsRunArmResult(
        arm=arm,
        measured=True,
        realized_r=_round(total_r),
        pnl_currency=_round(total_pnl, 2),
        mae_r=_round(mae_min),
        mfe_r=_round(mfe_max),
        capture=capture,
        return_pct=_round(100.0 * total_pnl / entry_notional, 4) if entry_notional > 0 else None,
        exits=exits,
        stops=stops,
        targets=targets,
        legs=len(legs),
        reason_codes=tuple(reasons) + (() if not deferred_exits else (f"deferred_exits:{deferred_exits}",)),
        decisions=_sorted_decisions(decisions),
        ledger=tuple(ledger),
    )


def run_hold_arm(
    legs: Sequence[AsRunLeg],
    bars_by_instrument: Mapping[str, Sequence[OhlcvBar]],
    *,
    after: str | None = None,
    cost_bps: float = DEFAULT_COST_BPS,
    execution: AsRunExecutionModel | None = None,
) -> AsRunArmResult:
    """Brazo ``hold_structural``: mantener hasta stop estructural o target."""
    return _run_hold_like(
        ARM_HOLD_STRUCTURAL,
        legs,
        bars_by_instrument,
        after=after,
        model=execution_model_for(execution, cost_bps),
    )


def run_engine_params_arm(
    legs: Sequence[AsRunLeg],
    bars_by_instrument: Mapping[str, Sequence[OhlcvBar]],
    *,
    after: str | None = None,
    cost_bps: float = DEFAULT_COST_BPS,
    execution: AsRunExecutionModel | None = None,
    stop_multiplier: float | None = None,
    target_multiplier: float | None = None,
) -> AsRunArmResult:
    """Brazo ``engine_params``: el motor con los parámetros vigentes declarados.

    Sin parámetros declarados **no** se inventa el resultado: se declara el hueco.
    """
    if stop_multiplier is None and target_multiplier is None:
        return AsRunArmResult(
            arm=ARM_ENGINE_PARAMS,
            measured=False,
            reason="params_not_declared",
        )
    return _run_hold_like(
        ARM_ENGINE_PARAMS,
        legs,
        bars_by_instrument,
        after=after,
        model=execution_model_for(execution, cost_bps),
        stop_multiplier=1.0 if stop_multiplier is None else float(stop_multiplier),
        target_multiplier=1.0 if target_multiplier is None else float(target_multiplier),
    )


def run_candidate_arm(
    legs: Sequence[AsRunLeg] | None,
    bars_by_instrument: Mapping[str, Sequence[OhlcvBar]],
    *,
    after: str | None = None,
    cost_bps: float = DEFAULT_COST_BPS,
    execution: AsRunExecutionModel | None = None,
) -> AsRunArmResult:
    """Brazo ``candidate``: la candidata en evaluación, si existe.

    Sin candidata se declara ``candidate_not_provided``; no se reutiliza el brazo estructural
    como si fuera la candidata.
    """
    if legs is None:
        return AsRunArmResult(
            arm=ARM_CANDIDATE,
            measured=False,
            reason="candidate_not_provided",
        )
    return _run_hold_like(
        ARM_CANDIDATE,
        legs,
        bars_by_instrument,
        after=after,
        model=execution_model_for(execution, cost_bps),
    )


def run_market_bh_arm(
    bars_by_instrument: Mapping[str, Sequence[OhlcvBar]],
    *,
    after: str | None = None,
    cost_bps: float = DEFAULT_COST_BPS,
    execution: AsRunExecutionModel | None = None,
    universe_instruments: Sequence[str] | None = None,
    capital: float | None = None,
    to_day: str | None = None,
) -> AsRunArmResult:
    """Brazo ``market_bh``: comprar y mantener equiponderado el universo de D.

    Es el **benchmark de mercado**, no una decisión de la operativa. Se mide en retorno
    porcentual (no tiene stop, así que no tiene R): devolver un R inventado sería peor que
    declarar que no aplica.

    Para que la comparación signifique algo tiene que compartir con la estrategia el
    **universo** (el declarado en D, no las claves de barras que el llamante haya cargado), el
    **capital** (el notional inicial de las patas, repartido equiponderado), el **periodo**
    (de la primera barra posterior a D a la última ``<= to_day``) y el **coste** (el mismo
    modelo de ejecución, con deslizamiento por ser contrafactual). La liquidez se evalúa con
    la cantidad real del reparto, nunca con una unidad simbólica.
    """
    model = execution_model_for(execution, cost_bps)
    universe = sorted(
        {
            str(item)
            for item in (
                universe_instruments
                if universe_instruments is not None
                else tuple(bars_by_instrument)
            )
        }
    )
    declared_capital = _finite(capital)
    if declared_capital is not None and declared_capital <= 0:
        declared_capital = None
    allocation = (declared_capital / len(universe)) if declared_capital and universe else 1.0

    pnls: list[float] = []
    deployed = 0.0
    reasons: list[str] = []
    decisions: list[dict[str, Any]] = []
    ledger: list[AsRunOperationRow] = []
    side_buy: Literal["buy", "sell"] = "buy"

    for instrument_id in universe:
        bars = _arm_bars(bars_by_instrument.get(instrument_id, ()), after=after)
        if to_day is not None:
            bars = [bar for bar in bars if _bar_day(bar) <= str(to_day)]
        if len(bars) < 2:
            reasons.append(f"no_bars:{instrument_id}")
            continue
        first = bars[0]
        last = bars[-1]
        entry_price = _slip(float(first.open), model, side=side_buy)
        exit_price = _slip(float(last.close), model, side="sell")
        if entry_price <= 0 or exit_price <= 0:
            reasons.append(f"non_positive_price:{instrument_id}")
            continue
        quantity = allocation / entry_price
        if not _has_capacity(first, quantity, model) or not _has_capacity(
            last, quantity, model
        ):
            reasons.append(f"liquidity_insufficient:{instrument_id}")
            continue
        pnl = (exit_price - entry_price) * quantity - _execution_cost_currency(
            exit_price, quantity, model
        )
        pnls.append(pnl)
        deployed += allocation
        decisions.append(
            _decision(_bar_day(first), instrument_id, "buy", entry_price, "benchmark_entry")
        )
        decisions.append(
            _decision(_bar_day(last), instrument_id, "sell", exit_price, "benchmark_exit")
        )
        ledger.append(
            AsRunOperationRow(
                arm=ARM_MARKET_BH,
                instrument_id=instrument_id,
                direction="long",
                quantity=quantity,
                entry_day=_bar_day(first),
                entry_price=entry_price,
                exit_day=_bar_day(last),
                exit_price=exit_price,
                exit_reason="benchmark_exit",
                days_held=_days_between(_bar_day(first), _bar_day(last)),
                pnl_currency=_round(pnl, 2),
                fees_currency=_round(
                    _execution_cost_currency(exit_price, quantity, model), 2
                ),
                outcome=_outcome_of(pnl),
                decision_quality=QUALITY_CONSISTENT,
                decisions=(
                    _decision(_bar_day(first), instrument_id, "buy", entry_price, "benchmark_entry"),
                    _decision(_bar_day(last), instrument_id, "sell", exit_price, "benchmark_exit"),
                ),
            )
        )

    if not pnls or deployed <= 0:
        return AsRunArmResult(
            arm=ARM_MARKET_BH,
            measured=False,
            reason="no_instruments",
            reason_codes=tuple(reasons),
            ledger=tuple(ledger),
        )
    total_pnl = sum(pnls)
    return AsRunArmResult(
        arm=ARM_MARKET_BH,
        measured=True,
        pnl_currency=_round(total_pnl, 2),
        return_pct=_round(100.0 * total_pnl / deployed, 4),
        exits=len(pnls),
        legs=len(pnls),
        reason_codes=tuple(reasons) + ("benchmark_return_only",),
        decisions=_sorted_decisions(decisions),
    )


def carried_in_legs_from_fills(fills: Sequence[AsRunFill]) -> tuple[AsRunLeg, ...]:
    """Inventario **anterior a ``D``** reconstruido del ledger de fills, con FIFO.

    El estado vivo sólo conserva lo que sigue abierto: una posición abierta antes de ``D`` y
    cerrada dentro de la ventana desaparece de ``sim_auto_positions``, y con ella el
    inventario inicial del replay (sus ventas quedaban como ``unmatched_sell``). Los fills
    previos sí son durables, así que el inventario se reconstruye con la MISMA semántica FIFO
    que usa el brazo.

    Cada lote que sobrevive es una pata propia: no se agrega a precio medio, porque dos lotes
    comprados a precios distintos son dos riesgos distintos. No traen stop de estado: el
    denominador de R lo aporta el journal durable (``AsRunRiskReference``). Sí conservan el
    ``cycle_id`` de la compra que los abrió, para que la venta que los cierra resuelva el
    denominador de SU ciclo.

    Una venta previa sin compra que la respalde no crea inventario negativo (el ledger previo
    no es un estado completo): se ignora aquí y el llamante declara los cortos no
    reconstruidos.
    """
    open_lots: dict[str, list[list[Any]]] = {}
    for fill in sorted(fills, key=lambda f: str(f.timestamp)):
        instrument = fill.instrument_id
        qty = abs(float(fill.quantity))
        price = float(fill.price)
        if qty <= 0:
            continue
        lots = open_lots.setdefault(instrument, [])
        if fill.side == "buy":
            lots.append([qty, price, fill.cycle_id])
            continue
        remaining = qty
        while remaining > 1e-12 and lots:
            lot = lots[0]
            take = min(remaining, lot[0])
            lot[0] -= take
            remaining -= take
            if lot[0] <= 1e-12:
                lots.pop(0)

    legs: list[AsRunLeg] = []
    for instrument in sorted(open_lots):
        for lot in open_lots[instrument]:
            if lot[0] > 1e-12:
                legs.append(
                    AsRunLeg(
                        instrument_id=instrument,
                        direction="long",
                        quantity=lot[0],
                        entry=lot[1],
                        cycle_id=lot[2],
                    )
                )
    return tuple(legs)


def run_as_run_arm(
    legs: Sequence[AsRunLeg],
    fills: Sequence[AsRunFill],
    *,
    cost_bps: float = DEFAULT_COST_BPS,
    execution: AsRunExecutionModel | None = None,
    risk_references: Sequence[AsRunRiskReference] = (),
) -> AsRunArmResult:
    """Brazo ``as_run``: lo que la operativa realmente hizo.

    Empareja compras y ventas por instrumento (FIFO) y mide el R realizado. Una venta sin
    compra previa **no se imputa**: se declara ``unmatched_sell:<instrumento>``. Los fills son
    reales: aquí **no** se aplica deslizamiento (ya está en el precio ejecutado).

    ``legs`` es el estado **arrastrado** al inicio de ``D``: sus lotes se siembran en el FIFO
    para que una venta de una posición que ya venía abierta sea un ciclo cerrado y no un
    ``unmatched_sell``. Los buys del propio día entran como fills, así que sembrar y procesar
    fills no se solapan (si un lote se sembrara además de su compra, el ciclo se contaría dos
    veces: por eso el llamante sólo pasa posiciones abiertas **antes** de ``D``).

    ``risk_references`` aporta el denominador de R desde hechos durables de entrada. Gana
    sobre ``legs`` cuando ambos conocen el instrumento: el stop vivo puede venir arrastrado
    por un trailing y entonces R no mediría la distancia entrada→stop inicial. El
    denominador aplicado se publica por instrumento en ``riskSource``.

    **R es por posición, no por tramo de venta.** La posición se identifica por el
    ``cycle_id`` canónico del fill cuando existe: los fills troceados de una misma orden
    comparten ciclo, y una reentrada del mismo instrumento tiene otro. Sin ``cycle_id`` (filas
    anteriores al sellado por fill) se agrupa por **episodio de tenencia**: los fills son la
    misma posición mientras el libro no quede plano. El P&L de la posición se agrega completo
    y se normaliza por su riesgo en moneda (``distancia_entrada→stop × cantidad``), así que
    vender la misma posición en 4 fills parciales da **un** R y no la suma de 4. ``realizedR``
    es la suma de R de las posiciones: equivale a «R total si cada posición arriesgara 1R»,
    que **no** es el R de la cartera (para eso está ``riskCurrency``: ``pnlCurrency /
    riskCurrency``). ``cycles`` cuenta posiciones cerradas; ``exits`` cuenta tramos de venta.
    """
    model = execution_model_for(execution, cost_bps)
    if not fills:
        return AsRunArmResult(arm=ARM_AS_RUN, measured=False, reason="no_fills")

    risk_by_id: dict[str, float] = {}
    risk_source_by_id: dict[str, str] = {}
    for leg in legs:
        risk = _risk_per_unit(leg)
        if risk is not None and risk > 0:
            risk_by_id[leg.instrument_id] = risk
            risk_source_by_id[leg.instrument_id] = "state_at_d"
    #: Riesgo por CICLO canónico: dos reentradas del mismo instrumento no comparten denominador.
    risk_by_cycle: dict[tuple[str, str], tuple[float, str]] = {}
    for reference in risk_references:
        if reference.risk_per_unit <= 0:
            continue
        if reference.cycle_id:
            risk_by_cycle[(reference.instrument_id, reference.cycle_id)] = (
                reference.risk_per_unit,
                reference.source,
            )
        else:
            risk_by_id[reference.instrument_id] = reference.risk_per_unit
            risk_source_by_id[reference.instrument_id] = reference.source

    def _risk_for(instrument: str, cycle: str | None) -> tuple[float, str] | None:
        """Denominador de R: el del ciclo si se conoce, si no el del instrumento."""
        if cycle is not None:
            found = risk_by_cycle.get((instrument, cycle))
            if found is not None:
                return found
        risk = risk_by_id.get(instrument)
        if risk is None:
            return None
        return risk, risk_source_by_id.get(instrument, "missing")

    # Estado arrastrado: se siembra ANTES de los fills. Sólo largos y con cantidad positiva:
    # una pata corta no se consume con esta semántica FIFO de compra→venta.
    #
    # La unidad de medición es la POSICIÓN, no el fill: una orden troceada en 4 fills de
    # compra y 4 de venta es UNA posición. Con ciclo canónico se usa el del fill; sin él, el
    # episodio avanza cuando el libro del instrumento queda plano. Agrupar por precio de
    # entrada fusionaría dos ciclos al mismo precio; agrupar por fill multiplicaba el R por el
    # número de tramos (el defecto que esto corrige).
    open_lots: dict[str, list[list[Any]]] = {}
    episode_by_instrument: dict[str, int] = {}
    carried_in = 0
    for leg in legs:
        quantity = float(leg.quantity)
        if leg.direction != "long" or quantity <= 0:
            continue
        episode = episode_by_instrument.setdefault(leg.instrument_id, 1)
        # La pata arrastrada conserva el ciclo que abrió su lote (si el linaje lo dice): así una
        # venta posterior hereda el denominador de SU ciclo y no el del último del instrumento.
        position_key = f"cycle:{leg.cycle_id}" if leg.cycle_id else f"episode:{episode}"
        open_lots.setdefault(leg.instrument_id, []).append(
            [quantity, float(leg.entry), 0.0, position_key, leg.cycle_id]
        )
        carried_in += 1

    #: ``(instrumento, posición, cantidad, entrada, salida, ciclo, día)``: un tramo de venta.
    realized: list[tuple[str, str, float, float, float, str | None, str]] = []
    reasons: list[str] = []
    decisions: list[dict[str, Any]] = []
    unmatched: list[tuple[str, float, float, str]] = []

    for fill in sorted(fills, key=lambda f: str(f.timestamp)):
        instrument = fill.instrument_id
        qty = abs(float(fill.quantity))
        price = float(fill.price)
        if qty <= 0:
            continue
        fill_day = str(fill.timestamp)[:10]
        decisions.append(
            _decision(fill_day, instrument, fill.side, price, "real_fill")
        )
        lots = open_lots.setdefault(instrument, [])
        if fill.side == "buy":
            if fill.cycle_id:
                # Ciclo canónico: la identidad de la posición ya no depende del troceo ni de
                # que el libro quede plano entre dos fills de la misma orden.
                position_key = f"cycle:{fill.cycle_id}"
            else:
                if not lots:
                    # Libro plano: reentrada ⇒ ciclo nuevo.
                    episode_by_instrument[instrument] = episode_by_instrument.get(instrument, 0) + 1
                position_key = f"episode:{episode_by_instrument.get(instrument, 1)}"
            lots.append([qty, price, 0.0, position_key, fill.cycle_id])
            continue
        # sell: consume FIFO
        remaining = qty
        while remaining > 1e-12 and lots:
            lot = lots[0]
            take = min(remaining, lot[0])
            # El ciclo del lote manda; si el lote es inventario arrastrado sin ciclo, la orden
            # de SALIDA sí dice qué ciclo cierra y sirve para resolver su denominador de R.
            position_cycle = lot[4] if lot[4] is not None else fill.cycle_id
            realized.append(
                (instrument, str(lot[3]), take, lot[1], price, position_cycle, fill_day)
            )
            lot[0] -= take
            remaining -= take
            if lot[0] <= 1e-12:
                lots.pop(0)
        if remaining > 1e-12:
            reasons.append(f"unmatched_sell:{instrument}")
            unmatched.append((instrument, remaining, price, fill_day))

    if not realized:
        return AsRunArmResult(
            arm=ARM_AS_RUN,
            measured=False,
            reason="no_closed_cycles",
            reason_codes=tuple(reasons),
            carried_in_lots=carried_in,
            ledger=tuple(
                AsRunOperationRow(
                    arm=ARM_AS_RUN,
                    instrument_id=instrument,
                    direction="long",
                    quantity=quantity,
                    entry_price=price,
                    exit_price=price,
                    exit_day=day,
                    exit_reason="unmatched_sell",
                    outcome=OUTCOME_UNMEASURED,
                    decision_quality=QUALITY_INCONSISTENT,
                    reason_codes=("unmatched_sell",),
                )
                for instrument, quantity, price, day in unmatched
            ),
        )

    # R por POSICIÓN, no por tramo (§3.1 del doc de reparación): sumar el R de cada tramo
    # multiplica el resultado por el número de fills parciales y no pondera por tamaño. Se
    # agrega el P&L de la posición completa y se normaliza por su riesgo en moneda.
    slices_by_position: dict[tuple[str, str], list[tuple[float, float, float, str, float]]] = {}
    cycle_by_position: dict[tuple[str, str], str | None] = {}
    total_pnl = 0.0
    entry_notional = 0.0
    for instrument, position, qty, entry, exit_price, cycle_id, day in realized:
        gross_currency = (exit_price - entry) * qty
        cost = _real_fill_cost_currency(exit_price, qty, model)
        net = gross_currency - cost
        total_pnl += net
        entry_notional += abs(entry * qty)
        slices_by_position.setdefault((instrument, position), []).append(
            (qty, entry, exit_price, day, net)
        )
        cycle_by_position[(instrument, position)] = cycle_id

    total_r = 0.0
    risk_currency = 0.0
    missing_risk: list[str] = []
    #: Fuentes realmente usadas por instrumento, para publicar una sola (la más conservadora).
    sources_used: dict[str, set[str]] = {}
    ledger: list[AsRunOperationRow] = [
        AsRunOperationRow(
            arm=ARM_AS_RUN,
            instrument_id=instrument,
            direction="long",
            quantity=quantity,
            entry_price=price,
            exit_price=price,
            exit_day=day,
            exit_reason="unmatched_sell",
            outcome=OUTCOME_UNMEASURED,
            decision_quality=QUALITY_INCONSISTENT,
            reason_codes=("unmatched_sell",),
        )
        for instrument, quantity, price, day in unmatched
    ]
    for (instrument, position), slices in sorted(slices_by_position.items()):
        quantity = sum(qty for qty, _entry, _exit, _day, _net in slices)
        if quantity <= 0:
            continue
        entry_price = sum(qty * entry for qty, entry, _exit, _day, _net in slices) / quantity
        exit_price = sum(qty * exit for qty, _entry, exit, _day, _net in slices) / quantity
        exit_day = max(day for _qty, _entry, _exit, day, _net in slices)
        net = sum(value for _qty, _entry, _exit, _day, value in slices)
        fees = sum(
            _real_fill_cost_currency(exit, qty, model)
            for qty, _entry, exit, _day, _net in slices
        )
        resolved = _risk_for(instrument, cycle_by_position.get((instrument, position)))
        risk, source = resolved if resolved is not None else (None, "missing")
        net_r: float | None = None
        if risk is not None and quantity > 0:
            sources_used.setdefault(instrument, set()).add(source)
            risk_money = risk * quantity
            risk_currency += risk_money
            net_r = net / risk_money
            total_r += net_r
        else:
            missing_risk.append(instrument)
        ledger.append(
            AsRunOperationRow(
                arm=ARM_AS_RUN,
                instrument_id=instrument,
                direction="long",
                quantity=quantity,
                entry_price=entry_price,
                exit_day=exit_day,
                exit_price=exit_price,
                exit_reason="real_sell",
                gross_r=(
                    None
                    if risk is None or risk <= 0
                    else _round((exit_price - entry_price) / risk)
                ),
                net_r=None if net_r is None else _round(net_r),
                pnl_currency=_round(net, 2),
                fees_currency=_round(fees, 2),
                risk_per_unit=risk,
                risk_source=source if risk is not None else "missing",
                outcome=_outcome_of(net_r),
                decision_quality=(
                    QUALITY_CONSISTENT if net_r is not None else QUALITY_UNMEASURED
                ),
                cycle_id=cycle_by_position.get((instrument, position)),
                reason_codes=() if net_r is not None else ("no_risk_reference",),
            )
        )

    risk_sources = tuple(
        (instrument, _weakest_source(sources_used.get(instrument, set())))
        for instrument in sorted({row[0] for row in realized})
    )
    cycles = len(slices_by_position)

    if missing_risk and len(missing_risk) == cycles:
        return AsRunArmResult(
            arm=ARM_AS_RUN,
            measured=False,
            reason="no_risk_reference",
            pnl_currency=_round(total_pnl, 2),
            reason_codes=tuple(reasons) + tuple(f"no_risk_reference:{i}" for i in missing_risk),
            carried_in_lots=carried_in,
            cycles=cycles,
            risk_source=risk_sources,
            ledger=tuple(ledger),
        )
    if missing_risk:
        # Antes se descartaba en silencio: el lote sumaba a la caja pero no al R. Se declara.
        reasons.append(f"partial_risk:{len(missing_risk)}/{cycles}")

    return AsRunArmResult(
        arm=ARM_AS_RUN,
        measured=True,
        realized_r=_round(total_r),
        pnl_currency=_round(total_pnl, 2),
        return_pct=_round(100.0 * total_pnl / entry_notional, 4) if entry_notional > 0 else None,
        exits=len(realized),
        legs=len(legs),
        reason_codes=tuple(reasons),
        decisions=_sorted_decisions(decisions),
        carried_in_lots=carried_in,
        cycles=cycles,
        risk_currency=_round(risk_currency, 2) if risk_currency > 0 else None,
        risk_source=risk_sources,
        ledger=tuple(ledger),
    )


# ── composición ─────────────────────────────────────────────────────────────


def _bar_fingerprint(bar: OhlcvBar) -> str:
    """sha256 de una vela: día y OHLCV canonicalizados (mismos números ⇒ mismo hash)."""
    canon = "|".join(
        [
            _bar_day(bar),
            repr(_round(float(bar.open))),
            repr(_round(float(bar.high))),
            repr(_round(float(bar.low))),
            repr(_round(float(bar.close))),
            str(int(bar.volume)),
        ]
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _bar_manifest_rows(bars: Sequence[OhlcvBar]) -> list[list[str]]:
    rows = sorted(bars, key=lambda bar: str(bar.timestamp))
    return [[_bar_day(bar), _bar_fingerprint(bar)] for bar in rows]


def _bars_fingerprint(bars_by_instrument: Mapping[str, Sequence[OhlcvBar]]) -> dict[str, Any]:
    """Huella determinista de las barras usadas: qué datos produjeron la medición.

    ``barsManifest`` guarda **una huella por vela**, no un resumen opaco: sin ella, cambiar
    una sola vela (o quitar una) no podía detectarse y la certificación heredaba esa ceguera.
    """
    manifest: dict[str, Any] = {}
    for instrument_id in sorted(bars_by_instrument):
        manifest[instrument_id] = _bar_manifest_rows(bars_by_instrument[instrument_id])
    details = [
        {
            "instrument": instrument_id,
            "bars": len(rows),
            "firstBar": rows[0][0] if rows else None,
            "lastBar": rows[-1][0] if rows else None,
        }
        for instrument_id, rows in sorted(manifest.items())
    ]
    return {
        "barsHash": artifact_hash(manifest),
        "barsManifest": manifest,
        "instruments": details,
    }


def verify_bars_manifest(
    manifest: Mapping[str, Any],
    bars_by_instrument: Mapping[str, Sequence[OhlcvBar]],
) -> tuple[str, ...]:
    """Re-verifica un ``barsManifest`` contra las barras de la fuente. Vacío ⇒ coincide.

    No lee ni escribe nada: compara la huella declarada con la que producirían las barras
    recibidas. Un instrumento ausente, una vela cambiada o un día de más son motivos.
    """
    reasons: list[str] = []
    declared = manifest if isinstance(manifest, Mapping) else {}
    for instrument_id in sorted({str(key) for key in declared} | set(bars_by_instrument)):
        expected = _bar_manifest_rows(bars_by_instrument.get(instrument_id, ()))
        rows = declared.get(instrument_id)
        if not isinstance(rows, list):
            reasons.append(f"bars_missing:{instrument_id}")
            continue
        if not rows and not expected:
            # Un instrumento sin barras no rompe la huella: el hueco se declara en los
            # gaps del artefacto. Marcarlo aquí convertía cualquier hueco de datos en un
            # «manifest roto» y el CLI no podía publicar nada.
            continue
        if not expected:
            reasons.append(f"bars_unexpected:{instrument_id}")
            continue
        if len(rows) != len(expected):
            reasons.append(f"bars_count_mismatch:{instrument_id}")
            continue
        if [list(row) if isinstance(row, list) else row for row in rows] != expected:
            reasons.append(f"bars_hash_mismatch:{instrument_id}")
    return tuple(reasons)


def _state_fingerprint(legs: Sequence[AsRunLeg]) -> dict[str, Any]:
    """Huella del estado inicial: las patas exactas que se rejugaron."""
    payload = [leg.to_dict() for leg in legs]
    payload.sort(key=lambda item: str(item["instrumentId"]))
    return {"legsHash": artifact_hash({"legs": payload}), "legs": payload}


def _candidate_gap_reason(
    candidate_legs: Sequence[AsRunLeg] | None,
    *,
    day: str,
    candidate_as_of: str | None,
    universe_instruments: set[str],
) -> str | None:
    """Motivo por el que la candidata NO puede medirse (``None`` si puede).

    Regla de punto en el tiempo: una candidata construida hoy con lo que se sabe hoy no puede
    rejugarse desde D. Sin fecha ``candidate_as_of <= D`` no hay medición, y si toca
    instrumentos fuera del universo declarado en D tampoco.
    """
    if candidate_legs is None:
        return "candidate_not_provided"
    if not candidate_as_of:
        return "candidate_not_point_in_time"
    if str(candidate_as_of)[:10] > day:
        return "candidate_not_point_in_time"
    outside = sorted(
        {leg.instrument_id for leg in candidate_legs} - set(universe_instruments)
    )
    if outside:
        return f"candidate_outside_universe:{','.join(outside)}"
    return None


def build_as_run_artifact(
    *,
    day: str,
    account_id: str,
    legs: Sequence[AsRunLeg],
    fills: Sequence[AsRunFill],
    bars_by_instrument: Mapping[str, Sequence[OhlcvBar]],
    cost_bps: float = DEFAULT_COST_BPS,
    candidate_legs: Sequence[AsRunLeg] | None = None,
    engine_stop_multiplier: float | None = None,
    engine_target_multiplier: float | None = None,
    universe: str = "watch",
    to_day: str | None = None,
    execution: AsRunExecutionModel | None = None,
    state_source: str | None = None,
    bars_source: str | None = None,
    bars_timeframe: str | None = None,
    strategy_version: str | None = None,
    mandate_version: str | None = None,
    params_hash: str | None = None,
    params: Mapping[str, Any] | None = None,
    bump: str | None = None,
    limits: Sequence[str] = (),
    candidate_as_of: str | None = None,
    universe_instruments: Sequence[str] | None = None,
    risk_references: Sequence[AsRunRiskReference] = (),
    candidate_forward: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Artefacto canónico de un día as-run, con brazo por brazo, huecos y sobre de auditoría.

    ``universe_instruments`` es el universo **declarado** de D. Sin él el universo se deriva
    de patas ∪ barras y se marca ``universeSource="derived"``: sirve para medir, pero la
    certificación lo declara ``NOT_EVALUATED`` porque no puede probar que en D se conociera.
    """
    model = execution_model_for(execution, cost_bps)
    derived_universe = {leg.instrument_id for leg in legs} | set(bars_by_instrument)
    if universe_instruments is None:
        universe_set = set(derived_universe)
        universe_source = UNIVERSE_SOURCE_DERIVED
    else:
        universe_set = {str(item) for item in universe_instruments}
        universe_source = UNIVERSE_SOURCE_DECLARED
    declared_params = dict(params) if params is not None else None
    resolved_params_hash = params_hash
    if declared_params is not None:
        computed = artifact_hash(declared_params)
        if params_hash is not None and str(params_hash) != computed:
            raise ValueError("params_hash no coincide con el hash de los params declarados")
        resolved_params_hash = computed
    candidate_reason = _candidate_gap_reason(
        candidate_legs,
        day=day,
        candidate_as_of=candidate_as_of,
        universe_instruments=universe_set,
    )
    candidate_arm = run_candidate_arm(
        None if candidate_reason is not None else candidate_legs,
        bars_by_instrument,
        after=day,
        execution=model,
    )
    if candidate_reason is not None:
        candidate_arm = AsRunArmResult(
            arm=ARM_CANDIDATE, measured=False, reason=candidate_reason
        )

    benchmark_capital = _finite(
        sum(abs(float(leg.quantity) * float(leg.entry)) for leg in legs)
    )
    if benchmark_capital is not None and benchmark_capital <= 0:
        benchmark_capital = None

    as_run_arm = run_as_run_arm(
        legs, fills, execution=model, risk_references=risk_references
    )
    # El realizado solo cuenta ciclos cerrados. Las posiciones vivas se marcan a mercado y
    # viajan APARTE (``unrealizedR``): sumarlas al realizado convertiría un ciclo abierto en
    # ganancia o pérdida cerrada.
    open_positions = mark_open_positions(
        legs,
        fills,
        bars_by_instrument,
        risk_references=risk_references,
        to_day=to_day,
        execution=model,
    )
    if open_positions:
        as_run_arm = replace(
            as_run_arm,
            open_positions=open_positions,
            unrealized_r=_sum_unrealized(open_positions),
        )

    columns: list[AsRunArmResult] = [
        as_run_arm,
        run_hold_arm(legs, bars_by_instrument, after=day, execution=model),
        run_cash_arm(),
        run_engine_params_arm(
            legs,
            bars_by_instrument,
            after=day,
            execution=model,
            stop_multiplier=engine_stop_multiplier,
            target_multiplier=engine_target_multiplier,
        ),
        candidate_arm,
        run_market_bh_arm(
            bars_by_instrument,
            after=day,
            execution=model,
            universe_instruments=sorted(universe_set),
            capital=benchmark_capital,
            to_day=to_day,
        ),
    ]

    gaps = [
        {"arm": column.arm, "reason": column.reason}
        for column in columns
        if not column.measured
    ]

    state = _state_fingerprint(legs)
    data = _bars_fingerprint(bars_by_instrument)

    payload: dict[str, Any] = {
        "engine": AS_RUN_ENGINE,
        "schemaVersion": ARTIFACT_SCHEMA_VERSION,
        "day": day,
        "toDay": to_day,
        "account": account_id,
        "universe": universe,
        "costBps": _round(model.round_trip_bps, 2),
        "startingState": {
            "legs": len(legs),
            "instruments": sorted({leg.instrument_id for leg in legs}),
            "cashOnly": len(legs) == 0,
        },
        "arms": [column.to_dict() for column in columns],
        "gaps": gaps,
        "measured": any(column.measured for column in columns),
        "audit": {
            "pointInTime": {
                "day": day,
                "toDay": to_day,
                "stateSource": state_source,
                "sourceIsReconstructed": False,
                "legsHash": state["legsHash"],
                "legs": state["legs"],
                "candidateAsOf": candidate_as_of,
                "universe": sorted(universe_set),
                "universeSource": universe_source,
            },
            "data": {
                "barsSource": bars_source,
                "timeframe": bars_timeframe,
                "barsHash": data["barsHash"],
                "barsManifest": data["barsManifest"],
                "instruments": data["instruments"],
            },
            "versions": {
                "engine": AS_RUN_ENGINE,
                "schema": ARTIFACT_SCHEMA_VERSION,
                "bump": bump,
                "strategy": strategy_version,
                "mandate": mandate_version,
                "paramsHash": resolved_params_hash,
            },
            "params": declared_params,
            "execution": model.to_dict(),
            "riskReference": {
                "count": len(risk_references),
                "source": "auto_position_materialized.entryPrice + auto_protection_event(PROTECT_APPLIED).stopAfter",
                "instruments": {
                    (
                        f"{reference.instrument_id}|{reference.cycle_id}"
                        if reference.cycle_id
                        else reference.instrument_id
                    ): reference.to_dict()
                    for reference in sorted(
                        risk_references,
                        key=lambda item: (item.instrument_id, item.cycle_id or ""),
                    )
                },
            },
            "benchmark": {
                "universe": sorted(universe_set),
                "capitalBasis": (
                    BENCHMARK_CAPITAL_INITIAL
                    if benchmark_capital is not None
                    else BENCHMARK_CAPITAL_UNIT
                ),
                "capital": benchmark_capital,
                "costBps": _round(model.round_trip_bps, 2),
                "toDay": to_day,
            },
            "decisions": {column.arm: list(column.decisions) for column in columns},
            "limits": [str(limit) for limit in limits],
        },
        "candidateForward": (
            None if candidate_forward is None else dict(candidate_forward)
        ),
    }
    payload["hash"] = artifact_hash(payload)
    return payload


def _mean(values: Iterable[float]) -> float | None:
    rows = [value for value in values if value is not None]
    if not rows:
        return None
    return _round(sum(rows) / len(rows))


def evaluate_multi_day(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    min_samples: int = DEFAULT_MIN_COHORT_SAMPLES,
) -> AsRunVerdict:
    """Agrega varios artefactos as-run y emite el veredicto de la cohorte.

    Compara ``as_run`` contra el **mejor** brazo medido distinto de sí mismo. Con menos de
    ``min_samples`` artefactos medidos el veredicto es ``insufficient_sample``: la muestra
    manda, no la curiosidad. ``market_bh`` no compite en R (no tiene stop): se publica como
    benchmark de retorno y queda fuera de la comparación de R.
    """
    rows: list[tuple[float, dict[str, list[float]]]] = []
    for artifact in artifacts:
        arms = artifact.get("arms")
        if not isinstance(arms, list):
            continue
        per_arm: dict[str, list[float]] = {}
        as_run: float | None = None
        for arm in arms:
            if not isinstance(arm, Mapping) or arm.get("measured") is not True:
                continue
            name = str(arm.get("arm") or "")
            r_value = _finite(arm.get("realizedR"))
            if r_value is None:
                continue
            per_arm.setdefault(name, []).append(r_value)
            if name == ARM_AS_RUN:
                as_run = r_value
        if as_run is not None:
            rows.append((as_run, per_arm))

    samples = len(rows)
    as_run_mean = _mean(row[0] for row in rows)
    if samples < max(1, int(min_samples)):
        return AsRunVerdict(
            verdict=VERDICT_INSUFFICIENT,
            samples=samples,
            as_run_mean_r=as_run_mean,
            best_arm=None,
            best_arm_mean_r=None,
            reason=f"min_samples:{min_samples}",
        )

    arm_names: set[str] = set()
    for _as_run, per_arm in rows:
        arm_names.update(name for name in per_arm if name != ARM_AS_RUN)

    best_arm: str | None = None
    best_mean: float | None = None
    for name in sorted(arm_names):
        values = [per_arm.get(name) for _as_run, per_arm in rows]
        mean = _mean(value[0] for value in values if value)
        if mean is None:
            continue
        if best_mean is None or mean > best_mean:
            best_mean = mean
            best_arm = name

    if as_run_mean is not None and best_mean is not None and as_run_mean >= best_mean:
        verdict = VERDICT_AS_RUN_BEATS
    else:
        verdict = VERDICT_ARMS_BEAT

    return AsRunVerdict(
        verdict=verdict,
        samples=samples,
        as_run_mean_r=as_run_mean,
        best_arm=best_arm,
        best_arm_mean_r=best_mean,
    )
