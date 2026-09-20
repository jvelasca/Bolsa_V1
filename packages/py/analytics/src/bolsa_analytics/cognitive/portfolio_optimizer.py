"""PortfolioOptimizer (AUTO-4 · V2.44 · `1.69.0-beta`).

El invariante de esta fase, en una frase: **el ranking deja de ser la decisión**. Hasta
`V2.43.3`, `plan_v2_tick` rankeaba, recortaba al `TOP_N` y decidía **una a una** en ese
orden; la primera del ranking entraba y las siguientes solo si la anterior dejaba hueco.
Aquí el `TOP_N` pasa a ser el **tamaño del conjunto candidato** y la cartera elige
**la combinación** que maximiza el valor esperado sujeto a restricciones duras.

Qué maximiza y qué respeta:

* **Objetivo** — máximo `Σ net_expected_currency` (valor esperado económico de la
  combinación, de `expected_value.py`).
* **Desempate** (el «MIN Portfolio Risk» del roadmap, implementado como desempate
  declarado y no como optimización multi-objetivo con pesos): a igual valor esperado
  **gana la combinación de menor riesgo** (`Σ risk_amount`); a igual riesgo, la
  combinación lexicográficamente menor (reproducibilidad).
* **Restricciones duras** — capital (`Σ notional <= available_cash`), capacidad
  (`|S| <= max_positions`), concentración por sector (`<= max_sector_pct` de la equity),
  correlación (`<= max_correlation`, *fail-closed* si es desconocida), liquidez
  (`>= min_liquidity_notional`) y permiso de riesgo nuevo (`new_risk_allowed`).
* **La opción "no operar" compite** — el conjunto vacío tiene valor `0`: si ninguna
  combinación factible tiene valor esperado **positivo**, el optimizador elige **no
  operar**. Un optimizador que siempre encuentra algo que comprar no es un optimizador.

**Enumeración exacta acotada.** Se enumeran **todos** los subconjuntos de tamaño
`1..max_positions` del conjunto candidato (deterministas: candidatas ordenadas por
`instrument_id` y `itertools.combinations`). El espacio crece exponencialmente y por eso
hay un **tope declarado**: si el número de subconjuntos a evaluar supera
`max_combinations`, el optimizador **no optimiza** — devuelve `UNKNOWN` con el motivo
`optimizer_enumeration_cap_exceeded` y el llamante **cae al camino del ranking**. No hay
degradación silenciosa a greedy: una búsqueda distinta no puede presentarse como la
misma decisión.

**Fail-closed, no permisivo.** Una candidata cuyo valor esperado no se pudo medir **no
entra** en ninguna combinación (y se declara con su motivo), en vez de puntuar `0` y
colarse por la puerta de atrás. Una candidata cuya correlación o liquidez no se conoce
cuando la restricción está activa es **infeasible**, no "probablemente bien".

Módulo **puro**: sin I/O, sin reloj, sin red, sin aleatoriedad.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from bolsa_analytics.cognitive.expected_value import ExpectedValue
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)

#: Motivos de no-selección (vocabulario del journal; los publica el llamante).
OPTIMIZER_NOT_SELECTED = "optimizer_not_selected"
OPTIMIZER_EXPECTED_VALUE_UNMEASURED = "optimizer_expected_value_unmeasured"
OPTIMIZER_NOTIONAL_UNMEASURED = "optimizer_notional_unmeasured"
OPTIMIZER_RISK_UNMEASURED = "optimizer_risk_unmeasured"
OPTIMIZER_CORRELATION_UNKNOWN = "optimizer_correlation_unknown"
OPTIMIZER_CORRELATION_EXCEEDED = "optimizer_correlation_exceeded"
OPTIMIZER_LIQUIDITY_UNKNOWN = "optimizer_liquidity_unknown"
OPTIMIZER_LIQUIDITY_BELOW_MINIMUM = "optimizer_liquidity_below_minimum"
OPTIMIZER_CAPITAL_EXCEEDED = "optimizer_capital_exceeded"
OPTIMIZER_SECTOR_UNMEASURED = "optimizer_sector_unmeasured"
OPTIMIZER_SECTOR_EXCEEDED = "optimizer_sector_exceeded"
OPTIMIZER_DRAWDOWN_BLOCKS_NEW_RISK = "optimizer_drawdown_blocks_new_risk"
OPTIMIZER_ENUMERATION_CAP_EXCEEDED = "optimizer_enumeration_cap_exceeded"

#: Tope por defecto de subconjuntos a evaluar (`2^12`). Con `TOP_N=5` (default) el
#: espacio nominal es `2^5 − 1 = 31`, así que el tope **no ata** en el caso nominal.
DEFAULT_MAX_COMBINATIONS = 4096

UNKNOWN_SECTOR = "<unknown>"


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _non_negative(value: Any) -> float | None:
    number = _finite(value)
    if number is None or number < 0.0:
        return None
    return number


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


@dataclass(frozen=True, slots=True)
class OptimizerCandidate:
    """Una oportunidad candidata, con lo que la cartera necesita para decidir.

    ``expected_value`` es de `expected_value.py`; ``notional``/``risk_amount`` vienen del
    **mismo** `compute_allocation` que dimensionará la orden (para que la foto del
    optimizador y la decisión real no puedan discrepar). ``sector``/``liquidity_notional``/
    ``correlation_with_portfolio`` son los ejes de restricción de cartera.
    """

    instrument_id: str
    expected_value: ExpectedValue = ExpectedValue()
    notional: float | None = None
    risk_amount: float | None = None
    sector: str | None = None
    liquidity_notional: float | None = None
    correlation_with_portfolio: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "expectedValue": self.expected_value.to_dict(),
            "notional": self.notional,
            "riskAmount": self.risk_amount,
            "sector": self.sector,
            "liquidityNotional": self.liquidity_notional,
            "correlationWithPortfolio": self.correlation_with_portfolio,
        }


@dataclass(frozen=True, slots=True)
class OptimizerConstraints:
    """Restricciones duras del conjunto. Todas opcionales salvo la capacidad.

    ``None`` en un límite significa **sin límite declarado** (no "cero"): solo cuando la
    restricción está **activa** se exige el dato que la verifica, y su ausencia es
    infeasible (fail-closed).
    """

    max_positions: int = 1
    available_cash: float | None = None
    equity: float | None = None
    max_sector_pct: float | None = None
    max_correlation: float | None = None
    min_liquidity_notional: float | None = None
    new_risk_allowed: bool = True
    max_combinations: int = DEFAULT_MAX_COMBINATIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "maxPositions": self.max_positions,
            "availableCash": self.available_cash,
            "equity": self.equity,
            "maxSectorPct": self.max_sector_pct,
            "maxCorrelation": self.max_correlation,
            "minLiquidityNotional": self.min_liquidity_notional,
            "newRiskAllowed": self.new_risk_allowed,
            "maxCombinations": self.max_combinations,
        }


@dataclass(frozen=True, slots=True)
class OptimizerRejection:
    """Por qué una candidata no está en la combinación elegida (nunca en silencio)."""

    instrument_id: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"instrumentId": self.instrument_id, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class OptimizerDecision:
    """Resultado: la combinación elegida, su valor y **por qué** se descartó el resto."""

    selected: tuple[str, ...] = ()
    objective: float | None = None
    expected_value_total: float | None = None
    risk_total: float | None = None
    combinations_evaluated: int = 0
    candidates_considered: int = 0
    rejections: tuple[OptimizerRejection, ...] = ()
    measurement: MeasurementStatus = MEASUREMENT_COMPLETE
    notes: tuple[str, ...] = ()

    @property
    def decided(self) -> bool:
        """¿El optimizador llegó a decidir (frente a abortar por tope/UNKNOWN)?"""
        return self.measurement != MEASUREMENT_UNKNOWN

    def reasons_by_instrument(self) -> dict[str, str]:
        return {r.instrument_id: r.reason for r in self.rejections}

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": list(self.selected),
            "objective": self.objective,
            "expectedValueTotal": self.expected_value_total,
            "riskTotal": self.risk_total,
            "combinationsEvaluated": self.combinations_evaluated,
            "candidatesConsidered": self.candidates_considered,
            "rejections": [r.to_dict() for r in self.rejections],
            "measurement": self.measurement,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class _Feasible:
    ids: tuple[str, ...]
    value: float
    risk: float


def _subsets_count(n: int, max_positions: int) -> int:
    """Número de subconjuntos de tamaño `1..max_positions` de `n` elementos."""
    if n <= 0 or max_positions <= 0:
        return 0
    top = min(n, max_positions)
    return sum(math.comb(n, k) for k in range(1, top + 1))


def optimize_portfolio(
    candidates: Iterable[OptimizerCandidate],
    constraints: OptimizerConstraints | None = None,
) -> OptimizerDecision:
    """Elige la combinación de la cartera por valor esperado sujeto a riesgo."""
    cfg = constraints if constraints is not None else OptimizerConstraints()

    ordered = sorted(candidates, key=lambda c: str(c.instrument_id).strip())
    rejected: dict[str, str] = {}

    # El permiso de riesgo nuevo es de la CARTERA, no de la candidata: si no se permite
    # abrir riesgo, ninguna combinación no vacía es feasible y se declara el motivo (una
    # decisión de "cero operaciones" es una decisión COMPLETA, no un UNKNOWN).
    if not cfg.new_risk_allowed:
        return OptimizerDecision(
            selected=(),
            objective=0.0,
            expected_value_total=0.0,
            risk_total=0.0,
            combinations_evaluated=0,
            candidates_considered=len(ordered),
            rejections=tuple(
                OptimizerRejection(str(c.instrument_id).strip(), OPTIMIZER_DRAWDOWN_BLOCKS_NEW_RISK)
                for c in ordered
            ),
            measurement=MEASUREMENT_COMPLETE,
            notes=("new_risk_not_allowed",),
        )

    measurable: list[OptimizerCandidate] = []
    for candidate in ordered:
        instrument_id = str(candidate.instrument_id).strip()
        value = candidate.expected_value.net_expected_currency
        if value is None:
            # Sin valor esperado medible NO se puntúa 0 (se colaría como el peor de los
            # "medidos" y podría entrar si todos los demás son peores).
            rejected[instrument_id] = OPTIMIZER_EXPECTED_VALUE_UNMEASURED
            continue
        measurable.append(candidate)

    if not measurable:
        return OptimizerDecision(
            selected=(),
            objective=0.0,
            expected_value_total=0.0,
            risk_total=0.0,
            combinations_evaluated=0,
            candidates_considered=len(ordered),
            rejections=tuple(
                OptimizerRejection(cid, reason) for cid, reason in sorted(rejected.items())
            ),
            measurement=MEASUREMENT_COMPLETE,
            notes=("no_measurable_candidates",),
        )

    total_subsets = _subsets_count(len(measurable), cfg.max_positions)
    cap = cfg.max_combinations if cfg.max_combinations > 0 else DEFAULT_MAX_COMBINATIONS
    if total_subsets > cap:
        # Tope de combinatoria: NO se optimiza (nada de greedy silencioso). El llamante
        # cae al camino del ranking y lo declara.
        return OptimizerDecision(
            selected=(),
            combinations_evaluated=0,
            candidates_considered=len(ordered),
            rejections=tuple(
                OptimizerRejection(str(c.instrument_id).strip(), OPTIMIZER_ENUMERATION_CAP_EXCEEDED)
                for c in ordered
            ),
            measurement=MEASUREMENT_UNKNOWN,
            notes=(OPTIMIZER_ENUMERATION_CAP_EXCEEDED,),
        )

    feasible: list[_Feasible] = []
    evaluated = 0
    top = min(len(measurable), cfg.max_positions)
    for size in range(1, top + 1):
        for combo in itertools.combinations(measurable, size):
            evaluated += 1
            verdict = _combination_verdict(combo, cfg)
            if verdict is None:
                feasible.append(
                    _Feasible(
                        ids=tuple(str(c.instrument_id).strip() for c in combo),
                        value=_round4(
                            sum(
                                c.expected_value.net_expected_currency or 0.0 for c in combo
                            )
                        ),
                        risk=_round4(sum(_finite(c.risk_amount) or 0.0 for c in combo)),
                    )
                )
            else:
                # Se guarda el PRIMER motivo de infeasibilidad por candidata: si una
                # candidata no cabe en ninguna combinación, su motivo es el que la
                # bloquea (más informativo que un genérico "not selected").
                for candidate in combo:
                    rejected.setdefault(str(candidate.instrument_id).strip(), verdict)

    # El conjunto vacío compite con valor 0: si nada factible tiene valor POSITIVO, la
    # decisión es no operar (y no un "algo habrá que comprar").
    best: _Feasible | None = None
    for item in feasible:
        if item.value <= 0.0:
            continue
        if best is None or _better(item, best):
            best = item

    if best is None:
        return OptimizerDecision(
            selected=(),
            objective=0.0,
            expected_value_total=0.0,
            risk_total=0.0,
            combinations_evaluated=evaluated,
            candidates_considered=len(ordered),
            rejections=tuple(
                OptimizerRejection(
                    str(c.instrument_id).strip(),
                    rejected.get(str(c.instrument_id).strip(), OPTIMIZER_NOT_SELECTED),
                )
                for c in ordered
            ),
            measurement=MEASUREMENT_COMPLETE,
            notes=("empty_set_wins",),
        )

    selected_set = set(best.ids)
    return OptimizerDecision(
        selected=best.ids,
        objective=best.value,
        expected_value_total=best.value,
        risk_total=best.risk,
        combinations_evaluated=evaluated,
        candidates_considered=len(ordered),
        rejections=tuple(
            OptimizerRejection(
                str(c.instrument_id).strip(),
                rejected.get(str(c.instrument_id).strip(), OPTIMIZER_NOT_SELECTED),
            )
            for c in ordered
            if str(c.instrument_id).strip() not in selected_set
        ),
        measurement=MEASUREMENT_COMPLETE,
        notes=(),
    )


def _better(candidate: _Feasible, current: _Feasible) -> bool:
    """¿`candidate` mejora a `current`? Mayor valor; a igual valor, menor riesgo; a
    igual riesgo, combinación lexicográficamente menor (determinismo)."""
    if candidate.value != current.value:
        return candidate.value > current.value
    if candidate.risk != current.risk:
        return candidate.risk < current.risk
    return candidate.ids < current.ids


def _combination_verdict(
    combo: Sequence[OptimizerCandidate], cfg: OptimizerConstraints
) -> str | None:
    """Motivo por el que la combinación **no** es feasible, o ``None`` si lo es."""
    # 1) Correlación y liquidez: se exige el dato solo si la restricción está activa.
    for candidate in combo:
        verdict = _candidate_verdict(candidate, cfg)
        if verdict is not None:
            return verdict

    # 2) Riesgo medido: sin `risk_amount` no se puede comparar contra nada ni desempatar.
    for candidate in combo:
        if _non_negative(candidate.risk_amount) is None:
            return OPTIMIZER_RISK_UNMEASURED

    # 3) Capital: `Σ notional <= available_cash` (el invariante del roadmap).
    if cfg.available_cash is not None:
        cash = _non_negative(cfg.available_cash)
        if cash is None:
            return OPTIMIZER_CAPITAL_EXCEEDED
        total_notional = 0.0
        for candidate in combo:
            notional = _non_negative(candidate.notional)
            if notional is None:
                return OPTIMIZER_NOTIONAL_UNMEASURED
            total_notional += notional
        if _round4(total_notional) > cash:
            return OPTIMIZER_CAPITAL_EXCEEDED

    # 4) Concentración por sector de la COMBINACIÓN (as-if, sobre la equity declarada).
    if cfg.max_sector_pct is not None:
        equity = _finite(cfg.equity)
        if equity is None or equity <= 0.0:
            return OPTIMIZER_SECTOR_UNMEASURED
        limit = _non_negative(cfg.max_sector_pct)
        if limit is not None:
            by_sector: dict[str, float] = {}
            for candidate in combo:
                notional = _non_negative(candidate.notional)
                if notional is None:
                    return OPTIMIZER_NOTIONAL_UNMEASURED
                sector = candidate.sector if candidate.sector and candidate.sector.strip() else UNKNOWN_SECTOR
                by_sector[sector] = by_sector.get(sector, 0.0) + notional
            for notional in by_sector.values():
                if (notional / equity) * 100.0 > limit:
                    return OPTIMIZER_SECTOR_EXCEEDED

    return None


def _candidate_verdict(candidate: OptimizerCandidate, cfg: OptimizerConstraints) -> str | None:
    if cfg.max_correlation is not None:
        limit = _non_negative(cfg.max_correlation)
        correlation = _finite(candidate.correlation_with_portfolio)
        if correlation is None:
            return OPTIMIZER_CORRELATION_UNKNOWN
        if limit is not None and abs(correlation) > limit:
            return OPTIMIZER_CORRELATION_EXCEEDED

    if cfg.min_liquidity_notional is not None:
        floor = _non_negative(cfg.min_liquidity_notional)
        if floor is not None and floor > 0.0:
            liquidity = _finite(candidate.liquidity_notional)
            if liquidity is None:
                return OPTIMIZER_LIQUIDITY_UNKNOWN
            if liquidity < floor:
                return OPTIMIZER_LIQUIDITY_BELOW_MINIMUM
    return None


__all__ = [
    "DEFAULT_MAX_COMBINATIONS",
    "OPTIMIZER_CAPITAL_EXCEEDED",
    "OPTIMIZER_CORRELATION_EXCEEDED",
    "OPTIMIZER_CORRELATION_UNKNOWN",
    "OPTIMIZER_DRAWDOWN_BLOCKS_NEW_RISK",
    "OPTIMIZER_ENUMERATION_CAP_EXCEEDED",
    "OPTIMIZER_EXPECTED_VALUE_UNMEASURED",
    "OPTIMIZER_LIQUIDITY_BELOW_MINIMUM",
    "OPTIMIZER_LIQUIDITY_UNKNOWN",
    "OPTIMIZER_NOTIONAL_UNMEASURED",
    "OPTIMIZER_NOT_SELECTED",
    "OPTIMIZER_RISK_UNMEASURED",
    "OPTIMIZER_SECTOR_EXCEEDED",
    "OPTIMIZER_SECTOR_UNMEASURED",
    "OptimizerCandidate",
    "OptimizerConstraints",
    "OptimizerDecision",
    "OptimizerRejection",
    "optimize_portfolio",
]
